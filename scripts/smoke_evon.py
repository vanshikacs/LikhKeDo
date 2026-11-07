"""Evon smoke test against the self-hosted OpenAI-compatible endpoint (Phase 2).

Usage (from the repo root, backend venv, after EVON_BASE_URL and EVON_API_KEY are in .env):
  backend/.venv/Scripts/python scripts/smoke_evon.py
"""
from __future__ import annotations

import json
import re
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings  # noqa: E402

DEVANAGARI = re.compile(r"[ऀ-ॿ]")

PITCH = """Sir, ye Suraksha Plus plan bilkul FD jaisa hai.
Isme returns guaranteed hain, minimum 12 percent har saal.
Aapko sirf 5 saal premium dena hai, uske baad koi lock-in nahi.
Aur 10 lakh ka life cover bhi milta hai."""

CLAUSES = """[p2-s4] Returns are not guaranteed. The illustrated rates of 4% and 8% p.a. are not upper or lower limits.
[p1-s3] Premium paying term: 10 years. Policy term: 15 years."""


def strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s)
    return s.strip()


def main() -> None:
    from openai import OpenAI, APIConnectionError, APIStatusError, AuthenticationError, NotFoundError

    st = get_settings()
    try:
        base = st.require("evon_base_url")
        key = st.require("evon_api_key").get_secret_value()
    except RuntimeError as e:
        sys.exit(str(e))
    client = OpenAI(base_url=base, api_key=key, timeout=120)
    model = st.evon_model

    def call(messages, thinking: bool, max_tokens: int):
        t0 = time.perf_counter()
        r = client.chat.completions.create(
            model=model, messages=messages, temperature=0.6, top_p=0.95, max_tokens=max_tokens,
            extra_body={"chat_template_kwargs": {"enable_thinking": thinking}},
        )
        return r, time.perf_counter() - t0

    results = []
    try:
        # 1. non-reasoning, Devanagari
        r, dt = call([{"role": "user", "content":
                       "Reply in Hindi in Devanagari script: what is a free-look period in insurance?"}],
                     False, 256)
        out = r.choices[0].message.content or ""
        ok = bool(DEVANAGARI.search(out))
        print(f"--- test 1 (Hindi, thinking off) {dt:.2f}s, Devanagari={'yes' if ok else 'NO'}\n{out}\n")
        results.append(f"hindi {'pass' if ok else 'FAIL'} {dt:.1f}s")

        # 2. JSON extraction
        sys_p = ('You extract promises a salesperson made about a financial product. Return ONLY JSON: '
                 '{"claims":[{"quote":"<exact words from the transcript>","claim_en":"<one English sentence>",'
                 '"category":"<returns|guarantee|lock_in|premium_term|policy_term|charges|liquidity|tax|cover|other>",'
                 '"numbers":["..."]}]}')
        r, dt = call([{"role": "system", "content": sys_p},
                      {"role": "user", "content": f"TRANSCRIPT (hi-IN, code-mixed):\n{PITCH}"}], False, 2048)
        out = r.choices[0].message.content or ""
        try:
            claims = json.loads(strip_fences(out))["claims"]
            ok = isinstance(claims, list) and len(claims) > 0
        except (ValueError, KeyError, TypeError) as e:
            ok, claims = False, e
        print(f"--- test 2 (JSON extraction) {dt:.2f}s, parse={'pass' if ok else 'FAIL'}\n{out}\n")
        results.append(f"extract {'pass' if ok else 'FAIL'} {dt:.1f}s")

        # 3. reasoning verification
        sys_p = ('You compare one spoken promise with the official policy document. Return ONLY JSON: '
                 '{"verdict":"WRITTEN|CONTRADICTED|NOT_IN_WRITING","clause_id":"...","clause_quote":"exact words",'
                 '"explain_en":"...","explain_local":"... in Hindi, Devanagari script","ask_agent":"..."}')
        user = (f"PROMISE: Returns are guaranteed at a minimum of 12% a year.\n\nCLAUSES:\n{CLAUSES}")
        r, dt = call([{"role": "system", "content": sys_p}, {"role": "user", "content": user}], True, 4096)
        msg = r.choices[0].message
        out = msg.content or ""
        reasoning = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None) or ""
        try:
            verdict = json.loads(strip_fences(out)).get("verdict")
        except ValueError:
            verdict = None
        print(f"--- test 3 (verify, thinking on) {dt:.2f}s, verdict={verdict}, reasoning chars={len(reasoning)}\n{out}\n")
        results.append(f"verify verdict={verdict} {dt:.1f}s")
    except AuthenticationError as e:
        sys.exit(f"401 auth failed: EVON_API_KEY in .env doesn't match the --api-key on the server. ({e})")
    except NotFoundError as e:
        sys.exit(f"404: wrong model name ({model}) or EVON_BASE_URL missing /v1. ({e})")
    except APIConnectionError as e:
        sys.exit(f"cannot connect to {base}: is the GPU running and port 8000 exposed? ({e})")
    except APIStatusError as e:
        sys.exit(f"HTTP {e.status_code}: {e.message}")

    print("SUMMARY: Evon " + "; ".join(results))


if __name__ == "__main__":
    main()
