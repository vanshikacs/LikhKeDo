"""Score the pipeline against demo/answer_key.json (skips STT; uses the pitch text). Needs Evon running.

Usage: backend/.venv/Scripts/python scripts/eval_answer_key.py [--only hi_hinglish] [--rules]
  default: Evon as configured (EVON_PROVIDER vllm | llamacpp) -> demo/eval_results.{json,md}
  --rules: mode B "Rules check - no AI model" (runs offline)   -> demo/eval_rules.{json,md}
  --from-audio: transcribe demo/pitches/<slug>.wav with Prisma first (real STT; cached after the first run)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import db  # noqa: E402
from app.evon import EvonClient, EvonUnavailable, engine_info  # noqa: E402
from app.ingest import parse_pdf  # noqa: E402
from app.pipeline import fuzzy_in, run_pipeline  # noqa: E402
from app.rules import LABEL as RULES_LABEL, run_rules  # noqa: E402

VERDICTS = ["WRITTEN", "CONTRADICTED", "NOT_IN_WRITING"]
MATCH = 70  # fuzzy match between a predicted quote and the answer-key quote hint


def match(expected: list[dict], predicted: list) -> list[tuple[dict, object | None]]:
    """Greedy one-to-one matching of answer-key promises to predicted claims by quote similarity."""
    pairs, used = [], set()
    for e in expected:
        best, best_s = None, 0.0
        for i, p in enumerate(predicted):
            if i in used:
                continue
            s = max(fuzzy_in(e["quote_hint"], p.quote), fuzzy_in(p.quote, e["quote_hint"]))
            if s > best_s:
                best, best_s = i, s
        if best is not None and best_s >= MATCH:
            used.add(best)
            pairs.append((e, predicted[best]))
        else:
            pairs.append((e, None))
    return pairs


class _Saved:
    """A saved claim (dict from the results JSON) with attribute access, so match() can re-pair it."""
    def __init__(self, d: dict):
        self.__dict__.update(d)


def extra_metrics(key: dict, report: dict) -> tuple[dict, list[str]]:
    """Per-language accuracy, and for correct WRITTEN/CONTRADICTED verdicts whether the cited clause is the
    answer key's clause. Recomputed from the saved claims, so it is reproducible without the model."""
    by_slug = {p["slug"]: p for p in key["pitches"]}
    langs: dict[str, list[int]] = {}
    clause_ok = clause_n = 0
    wrong_clause = []
    for rp in report["pitches"]:
        kp = by_slug[rp["slug"]]
        pairs = match(kp["promises"], [_Saved(c) for c in rp["claims"]])
        lang = kp["lang"] + (" (held-out)" if kp.get("eval_only") else "")
        got = langs.setdefault(lang, [0, 0])
        for e, c in pairs:
            ok = c is not None and c.verdict == e["expected_verdict"]
            got[0] += ok
            got[1] += 1
            if ok and c.verdict in ("WRITTEN", "CONTRADICTED") and e.get("expected_clause_id"):
                clause_n += 1
                if c.clause_id == e["expected_clause_id"]:
                    clause_ok += 1
                else:
                    wrong_clause.append(f"{rp['slug']} {e['id']}: cited {c.clause_id}, key {e['expected_clause_id']}")
    m = {"by_language": {k: {"correct": v[0], "total": v[1]} for k, v in langs.items()},
         "clause_match": {"correct": clause_ok, "total": clause_n, "mismatches": wrong_clause}}
    md = ["", "| Language | Correct |", "| --- | --- |"]
    md += [f"| {k} | {v[0]}/{v[1]} |" for k, v in langs.items()]
    md += ["", f"Cited clause = answer key's clause, for correct *Written* / *Different on paper* verdicts: "
           f"**{clause_ok}/{clause_n}**" + (f" (other clause: {'; '.join(wrong_clause)})" if wrong_clause else "") + "."]
    return m, md


