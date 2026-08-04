# Octoteo Skills

A public collection of reusable Agent Skills maintained by [octoteo](https://github.com/octoteo). Each skill is a self-contained directory at the repository root and can be validated, packaged, and released independently.

## Skills

| Skill | Status | Description |
|---|---|---|
| [`wpf-development`](wpf-development/) | Active | Build, modernize, review, and troubleshoot production WPF applications. The current default baseline is .NET 10 and C# 14. |

## Repository layout

```text
skills/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── wpf-development/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   ├── references/
│   ├── scripts/
│   └── assets/
├── tests/
│   └── wpf-development/
├── tools/
└── .github/workflows/
```

Every direct child directory containing `SKILL.md` is treated as an installable skill. Shared repository tooling and tests stay outside skill directories so they are not included in packaged skills.

## WPF Development

The first skill supports both greenfield and existing-codebase work:

- create appropriately sized WPF solution structures
- modernize existing WPF applications incrementally
- apply MVVM, Generic Host, dependency injection, configuration, and logging
- diagnose XAML, binding, dispatcher, startup, shutdown, and packaging problems
- improve testing, accessibility, localization, observability, deployment, updates, and rollback
- account for .NET 10 WPF and C# 14 behavior and compatibility changes

The skill name is intentionally version-neutral. .NET 10 is the current implementation baseline and can be advanced later without changing the skill identity or install path.

## Install in ChatGPT

1. Open this repository's **Releases** page.
2. Download the `skill.zip` asset from the release you want.
3. In ChatGPT, open **Plugins**, then **Skills**.
4. Select **Create** and upload `skill.zip`.
5. Review the scan result before enabling the skill.

A source checkout can also be packaged locally:

```bash
python tools/package_skill.py wpf-development .artifacts/wpf-development
```

The generated file is `.artifacts/wpf-development/skill.zip`. Build artifacts are intentionally ignored by Git and are not stored in the source tree.

## Validate

```bash
python tools/validate_repository.py
python tools/run_tests.py
python tools/package_skill.py wpf-development .artifacts/wpf-development
```

GitHub Actions performs the same structural validation, tests the deterministic scripts, and creates an ephemeral package artifact. Tagged releases attach `skill.zip` without committing the archive to the repository.

## Add another skill

Create a new root-level directory with this minimum structure:

```text
new-skill/
├── SKILL.md
└── agents/
    └── openai.yaml
```

Add only the references, scripts, and assets that materially improve execution. Add deterministic script tests under `tests/new-skill/`, then update the skill index above.

## License

MIT. See [`LICENSE`](LICENSE).
