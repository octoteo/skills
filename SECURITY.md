# Security Policy

## Supported versions

Security fixes are applied to the latest release of each skill and to the `main` branch. Pre-release artifacts may change without compatibility guarantees.

## Reporting a vulnerability

Do not open a public issue for suspected credential exposure, unsafe script behavior, archive path traversal, release tampering, or another security-sensitive defect. Use GitHub's private vulnerability reporting for this repository when available.

Include:

- affected skill and version or commit
- reproduction steps
- expected and actual behavior
- impact and any known exploit conditions
- a minimal proof of concept that does not expose real secrets

## Skill safety model

The repository treats skill packages as executable instruction bundles:

- packaging fails on symbolic links, hidden files, credential-like filenames, secret-like content, oversized files, broken internal references, and invalid metadata
- scripts must default to read-only or dry-run behavior when they can modify a target repository
- releases include a SHA-256 checksum, a manifest, and GitHub build provenance
- Windows-specific WPF execution is validated on a Windows runner

Automated checks reduce risk but do not replace source review before installing a skill.
