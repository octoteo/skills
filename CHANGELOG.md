# Changelog

All notable repository and skill changes are documented here.

## Unreleased

### Added

- A provider-neutral paired evaluation tool that creates response templates, blinds A/B responses, validates judgments, and generates machine-readable and human-readable reports.
- A stable-release checker that rejects missing, synthetic, failing, or package-mismatched evaluation evidence.
- A 25-case WPF evaluation suite with 18 positive and 7 adjacent-framework or out-of-scope negative routing scenarios.
- Exact release thresholds for routing, rubric quality, paired improvement, bootstrap confidence, sign-test significance, and critical failures.
- Public evaluation evidence and release-procedure documentation.
- Deterministic skill packaging with SHA-256 checksum and file manifest.
- Validation for broken references, metadata, hidden files, credential-like files, secret-like content, symbolic links, case collisions, and size limits.
- A Windows CI job that executes the WPF scaffold and builds/tests the generated .NET 10 solution.
- Activation and capability evaluation scenarios covering create, modernize, implement, review, troubleshoot, and negative routing cases.
- Release provenance attestation and pinned GitHub Actions dependencies.
- Security policy, code ownership, Dependabot configuration, and production quality gates.

### Fixed

- Corrected the packaged skill identity from `dotnet10-wpf` to `wpf-development`.
- Corrected references from `references/dotnet10-wpf.md` to `references/dotnet10.md`.
