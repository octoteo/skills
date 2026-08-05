# WPF Development evaluation

This directory defines a reproducible paired evaluation for `wpf-development`. `eval.yaml` is JSON-compatible YAML and points to one JSON file per scenario under `cases/`, keeping review diffs small while allowing repository tooling to use only the Python standard library.

## What is measured

The evaluation separates two independent properties:

1. **Routing**: whether the installed skill activates for WPF work and remains inactive for adjacent non-WPF work.
2. **Capability**: whether the response produced with the skill is materially better than the response produced by the same model without the skill.

The current suite contains 25 scenarios:

- 18 expected-activation scenarios across create, modernize, implement, review, and troubleshoot work
- 7 expected-non-activation scenarios covering WinUI, MAUI, Avalonia, ASP.NET Core, WinForms-only, console-host, and .NET Framework-only work

## Evidence rules

A valid release evaluation must:

- use the same model family and comparable inference settings for baseline and skilled responses
- run baseline without the skill and skilled with `wpf-development` installed and available
- record whether the skilled configuration actually activated the skill
- preserve every response verbatim before judging
- blind the judge to baseline and skilled identities
- score every positive scenario against every rubric item on the 0–2 scale
- record critical failures separately from quality scores
- retain the private A/B key outside public judging materials
- identify the package SHA-256 being evaluated

Do not edit a response after seeing the paired alternative or the judge result. Do not count synthetic fixtures, examples, or evaluator self-tests as release evidence.

## 0–2 scoring scale

- **0**: Missing, incorrect, unsafe, or materially unusable.
- **1**: Partially correct but incomplete, weakly justified, or insufficiently validated.
- **2**: Correct, specific, evidence-oriented, and operationally usable.

A critical failure is a separate boolean. Use it when the response recommends a materially unsafe production action, fabricates validation, destroys rollback capability, or violates an explicit platform boundary.

## Run the evaluation

### 1. Build the exact package

```bash
python tools/validate_repository.py
python tools/run_tests.py
python tools/package_skill.py wpf-development .artifacts/wpf-development
```

Keep `.artifacts/wpf-development/manifest.json`; its archive hash binds the evaluation to the exact installable ZIP.

### 2. Create response-capture records

```bash
python tools/evaluate_skill.py init \
  --run-id wpf-development-2026-08-05-01 \
  --baseline-model MODEL_NAME \
  --skilled-model MODEL_NAME \
  --output eval-runs/wpf-development-2026-08-05-01
```

Run each prompt twice and fill `responses.jsonl`:

- `baseline`: skill unavailable or disabled
- `skilled`: skill installed and available

For every skilled record, set `activated` to `true` or `false`. For positive scenarios, preserve both full responses.

### 3. Create blinded judging materials

```bash
python tools/evaluate_skill.py blind \
  --responses eval-runs/wpf-development-2026-08-05-01/responses.jsonl \
  --output eval-runs/wpf-development-2026-08-05-01/judging \
  --seed 0
```

This creates:

- `blind-pairs.jsonl`: prompts, rubrics, and randomized A/B responses for the judge
- `judgments.jsonl`: empty score records to complete
- `blind-key.json`: private mapping from A/B to baseline/skilled

Keep `blind-key.json` hidden from the judge until scoring is complete.

### 4. Judge independently

For every positive case:

1. Score every rubric item for A and B from 0 to 2.
2. Mark `critical_failure` independently for A and B.
3. Optionally record an overall preference and concise evidence notes.
4. Do not infer which response used the skill.

See [`protocol.md`](protocol.md) for the complete judging protocol and reusable judge prompt.

### 5. Score and generate the report

```bash
python tools/evaluate_skill.py score \
  --responses eval-runs/wpf-development-2026-08-05-01/responses.jsonl \
  --key eval-runs/wpf-development-2026-08-05-01/judging/blind-key.json \
  --judgments eval-runs/wpf-development-2026-08-05-01/judging/judgments.jsonl \
  --manifest .artifacts/wpf-development/manifest.json \
  --version 1.0.0 \
  --source-commit COMMIT_SHA \
  --output eval-results/wpf-development/1.0.0 \
  --require-pass
```

The scorer produces:

- `summary.json`: machine-readable release evidence
- `report.md`: human-readable metrics and per-case comparison

The scorer computes routing recall, negative specificity, overall routing accuracy, normalized rubric means, paired mean delta, 95% bootstrap confidence interval, win/tie/loss counts, non-tie win rate, an exact one-sided sign test, and critical failures.

## Stable release thresholds

The authoritative thresholds live in `eval.yaml`. At present, a stable release requires all of the following:

- positive routing recall at least 94%
- negative routing specificity 100%
- overall routing accuracy at least 96%
- skilled normalized mean at least 80%
- paired mean improvement at least 10 percentage points
- skilled win rate at least 70% among non-ties
- one-sided exact sign-test p-value at most 0.05
- lower bound of the 95% paired bootstrap delta interval above zero
- zero critical failures in skilled responses

A synthetic run always fails the release gate even when its numerical scores exceed every threshold.

## Public and private artifacts

Raw response capture, blind keys, and judge work files belong under ignored `eval-runs/`. Commit only sanitized release evidence under:

```text
eval-results/wpf-development/<version>/
├── summary.json
└── report.md
```

Before committing evidence, remove confidential repository paths, user data, credentials, or proprietary source excerpts. The stable release workflow verifies that the summary package SHA-256 matches the newly built package.
