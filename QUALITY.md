# Quality gates

A release is eligible for publication only when all applicable gates pass.

## Structural gates

- Every installable skill is a root-level directory containing `SKILL.md`.
- The frontmatter name matches the directory and contains only `name` and `description`.
- `agents/openai.yaml` contains display metadata and all referenced icons exist.
- Every local path referenced by `SKILL.md` exists inside the skill directory.
- No symbolic link, hidden file, credential-like file, secret-like content, path collision, or oversized file is packaged.

## Deterministic tooling gates

- Repository unit tests pass on Linux and Windows.
- Running the packager twice against identical content produces the same `skill.zip` SHA-256.
- The package contains exactly one skill root and excludes repository tests and tooling.
- The package checksum and manifest match the generated archive.

## WPF execution gates

- The scaffold runs on a Windows runner with a .NET 10 SDK.
- The generated solution restores, builds, and tests successfully.
- The generated repository is inspected by the bundled WPF inspector.

## Skill behavior gates

- Evaluation specifications include at least 15 discriminating scenarios.
- At least 10 scenarios expect activation and at least 5 verify non-activation.
- Scenarios cover creation, modernization, implementation, review, troubleshooting, and adjacent non-WPF frameworks.
- A stable `v1.0.0` release additionally requires completed model-versus-baseline evaluation results. The repository validates the evaluation specification but does not claim those external model runs occurred.

## Release gates

- GitHub Actions dependencies are pinned to full commit SHAs.
- Release assets include `skill.zip`, `skill.zip.sha256`, and `manifest.json`.
- Public releases generate GitHub artifact attestation for `skill.zip`.
- Release notes identify the source commit and any validation that remains manual.
