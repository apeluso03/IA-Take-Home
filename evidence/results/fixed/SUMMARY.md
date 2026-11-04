# Evidence results: fixed

redact.py: `src/redact.py`

| input | changed | markers added | lines still containing `rly_` |
|---|---|---|---|
| 01_plain.txt | yes | 1 | 0 |
| 02_hyphenated.txt | yes | 1 | 0 |
| 03_wrapped.txt | yes | 1 | 0 |
| 04_json.txt | yes | 1 | 0 |
| 05_uppercase.txt | yes | 1 | 0 |
| 06_auth.txt | yes | 1 | 0 |
| 07_long.txt | yes | 1 | 0 |
| 08_text.txt | **no** | 0 | 1 |
| 09_lookalike.txt | yes | 1 | 0 |
| 10_comment.txt | yes | 2 | 0 |
| 11_multiple.txt | yes | 2 | 0 |
| 12_wrapped2.txt | yes | 1 | 0 |

`rly_` count is a pointer for manual review only; it can be a legitimate
mention of the prefix. Read each result file before drawing conclusions.
