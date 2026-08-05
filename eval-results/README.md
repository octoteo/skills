# Evaluation results

This directory stores sanitized, versioned evidence for stable skill releases.

```text
eval-results/<skill>/<version>/
├── summary.json
└── report.md
```

Raw responses, blind keys, private judge notes, and proprietary repository context must remain under ignored `eval-runs/` or another controlled location.

A committed `summary.json` is accepted only when:

- it was produced by `tools/evaluate_skill.py score`
- `evaluation.synthetic` is `false`
- every release threshold passed
- its package SHA-256 matches the deterministic package built by the release workflow
- the skill and semantic version match the stable release tag

Do not hand-edit a passing result. Re-run the scorer after any source, package, response, or judgment change.
