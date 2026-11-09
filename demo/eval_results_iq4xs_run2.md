# Answer-key evaluation — Evon IQ4_XS, run 2 (same code as the saved demo cases)

Run: 2026-11-09 17:32. fictional CIS. Engine: Evon v3.3 · community 4-bit GGUF (llama.cpp). Input: pitch text (no STT).

| Pitch | Correct | Extra claims | Time (s) |
| --- | --- | --- | --- |
| hi_hinglish | 5/6 | 0 | 46.8 |
| ta_tamil_english | 2/6 | 0 | 27.1 |
| mr_marathi | 3/6 | 0 | 32.8 |
| hi_hinglish_2 | 2/6 | 0 | 18.9 |
| en_english | 6/6 | 0 | 18.6 |

| Expected \ Predicted | WRITTEN | CONTRADICTED | NOT_IN_WRITING | MISSED |
| --- | --- | --- | --- | --- |
| WRITTEN | 5 | 4 | 1 | 0 |
| CONTRADICTED | 0 | 8 | 3 | 0 |
| NOT_IN_WRITING | 0 | 3 | 5 | 1 |

| Verdict | Precision | Recall |
| --- | --- | --- |
| WRITTEN | 1.0 | 0.5 |
| CONTRADICTED | 0.533 | 0.727 |
| NOT_IN_WRITING | 0.556 | 0.556 |

| Language | Correct |
| --- | --- |
| hi | 5/6 |
| ta | 2/6 |
| mr | 3/6 |
| hi (held-out) | 2/6 |
| en (held-out) | 6/6 |

Cited clause = answer key's clause, for correct *Written* / *Different on paper* verdicts: **12/13** (other clause: en_english en-3: cited p3-s2, key p3-s1).
