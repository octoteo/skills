# Releasing a skill

This repository uses independently versioned per-skill tags.

## Tag format

```text
<skill>-v<major>.<minor>.<patch>
<skill>-v<major>.<minor>.<patch>-<prerelease>
```

Examples:

```text
wpf-development-v0.9.0-beta.1
wpf-development-v1.0.0
```

## Prerelease procedure

A prerelease is appropriate while real model-versus-baseline evidence is incomplete.

1. Validate and test the repository.
2. Build the deterministic package.
3. Optionally run synthetic evaluator self-tests, but do not present them as model evidence.
4. Create a prerelease tag.
5. Confirm the release workflow publishes checksums, manifest, and provenance.

The release workflow marks tags containing a prerelease suffix as GitHub prereleases.

## Stable release procedure

### 1. Freeze the skill package

```bash
python tools/validate_repository.py
python tools/run_tests.py
python tools/package_skill.py wpf-development .artifacts/wpf-development
```

Do not edit `wpf-development/` after collecting evaluation responses unless the entire evaluation is repeated.

### 2. Run paired blind evaluation

Follow [`evals/wpf-development/README.md`](evals/wpf-development/README.md). Produce a non-synthetic passing result under:

```text
eval-results/wpf-development/<version>/
├── summary.json
└── report.md
```

The summary must reference the exact `.artifacts/wpf-development/skill.zip` SHA-256.

### 3. Review public evidence

Before committing evaluation evidence:

- remove confidential repository paths and proprietary source excerpts
- verify no credentials, personal data, or private prompts are included
- confirm the blind key and raw responses remain outside the public result directory
- confirm `evaluation.synthetic` is `false`
- confirm `release_gate.passed` is `true`

### 4. Validate the future tag

```bash
python tools/check_release.py \
  --tag wpf-development-v1.0.0 \
  --manifest .artifacts/wpf-development/manifest.json \
  --results-root eval-results
```

### 5. Commit and tag

Commit the sanitized evidence and any final release notes. Tag that commit only after CI passes.

```bash
git tag wpf-development-v1.0.0
git push origin wpf-development-v1.0.0
```

The release workflow rebuilds the package, verifies the stable evidence against the new package hash, generates provenance, and uploads the package, checksum, manifest, and evaluation report.

## Stable release blockers

Do not create a stable tag when:

- any routing or capability threshold fails
- a skilled response has a critical failure
- evidence is synthetic or incomplete
- the package hash differs from the evaluated package
- the skill changed after response collection
- Windows CI has not passed
- public evaluation files contain confidential data
