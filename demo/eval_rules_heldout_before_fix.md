# Answer-key evaluation

Run: 2026-11-07 21:23. fictional CIS. Engine: Rules check — no AI model. Input: pitch text (no STT).

| Pitch | Correct | Extra claims | Time (s) |
| --- | --- | --- | --- |
| hi_hinglish | 6/6 | 1 | 0.0 |
| ta_tamil_english | 6/6 | 1 | 0.0 |
| mr_marathi | 6/6 | 1 | 0.0 |
| hi_hinglish_2 | 1/6 | 0 | 0.0 |
| en_english | 1/6 | 0 | 0.0 |

| Expected \ Predicted | WRITTEN | CONTRADICTED | NOT_IN_WRITING | MISSED |
| --- | --- | --- | --- | --- |
| WRITTEN | 7 | 0 | 3 | 0 |
| CONTRADICTED | 1 | 6 | 2 | 2 |
| NOT_IN_WRITING | 0 | 0 | 7 | 2 |

| Verdict | Precision | Recall |
| --- | --- | --- |
| WRITTEN | 0.875 | 0.7 |
| CONTRADICTED | 1.0 | 0.545 |
| NOT_IN_WRITING | 0.583 | 0.778 |
