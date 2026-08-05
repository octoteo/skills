# Octoteo Skills

A public collection of reusable Agent Skills maintained by [octoteo](https://github.com/octoteo). Each installable skill is a self-contained directory at the repository root and can be validated, evaluated, packaged, and released independently.

## Skills

| Skill | Status | Description |
|---|---|---|
| [`wpf-development`](wpf-development/) | Beta | Build, modernize, review, and troubleshoot production WPF applications. The current default baseline is .NET 10 and C# 14. |

`wpf-development` is engineering-hardened for packaging, deterministic scripts, Linux validation, and real Windows WPF execution. It remains Beta until a non-synthetic paired model evaluation passes every stable-release threshold.

## Repository layout

```text
skills/
├── README.md
├── LICENSE
├── SECURITY.md
├── QUALITY.md
├── RELEASING.md
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
├── eval-results/
├── tests/
│   └── wpf-development/
├── tools/
└── .github/
```

Every direct child directory containing `SKILL.md` is treated as an installable skill. Evaluation specifications, public evidence, tests, repository tooling, and CI configuration remain outside skill directories and are never included in the installation package.

## WPF Development

The skill supports both greenfield and existing-codebase work:

- choose a compact, product, or modular-product architecture based on real constraints
- create .NET 10 WPF solution boundaries through a dry-run-first scaffold
- modernize existing WPF applications incrementally while preserving behavior
- apply MVVM, Generic Host, dependency injection, configuration, and logging deliberately
- diagnose XAML, binding, dispatcher, startup, shutdown, memory, and packaging problems
- improve testing, accessibility, localization, observability, deployment, updates, and rollback
- account for .NET 10 WPF and C# 14 capabilities and compatibility changes
- handle explicit WPF and Windows Forms interoperability boundaries without treating WinForms-only work as WPF

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
- a 25-case routing and capability suite with 18 positive and 7 negative scenarios
- blind A/B judging, 0–2 rubric scoring, paired bootstrap confidence intervals, and an exact sign test
- a release checker that rejects synthetic, failing, missing, or package-mismatched stable evidence
- full-commit SHA pinning for GitHub Actions
- release SHA-256 assets and GitHub build-provenance attestation

See [`QUALITY.md`](QUALITY.md), [`SECURITY.md`](SECURITY.md), and [`RELEASING.md`](RELEASING.md).

## Run model-versus-baseline evaluation

Create paired response records:

```bash
python tools/evaluate_skill.py init \
  --run-id wpf-development-2026-08-05-01 \
  --baseline-model MODEL_NAME \
  --skilled-model MODEL_NAME \
  --output eval-runs/wpf-development-2026-08-05-01
```

After collecting responses, create blinded judging materials:

```bash
python tools/evaluate_skill.py blind \
  --responses eval-runs/wpf-development-2026-08-05-01/responses.jsonl \
  --output eval-runs/wpf-development-2026-08-05-01/judging \
  --seed 0
```

After judging, generate release evidence:

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

The evaluator measures activation recall, negative specificity, routing accuracy, baseline and skilled rubric means, paired improvement, a 95% bootstrap delta interval, win/tie/loss rate, exact one-sided sign-test significance, and critical failures. Synthetic fixtures always fail the stable-release gate.

See [`evals/wpf-development/README.md`](evals/wpf-development/README.md) for the complete protocol.

## Release convention

Use per-skill tags so this repository can host multiple independently versioned skills:

```text
wpf-development-v0.9.0-beta.1
wpf-development-v1.0.0
```

Prerelease tags may publish without completed model evidence and are marked as GitHub prereleases. Stable tags are blocked unless a sanitized, non-synthetic, passing evaluation summary exists and matches the newly built package SHA-256.

Validate a future tag locally:

```bash
python tools/check_release.py \
  --tag wpf-development-v1.0.0 \
  --manifest .artifacts/wpf-development/manifest.json \
  --results-root eval-results
```

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
