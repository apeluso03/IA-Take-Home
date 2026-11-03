# AI-Use Note

## Tools Used
- Claude Code

## Transcripts
1. According to task 1 in SPEC.md, build the evidence runner. Place it in 'evidence/' as 'run_evidence.py'

    - I built evidence/run_evidence.py. It works on the original redact.py. It can't run the fixed version yet, because src/redact.py is still just a placeholder comment.

    How to run it


    python3 evidence/run_evidence.py --target original
    python3 evidence/run_evidence.py --target fixed
    What it writes: one result file per input in evidence/results/<target>/, using the same file name as the input. Each result file has:

    A header: whether the output changed at all, how many [REDACTED] markers were added, and every output line that still contains rly_ in any case. That last list is only a pointer for your review, not a verdict: 08_text.txt mentions the rly_ prefix in ordinary text.
    A line-by-line comparison: each input line next to its output line, marked CHANGED or UNCHANGED. It also notes when the output has a different number of lines than the input.
    The full raw input and raw output at the bottom.
    It also writes a SUMMARY.md table covering all the inputs.

    How it keeps the spec's rules

    Input files aren't changed: it only reads them, and it checks each file's hash before and after the run. If any file changed, the run exits with an error.
    original/ is untouched: loading original/redact.py normally would create a __pycache__ folder inside it, so I turned that off. I checked afterwards and original/ still contains only SKILL.md and redact.py.
    No network calls, standard library only. It loads the chosen redact.py from its file path and calls its redact(text) function. If redact() raises an error on an input, the error is written into that input's result and the run carries on.
    Run against the original: it processed all 10 inputs, and the input files were unchanged. --target fixed currently stops with "src/redact.py does not define a redact(text) function", which is the expected result for now. The results are in evidence/results/original/ for you to read; I haven't drawn any conclusions from them.

    Nothing is committed: evidence/run_evidence.py and evidence/results/ are untracked. Do you want the results folder committed along with the script, or kept out of git until you've reviewed it?