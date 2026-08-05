# Security Policy

## Supported versions

Security fixes are applied to the latest release of each skill and to the `main` branch. Pre-release artifacts may change without compatibility guarantees.

## Reporting a vulnerability

Do not open a public issue for suspected credential exposure, unsafe script behavior, archive path traversal, release tampering, evaluation-data disclosure, or another security-sensitive defect. Use GitHub's private vulnerability reporting for this repository when available.

Include:

- affected skill and version or commit
- reproduction steps
- expected and actual behavior
- impact and any known exploit conditions
- a minimal proof of concept that does not expose real secrets

## Skill safety model

The repository treats skill packages as executable instruction bundles:

- packaging fails on symbolic links, hidden files, credential-like filenames, secret-like content, oversized files, broken internal references, and invalid metadata
- scripts default to read-only or dry-run behavior when they can modify a target repository or incur external cost
- releases include a SHA-256 checksum, a manifest, and GitHub build provenance
- Windows-specific WPF execution is validated on a Windows runner
- uploaded hosted Skill versions are bound to the exact local package and content hashes before evaluation

Automated checks reduce risk but do not replace source review before installing or executing a skill.

## Evaluation credentials and private evidence

- `OPENAI_API_KEY` is accepted only through the environment. The evaluation CLI has no API-key argument and never writes the key to receipts, requests, responses, or reports.
- Optional `OPENAI_PROJECT_ID` and `OPENAI_ORG_ID` values are also read only from the environment.
- API operations require explicit `--execute`; dry runs do not open the network or create billable requests.
- `eval-runs/` is ignored because it contains labeled responses, raw API objects, hosted Skill ids, shell commands, blind keys, and judge notes.
- The manual GitHub evaluation workflow requires `EVAL_ARTIFACT_PASSPHRASE` and uploads only an AES-256-CBC/PBKDF2-encrypted archive. Never store the passphrase in repository variables, workflow inputs, issues, or artifacts.
- Decrypt evidence only on a trusted machine. Share only `blind-pairs.jsonl` with a judge and keep the labeled responses and blind key separate.
- The automated judge receives no blind key, mounts no Skill, and exposes no tools. A and B response bodies are treated as untrusted quoted data, not instructions.
- Strict structured output constrains the judge response shape but does not make model judgment infallible or eliminate prompt-injection risk; manually audit critical and surprising results.
- Public release evidence must be sanitized and limited to aggregate `summary.json` and `report.md` outputs.

OpenAI Skills can influence planning, tool use, and command execution. Review the exact package before uploading it to any hosted runtime and do not attach arbitrary untrusted Skills to an environment with sensitive data or network access.