def rescore(path: Path) -> None:
    key = json.loads((ROOT / "demo/answer_key.json").read_text(encoding="utf-8"))
    report = json.loads(path.read_text(encoding="utf-8"))
    m, md = extra_metrics(key, report)
    total = sum(v["total"] for v in m["by_language"].values())
    correct = sum(v["correct"] for v in m["by_language"].values())
    print(f"{path.name}: {correct}/{total} correct")
    print("\n".join(md))


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--rules", action="store_true")
    ap.add_argument("--from-audio", action="store_true")
    ap.add_argument("--rescore", type=Path, help="recompute the language/clause tables from a saved results JSON")
    a = ap.parse_args()
    if a.rescore:
        rescore(a.rescore)
        return
    engine = RULES_LABEL if a.rules else engine_info()["label"]
    out_name = ("eval_rules" if a.rules else "eval_results") + ("_stt" if a.from_audio else "")
    db.init_db()
    key = json.loads((ROOT / "demo/answer_key.json").read_text(encoding="utf-8"))
    clauses = parse_pdf((ROOT / key["document"]).read_bytes())

    confusion = {e: {p: 0 for p in VERDICTS + ["MISSED"]} for e in VERDICTS}
    report = {"pitches": [], "created": time.strftime("%Y-%m-%d %H:%M"), "engine": None}
    disagreements = []
    for pitch in key["pitches"]:
        if a.only and pitch["slug"] != a.only:
            continue
        text = (ROOT / pitch["file"]).read_text(encoding="utf-8")
        if a.from_audio:
            from app import gnani
            from app.langs import get_lang
            wav = ROOT / "demo" / "pitches" / f"{pitch['slug']}.wav"
            tr = await gnani.get_client().transcribe_rest(wav.read_bytes(), wav.name, get_lang(pitch["lang"]).prisma,
                                                          keyterms=gnani.FINANCE_TERMS)
            text = tr.text
            print(f"{pitch['slug']}: Prisma {tr.request_ids}{' (cache)' if tr.cached else ''}")
        t0 = time.perf_counter()
        try:
            res = (run_rules(text, clauses, pitch["lang"]) if a.rules
                   else await run_pipeline(text, clauses, pitch["lang"], EvonClient()))
        except EvonUnavailable as e:
            sys.exit(f"Evon unavailable: {e}")
        secs = time.perf_counter() - t0
        pairs = match(pitch["promises"], res.claims)
        correct = 0
        for e, p in pairs:
            got = p.verdict if p else "MISSED"
            confusion[e["expected_verdict"]][got] += 1
            ok = got == e["expected_verdict"]
            correct += ok
            if not ok:
                disagreements.append({"pitch": pitch["slug"], "id": e["id"], "expected": e["expected_verdict"],
                                      "got": got, "quote_expected": e["quote_hint"],
                                      "quote_got": p.quote if p else None,
                                      "clause_expected": e["expected_clause_id"],
                                      "clause_got": p.clause_id if p else None,
                                      "clause_quote": p.clause_quote if p else None,
                                      "reason": p.reason if p else None})
        extra = len(res.claims) - sum(1 for _, p in pairs if p)
        report["pitches"].append({"slug": pitch["slug"], "correct": correct, "total": len(pairs),
                                  "extra_claims": extra, "seconds": round(secs, 1),
                                  "claims": [asdict(c) for c in res.claims], "summary": res.summary,
                                  "trace": res.trace})
        print(f"{pitch['slug']}: {correct}/{len(pairs)} correct, {extra} extra claims, {secs:.1f}s")

    print("\nConfusion (rows = expected, cols = predicted):")
    print(f"{'':16}" + "".join(f"{c:>16}" for c in VERDICTS + ["MISSED"]))
    for e in VERDICTS:
        print(f"{e:16}" + "".join(f"{confusion[e][c]:>16}" for c in VERDICTS + ["MISSED"]))
    metrics = {}
    for v in VERDICTS:
        tp = confusion[v][v]
        pred = sum(confusion[e][v] for e in VERDICTS)
        actual = sum(confusion[v].values())
        metrics[v] = {"precision": round(tp / pred, 3) if pred else None,
                      "recall": round(tp / actual, 3) if actual else None}
        print(f"{v}: precision={metrics[v]['precision']} recall={metrics[v]['recall']}")
    for d in disagreements:
        print(f"\n[{d['pitch']} {d['id']}] expected {d['expected']} got {d['got']}\n  said: {d['quote_got']}\n"
              f"  clause {d['clause_got']}: {d['clause_quote']}\n  reason: {d['reason']}")

    extra, extra_md = extra_metrics(key, report)
    report.update(engine=engine, confusion=confusion, metrics=metrics, disagreements=disagreements, **extra)
    (ROOT / f"demo/{out_name}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# Answer-key evaluation", "", f"Run: {report['created']}. "
          f"fictional CIS. Engine: {engine}. Input: "
          f"{'Prisma v3.0 transcript of the Timbre pitch audio' if a.from_audio else 'pitch text (no STT)'}.", "",
          "| Pitch | Correct | Extra claims | Time (s) |", "| --- | --- | --- | --- |"]
    md += [f"| {p['slug']} | {p['correct']}/{p['total']} | {p['extra_claims']} | {p['seconds']} |"
           for p in report["pitches"]]
    md += ["", "| Expected \\ Predicted | " + " | ".join(VERDICTS + ["MISSED"]) + " |",
           "| --- |" + " --- |" * 4]
    md += [f"| {e} | " + " | ".join(str(confusion[e][c]) for c in VERDICTS + ["MISSED"]) + " |" for e in VERDICTS]
    md += ["", "| Verdict | Precision | Recall |", "| --- | --- | --- |"]
    md += [f"| {v} | {metrics[v]['precision']} | {metrics[v]['recall']} |" for v in VERDICTS]
    md += extra_md
    (ROOT / f"demo/{out_name}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\nwrote demo/{out_name}.json and demo/{out_name}.md")


if __name__ == "__main__":
    asyncio.run(main())
