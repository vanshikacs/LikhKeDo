# Answer-key evaluation

Run: 2026-11-07 21:24. fictional CIS. Engine: Rules check — no AI model. Input: Prisma v3.0 transcript of the Timbre pitch audio.

| Pitch | Correct | Extra claims | Time (s) |
| --- | --- | --- | --- |
| hi_hinglish | 4/6 | 3 | 0.0 |
| ta_tamil_english | 5/6 | 3 | 0.0 |
| mr_marathi | 6/6 | 2 | 0.0 |
| hi_hinglish_2 | 1/6 | 1 | 0.0 |
| en_english | 0/6 | 0 | 0.0 |

| Expected \ Predicted | WRITTEN | CONTRADICTED | NOT_IN_WRITING | MISSED |
| --- | --- | --- | --- | --- |
| WRITTEN | 4 | 0 | 5 | 1 |
| CONTRADICTED | 0 | 5 | 1 | 5 |
| NOT_IN_WRITING | 0 | 0 | 7 | 2 |

| Verdict | Precision | Recall |
| --- | --- | --- |
| WRITTEN | 1.0 | 0.4 |
| CONTRADICTED | 1.0 | 0.455 |
| NOT_IN_WRITING | 0.538 | 0.778 |
