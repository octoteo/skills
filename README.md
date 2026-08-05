# Octoteo Skills

A public collection of reusable Agent Skills maintained by [octoteo](https://github.com/octoteo). Each installable skill is a self-contained directory at the repository root and can be validated, packaged, and released independently.

## Skills

| Skill | Status | Description |
|---|---|---|
| [`wpf-development`](wpf-development/) | Beta | Build, modernize, review, and troubleshoot production WPF applications. The current default baseline is .NET 10 and C# 14. |

`wpf-development` is engineering-hardened for packaging and deterministic script execution. It remains Beta until model-versus-baseline evaluation results are recorded for the scenarios under [`evals/wpf-development`](evals/wpf-development/).

## Repository layout

```text
skills/
├── README.md
├── LICENSE
├── SECURITY.md
├── QUALITY.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── wpf-development/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   ├── references/
│   ├── scripts/
│   └── assets/
├── evals/
│   └── wpf-development/
├── tests/
│   └── wpf-development/
├── tools/
└── .github/
```

Every direct child directory containing `SKILL.md` is treated as an installable skill. Evaluation specifications, tests, repository tooling, and CI configuration remain outside skill directories and are never included in the installation package.

## WPF Development

The skill supports both greenfield and existing-codebase work:

- choose a compact, product, or modular-product architecture based on real constraints
- create .NET 10 WPF solution boundaries through a dry-run-first scaffold
- modernize existing WPF applications incrementally while preserving behavior
- apply MVVM, Generic Host, dependency injection, configuration, and logging deliberately
- diagnose XAML, binding, dispatcher, startup, shutdown, memory, and packaging problems
- improve testing, accessibility, localization, observability, deployment, updates, and rollback
- account for .NET 10 WPF and C# 14 capabilities and compatibility changes

The skill name is intentionally version-neutral. .NET 10 is the current implementation baseline and can be advanced later without changing the skill identity or install path.

## Install in ChatGPT

Use a package generated from a release or a trusted checkout:

1. Download `skill.zip` and `skill.zip.sha256` from the matching GitHub Release.
2. Verify the checksum.
3. In ChatGPT, open **Plugins**, then **Skills**.
4. Select **Create** and upload `skill.zip`.
5. Review the platform scan result before enabling the skill.

Local package generation:

```bash
python tools/validate_repository.py
python tools/run_tests.py
python tools/package_skill.py wpf-development .artifacts/wpf-development
```

Outputs:

```text
.artifacts/wpf-development/
├── skill.zip
├── skill.zip.sha256
└── manifest.json
```

Build artifacts are ignored by Git and are not stored in the source tree.

## Quality and security controls

The repository enforces:

- exact skill-directory and frontmatter identity
- internal reference and icon existence
- rejection of hidden files, symbolic links, credential-like files, secret-like content, path collisions, caches, and oversized files
- deterministic ZIP timestamps, ordering, permissions, compression, checksum, and manifest
- Linux repository tests and a Windows job that executes the scaffold and builds/tests the generated .NET 10 WPF solution
- at least 15 routing and capability evaluation scenarios, including adjacent-framework non-activation cases
- full-commit SHA pinning for GitHub Actions
- release SHA-256 assets and GitHub build-provenance attestation

See [`QUALITY.md`](QUALITY.md) and [`SECURITY.md`](SECURITY.md).

## Release convention

Use per-skill tags so this repository can host multiple independently versioned skills:

```text
wpf-development-v0.8.0-beta.1
wpf-development-v1.0.0
```

A stable `v1.0.0` tag should be created only after the model evaluation scenarios have been run against both baseline and skilled configurations with a recorded passing result.

## Add another skill

Create a new root-level directory with this minimum structure:

```text
new-skill/
├── SKILL.md
└── agents/
    └── openai.yaml
```

Add only references, scripts, and assets that materially improve execution. Add deterministic tests under `tests/new-skill/`, an evaluation specification under `evals/new-skill/`, and update the skill index above.

## License

MIT. See [`LICENSE`](LICENSE).
