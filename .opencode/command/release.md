---
description: Release gate - run privacy audit + full QA, and only if both pass, commit and push. Usage - /release [commit message hint]
agent: build
---

Release the current state of the terminal-CV project:

1. Launch the privacy-auditor subagent to scan the project and the staged changes.
   Abort the release on VERDICT: LEAK.
2. Launch the qa-tester subagent for the full QA pass. Abort on VERDICT: FAIL.
3. If both gates pass: review `git status` and `git diff`, stage only intended files,
   write a concise commit message in the repo's existing style
   (hint from user, may be empty: "$ARGUMENTS"), commit and push.
4. Report: gate verdicts, commit hash, pushed branch.

If any gate fails, stop, do not commit, and summarize exactly what must be fixed and which
agent should fix it (content-editor for config.json text, ui-engineer for template/build code,
pdf-publisher for the PDF).
