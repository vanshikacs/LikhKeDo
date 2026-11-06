"""Score the pipeline against demo/answer_key.json (skips STT; uses the pitch text). Needs Evon running.

Usage: backend/.venv/Scripts/python scripts/eval_answer_key.py [--only hi_hinglish]
Writes demo/eval_results.json and demo/eval_results.md.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import db  # noqa: E402
from app.evon import EvonClient, EvonUnavailable  # noqa: E402
from app.ingest import parse_pdf  # noqa: E402
from app.pipeline import fuzzy_in, run_pipeline  # noqa: E402

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


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    a = ap.parse_args()
    db.init_db()
    key = json.loads((ROOT / "demo/answer_key.json").read_text(encoding="utf-8"))
    clauses = parse_pdf((ROOT / key["document"]).read_bytes())

    confusion = {e: {p: 0 for p in VERDICTS + ["MISSED"]} for e in VERDICTS}
    report = {"pitches": [], "created": time.strftime("%Y-%m-%d %H:%M")}
    disagreements = []
    for pitch in key["pitches"]:
        if a.only and pitch["slug"] != a.only:
            continue
        text = (ROOT / pitch["file"]).read_text(encoding="utf-8")
        evon = EvonClient()
        t0 = time.perf_counter()
        try:
            res = await run_pipeline(text, clauses, pitch["lang"], evon)
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

    report.update(confusion=confusion, metrics=metrics, disagreements=disagreements)
    (ROOT / "demo/eval_results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# Answer-key evaluation", "", f"Run: {report['created']}. Pipeline on the pitch text (no STT), "
          "fictional CIS. Model: Evon v3.3 (self-hosted).", "",
          "| Pitch | Correct | Extra claims | Time (s) |", "| --- | --- | --- | --- |"]
    md += [f"| {p['slug']} | {p['correct']}/{p['total']} | {p['extra_claims']} | {p['seconds']} |"
           for p in report["pitches"]]
    md += ["", "| Expected \\ Predicted | " + " | ".join(VERDICTS + ["MISSED"]) + " |",
           "| --- |" + " --- |" * 4]
    md += [f"| {e} | " + " | ".join(str(confusion[e][c]) for c in VERDICTS + ["MISSED"]) + " |" for e in VERDICTS]
    md += ["", "| Verdict | Precision | Recall |", "| --- | --- | --- |"]
    md += [f"| {v} | {metrics[v]['precision']} | {metrics[v]['recall']} |" for v in VERDICTS]
    (ROOT / "demo/eval_results.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\nwrote demo/eval_results.json and demo/eval_results.md")


if __name__ == "__main__":
    asyncio.run(main())
