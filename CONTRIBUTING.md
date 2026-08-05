# Contributing

Keep contributions focused, evidence-based, secure, and verifiable.

## Repository conventions

- Place every installable skill directly under the repository root.
- Use a short lowercase kebab-case directory name that matches the `name` in `SKILL.md`.
- Keep `SKILL.md` as the control plane and move detailed guidance into one-level `references/` files.
- Put deterministic helpers inside the skill's `scripts/` directory and test them under `tests/<skill-name>/`.
- Add routing and capability scenarios under `evals/<skill-name>/eval.yaml`.
- Keep shared validation and packaging utilities under `tools/`.
- Do not commit ZIP archives, generated manifests, raw model responses, blind keys, credentials, private environment details, caches, or editor state.

## Skill safety requirements

A script that can modify files must:

- default to read-only or dry-run behavior
- identify the exact directory it owns before writing
- reject ambiguous or non-empty destinations unless explicitly designed for incremental editing
- avoid deleting content it did not create
- report partial failure truthfully
- provide a bounded recovery or cleanup path

A skill package must not contain:

- symbolic links
- hidden files
- credential-like filenames or secret-like content
- generated caches
- broken internal references
- case-insensitive path collisions
- files larger than the repository limits

## Quality principles

- Encode decisions the baseline model commonly gets wrong; do not restate generic WPF advice.
- Prefer primary and official sources for compatibility claims.
- Avoid stale hardcoded package versions unless a version is part of the compatibility boundary.
- Preserve existing application behavior before architectural modernization.
- Document platform constraints explicitly; WPF execution and UI validation require Windows.
- Distinguish static review, successful build, automated tests, and manual UI validation.
- Keep packaged skills below the platform upload limit.

## Validate locally

```bash
python tools/validate_repository.py
python tools/run_tests.py
python tools/package_skill.py wpf-development .artifacts/wpf-development
```

Verify the archive checksum:

```bash
cd .artifacts/wpf-development
sha256sum --check skill.zip.sha256
```

On Windows, also execute the scaffold with a supported .NET 10 SDK and build/test the generated solution.

## Evaluation expectations

Every directly invokable skill needs an evaluation specification with:

- at least 20 discriminating scenarios
- at least 12 expected-activation scenarios
- at least 5 expected-non-activation scenarios
- coverage of every primary workflow declared in `SKILL.md`
- at least 4 critical production scenarios
- at least 3 decision-oriented rubric items for every positive scenario
- explicit routing and stable-release thresholds

Repository validation checks the specification. A stable release additionally requires paired baseline-versus-skilled response collection, blind A/B judging, a non-synthetic passing report, and a package SHA-256 match. Follow `evals/<skill-name>/README.md`.

## Pull requests

Keep each pull request scoped to one skill or one shared tooling improvement. Explain:

1. what changed
2. why the skill needs it
3. how the change was validated
4. any Windows-only or model-evaluation validation still pending
5. routing, packaging, execution, or compatibility risks
