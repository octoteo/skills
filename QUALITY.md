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

## Evidence handling gates

- Baseline and skilled responses use the same model family and comparable inference settings.
- The baseline does not have the skill; the skilled configuration has `wpf-development` installed and available.
- Skilled activation is recorded for every scenario.
- Responses are preserved before judging.
- A/B identities remain hidden from the judge until scoring is complete.
- Every positive rubric item receives an integer score from 0 to 2 for both variants.
- Raw responses, blind keys, and private judge notes are not published accidentally.
- Public evidence contains only sanitized `summary.json` and `report.md` files.

## Release gates

- GitHub Actions dependencies are pinned to full commit SHAs.
- Release assets include `skill.zip`, `skill.zip.sha256`, and `manifest.json`.
- Public releases generate GitHub artifact attestation for `skill.zip`.
- Prerelease tags may publish without model evidence but must be marked prerelease.
- Stable tags require a passing, non-synthetic evaluation summary whose package SHA-256 matches the newly built package.
- Release notes identify the source commit, package hash, validation performed, and any remaining manual validation.
