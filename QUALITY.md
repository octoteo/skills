# Quality gates

A release is eligible for publication only when every applicable gate passes against the exact package being released.

## Structural gates

- Every installable skill is a root-level directory containing `SKILL.md`.
- The frontmatter name matches the directory and contains only `name` and `description`.
- `agents/openai.yaml` contains display metadata and all referenced icons exist.
- Every local path referenced by `SKILL.md` exists inside the skill directory.
- No symbolic link, hidden file, credential-like file, secret-like content, path collision, generated cache, or oversized file is packaged.

## Deterministic tooling gates

- Repository unit tests pass on Linux and Windows.
- Running the packager twice against identical content produces the same `skill.zip` SHA-256.
- The package contains exactly one skill root and excludes repository tests and tooling.
- The package checksum and manifest match the generated archive.
- Evaluation and release tooling tests cover incomplete evidence, synthetic evidence, package mismatch, and stable-tag rejection.
- Repository inspection tests cover inherited MSBuild properties, central package versions, project-reference integrity, redacted secret findings, and architecture-tier planning.
- OpenAI collection tests cover dry-run safety, key handling, upload version receipts, rate-limit retry, package binding, paired-request controls, activation evidence, and resumability.
- Automated judge tests cover strict score-array schemas, A/B identity isolation, prompt-injection resistance instructions, no-tool/no-Skill requests, blind-key exclusion, per-case persistence, and resumability.

## WPF execution gates

- Compact, Product, and Modular scaffolds run on Windows with a .NET 10 SDK.
- Every generated solution restores, builds in Release configuration, and tests successfully.
- Every generated repository is inspected by the bundled WPF inspector in strict mode.
- Windows execution failures are not replaced by Linux-only claims.

## Skill behavior gates

The evaluation specification must include at least:

- 20 discriminating scenarios
- 12 expected-activation scenarios
- 5 expected-non-activation scenarios
- create, modernize, implement, review, troubleshoot, and negative-routing coverage
- 4 critical production scenarios
- 3 decision-oriented rubric items for each positive scenario

The current `wpf-development` suite contains 27 scenarios: 20 positive and 7 negative. It includes explicit security-boundary and industrial command-reconciliation cases.

A stable release must be evaluated through paired blind judging against the exact package SHA-256. All current thresholds must pass:

| Metric | Requirement |
|---|---:|
| Positive routing recall | at least 94% |
| Negative routing specificity | 100% |
| Overall routing accuracy | at least 96% |
| Skilled normalized rubric mean | at least 80% |
| Paired mean improvement | at least 10 percentage points |
| Skilled win rate among non-ties | at least 70% |
| One-sided exact sign-test p-value | at most 0.05 |
| Lower bound of paired 95% bootstrap delta interval | above 0 |
| Skilled critical failures | 0 |

Synthetic fixtures validate the evaluator only and always fail the stable-release gate.

## Automated collection gates

When the OpenAI API collector is used:

- The Skill upload receipt must identify an immutable hosted Skill version and match the package and content hashes in `manifest.json`.
- Baseline and skilled requests use the same prompt, model id, reasoning effort, output limit, hosted shell type, and fresh-container policy.
- The skilled request differs only by the mounted `skill_reference`.
- The prompt does not explicitly tell the model to use the Skill; routing remains observable.
- Skilled activation is inferred only from visible shell commands reading `SKILL.md` or named `wpf-development` references/scripts.
- Every activation inference retains the matching command as reviewable evidence.
- Each API response is persisted before the next request so an interrupted run can resume without silently regenerating earlier evidence.
- Raw API responses and receipts stay private and are not release evidence by themselves.
- A small ChatGPT product-surface check remains required before a stable release primarily intended for ChatGPT, because API hosted-shell evidence does not prove every product surface behaves identically.

## Automated judge gates

When the structured-output judge is used:

- The judge receives only `blind-pairs.jsonl` data and the incomplete judgment template; it has no blind-key parameter or input.
- The request mounts no Skill and exposes no shell, web, file, connector, or other tools.
- Strict JSON Schema output requires exactly one integer score from 0 to 2 per rubric item for A and B.
- Response texts are treated as untrusted quoted data; embedded role, scoring, tool, and output instructions must be ignored.
- The requested and returned judge model ids, response id, usage, and completion time are retained privately.
- Every completed judgment and raw judge response is persisted before the next request; interrupted judging can resume without replacing completed judgments.
- Automated judgments are manually audited for a representative sample and every critical, security, equipment, data-loss, rollback, or platform-boundary case.
- Material disagreement between independent judges requires blinded adjudication before the A/B key is revealed.

## Evidence handling gates

- Baseline and skilled responses use the same model family and comparable inference settings.
- The baseline does not have the Skill; the skilled configuration has the exact `wpf-development` package version mounted.
- Skilled activation is recorded for every scenario.
- Responses are preserved before judging.
- A/B identities remain hidden from the judge until scoring is complete.
- Every positive rubric item receives an integer score from 0 to 2 for both variants.
- Raw responses, hosted Skill receipts, shell transcripts, blind keys, and private judge notes are not published accidentally.
- The manual GitHub collection workflow uploads only passphrase-encrypted private evidence.
- Public evidence contains only sanitized `summary.json` and `report.md` files.

## Release gates

- GitHub Actions dependencies are pinned to full commit SHAs.
- Release assets include `skill.zip`, `skill.zip.sha256`, and `manifest.json`.
- Public releases generate GitHub artifact attestation for `skill.zip`.
- Prerelease tags may publish without model evidence but must be marked prerelease.
- Stable tags require a passing, non-synthetic evaluation summary whose package SHA-256 matches the newly built package.
- Release notes identify the source commit, package hash, evaluation runtime and model, validation performed, and any remaining manual validation.
