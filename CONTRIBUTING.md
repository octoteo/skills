# Contributing

Keep contributions focused, evidence-based, and verifiable.

## Repository conventions

- Place every installable skill directly under the repository root.
- Use a short, lowercase, kebab-case directory name that matches the `name` in `SKILL.md`.
- Keep `SKILL.md` as the control plane and move detailed guidance into one-level `references/` files.
- Put deterministic helpers inside the skill's `scripts/` directory and test them under `tests/<skill-name>/`.
- Keep shared validation and packaging utilities under `tools/`.
- Do not commit generated ZIP archives, build outputs, credentials, private environment details, or editor caches.

## Quality principles

- Prefer primary and official sources for technical compatibility claims.
- Avoid stale hardcoded dependency versions unless a version is part of the task's compatibility boundary.
- Preserve existing application behavior before architectural modernization.
- Document platform constraints explicitly; WPF execution and UI validation require Windows.
- Keep packaged skills below the platform upload limit.

## Validate locally

```bash
python tools/validate_repository.py
python tools/run_tests.py
python tools/package_skill.py wpf-development .artifacts/wpf-development
```

Test Windows-specific execution on a Windows machine with the supported .NET SDK before changing execution behavior.

## Pull requests

Keep each pull request scoped to one skill or one shared tooling improvement. Explain:

1. what changed
2. why the skill needs it
3. how the change was validated
4. any Windows-only validation still pending
