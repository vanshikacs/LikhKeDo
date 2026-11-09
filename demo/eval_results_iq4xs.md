# Answer-key evaluation — Evon IQ4_XS (superseded: use Q4_K_M)

Run: 2026-11-09 14:39. fictional CIS. Engine: Evon v3.3 · community 4-bit GGUF (llama.cpp). Input: pitch text (no STT).

| Pitch | Correct | Extra claims | Time (s) |
| --- | --- | --- | --- |
| hi_hinglish | 3/6 | 0 | 31.4 |
| ta_tamil_english | 4/6 | 0 | 33.6 |
| mr_marathi | 3/6 | 0 | 32.1 |
| hi_hinglish_2 | 4/6 | 0 | 17.3 |
| en_english | 6/6 | 0 | 23.5 |

| Expected \ Predicted | WRITTEN | CONTRADICTED | NOT_IN_WRITING | MISSED |
| --- | --- | --- | --- | --- |
| WRITTEN | 6 | 1 | 3 | 0 |
| CONTRADICTED | 0 | 9 | 2 | 0 |
| NOT_IN_WRITING | 0 | 1 | 5 | 3 |

| Verdict | Precision | Recall |
| --- | --- | --- |
| WRITTEN | 1.0 | 0.6 |
| CONTRADICTED | 0.818 | 0.818 |
| NOT_IN_WRITING | 0.5 | 0.556 |
