# Changelog

All notable repository and skill changes are documented here.

## Unreleased

### Added

- Repository-aware WPF inspection that resolves unconditional `Directory.Build.props` values, central package versions, `global.json` SDK metadata, project-reference cycles, missing references, risky publish settings, and redacted plain-text secret findings.
- Compact, Product, and Modular compile-time WPF scaffold tiers with Release build/test validation and safer failure cleanup for pre-existing empty destinations.
- Dedicated security-engineering guidance for trust boundaries, secrets, IPC, embedded web content, import validation, code signing, updates, diagnostics, and privacy.
- Dedicated industrial and device-integration guidance for PLC and equipment command lifecycles, idempotency, stale-state handling, reconnect reconciliation, recipes, auditability, simulation, and hardware-in-the-loop validation.
- Security-boundary and unknown-device-command-state evaluation cases, increasing the suite to 27 scenarios.
- Windows CI coverage for every scaffold architecture tier.
- A provider-neutral paired evaluation tool that creates response templates, blinds A/B responses, validates judgments, and generates machine-readable and human-readable reports.
- A stable-release checker that rejects missing, synthetic, failing, or package-mismatched evaluation evidence.
- Exact release thresholds for routing, rubric quality, paired improvement, bootstrap confidence, sign-test significance, and critical failures.
- Public evaluation evidence and release-procedure documentation.
- Deterministic skill packaging with SHA-256 checksum and file manifest.
- Validation for broken references, metadata, hidden files, credential-like files, secret-like content, symbolic links, case collisions, and size limits.
- Release provenance attestation and pinned GitHub Actions dependencies.
- Security policy, code ownership, Dependabot configuration, and production quality gates.

### Fixed

- Corrected the packaged skill identity from `dotnet10-wpf` to `wpf-development`.
- Corrected references from `references/dotnet10-wpf.md` to `references/dotnet10.md`.
