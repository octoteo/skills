# Octoteo Skills

A public collection of reusable Agent Skills maintained by [octoteo](https://github.com/octoteo). Each installable skill is a self-contained directory at the repository root and can be validated, evaluated, packaged, and released independently.

## Skills

| Skill | Status | Description |
|---|---|---|
| [`wpf-development`](wpf-development/) | Beta | Build, modernize, review, and troubleshoot production WPF applications. The current default baseline is .NET 10 and C# 14. |

`wpf-development` is engineering-hardened for deterministic packaging, repository analysis, three-tier scaffolding, Linux validation, and real Windows WPF execution. It remains Beta until a non-synthetic paired model evaluation passes every stable-release threshold.

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
├── evals/wpf-development/
├── eval-results/
├── tests/wpf-development/
├── tools/
└── .github/workflows/
```

Every direct child directory containing `SKILL.md` is treated as an installable skill. Evaluation specifications, private runs, public evidence, tests, repository tooling, and CI configuration remain outside skill directories and are never included in the installation package.

## WPF Development

The skill supports both greenfield and existing-codebase work:

- choose Compact, Product, or Modular Product architecture based on real constraints
- create each architecture tier through a dry-run-first .NET 10 scaffold
- inspect effective repository configuration from project files, `Directory.Build.props`, `Directory.Packages.props`, and `global.json`
- detect missing and cyclic project references, unresolved package versions, risky publish settings, and redacted secret findings
- modernize existing WPF applications incrementally while preserving behavior
- apply MVVM, Generic Host, dependency injection, configuration, and logging deliberately
- diagnose XAML, binding, dispatcher, startup, shutdown, memory, packaging, and project-graph problems
- review trust boundaries, local IPC, imported files, embedded web content, signed updates, secrets, and support-bundle privacy
- design PLC and device command lifecycles, idempotency, stale-state handling, reconnect reconciliation, recipes, and simulation boundaries
- improve testing, accessibility, localization, observability, deployment, updates, and rollback
- account for .NET 10 WPF and C# 14 capabilities and compatibility changes

The skill name is intentionally version-neutral. .NET 10 is the current implementation baseline and can advance later without changing the skill identity or install path.

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
- Linux repository tests and Windows jobs that execute, build, test, and inspect Compact, Product, and Modular WPF scaffolds
- a 27-case routing and capability suite with 20 positive and 7 negative scenarios
- paired OpenAI Responses API collection with an exact hosted Skill version and only the Skill attachment varied between baseline and skilled requests
- activation evidence derived from visible hosted-shell reads of `SKILL.md` or named Skill resources
- an optional independent structured-output judge that receives only blinded A/B data, mounts no Skill, and has no blind-key access
- blind A/B judging, 0–2 rubric scoring, paired bootstrap confidence intervals, and an exact sign test
- a release checker that rejects synthetic, failing, missing, or package-mismatched stable evidence
- encrypted private evidence in the optional manual GitHub workflow
- full-commit SHA pinning for GitHub Actions
- release SHA-256 assets and GitHub build-provenance attestation

See [`QUALITY.md`](QUALITY.md), [`SECURITY.md`](SECURITY.md), and [`RELEASING.md`](RELEASING.md).

## Run model-versus-baseline evaluation

The repository supports manual response capture and automated collection through the OpenAI Skills API plus Responses API hosted shell.

Preview a complete automated run without network access or cost:

```bash
python tools/openai_eval_collect.py collect \
  --receipt eval-runs/private/skill-receipt.json \
  --manifest .artifacts/wpf-development/manifest.json \
  --run-id wpf-development-plan \
  --output eval-runs/wpf-development-plan
```

A real run requires `OPENAI_API_KEY` in the environment and explicit `--execute`. Start with `--max-cases 2`, inspect the evidence, then run all 27 cases. The collector persists each successful request and supports `--resume`.

After collection, blind the labeled responses:

```bash
python tools/evaluate_skill.py blind \
  --responses eval-runs/wpf-development-2026-08-05-01/responses.jsonl \
  --output eval-runs/wpf-development-2026-08-05-01/judging \
  --seed 0
```

Optionally run the independent structured-output judge. It receives only blinded pairs and does not accept the blind key:

```bash
python tools/openai_eval_judge.py \
  --pairs eval-runs/wpf-development-2026-08-05-01/judging/blind-pairs.jsonl \
  --judgments eval-runs/wpf-development-2026-08-05-01/judging/judgments.jsonl \
  --model gpt-5.5-2026-04-23 \
  --reasoning-effort high \
  --execute
```

Audit critical and surprising judgments before generating release evidence:

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

See [`evals/wpf-development/README.md`](evals/wpf-development/README.md) and [`evals/wpf-development/openai-api-collection.md`](evals/wpf-development/openai-api-collection.md).

## Release convention

Use per-skill tags so this repository can host multiple independently versioned skills:

```text
wpf-development-v0.9.0-beta.1
wpf-development-v1.0.0
```

Prerelease tags may publish without completed model evidence and are marked as GitHub prereleases. Stable tags are blocked unless sanitized, non-synthetic, passing evaluation evidence exists and matches the newly built package SHA-256.

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
