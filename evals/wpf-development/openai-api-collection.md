# OpenAI API response collection

This procedure collects real paired responses using the OpenAI Skills API and the Responses API hosted shell. It controls the comparison so the only intended request difference is whether the exact hosted Skill version is mounted.

## Security and cost boundaries

- Keep `OPENAI_API_KEY` in an environment variable or a protected GitHub Actions secret. Never put it in a command, config file, issue, log, or evaluation record.
- API execution is opt-in. The collector is dry-run-only unless `--execute` is present.
- A complete 27-case run makes 54 Responses API requests plus one Skill upload. Start with `--max-cases 2` to verify access, model support, output quality, and cost.
- Raw responses, Skill receipts, shell commands, blind keys, and judge notes are private evidence under `eval-runs/` or an encrypted workflow artifact. Do not commit them.
- Reuse an existing hosted Skill id with `--skill-id` so a new immutable version is created instead of another Skill object.

## Build the exact package

```bash
python tools/validate_repository.py
python tools/run_tests.py
python tools/package_skill.py wpf-development .artifacts/wpf-development
```

The collector verifies that the upload receipt and later response collection match `.artifacts/wpf-development/manifest.json`.

## Preview without network access

```bash
python tools/openai_eval_collect.py upload \
  --package .artifacts/wpf-development/skill.zip \
  --manifest .artifacts/wpf-development/manifest.json \
  --output eval-runs/private/skill-receipt.json
```

```bash
python tools/openai_eval_collect.py collect \
  --receipt eval-runs/private/skill-receipt.json \
  --manifest .artifacts/wpf-development/manifest.json \
  --run-id wpf-development-smoke \
  --output eval-runs/wpf-development-smoke \
  --max-cases 2
```

These commands print plans only. They do not require a key and do not create response evidence.

## Upload a hosted Skill version

Set the key outside command history:

```bash
export OPENAI_API_KEY='set-this-in-your-shell-secret-store'
```

Create the first hosted Skill:

```bash
python tools/openai_eval_collect.py upload \
  --package .artifacts/wpf-development/skill.zip \
  --manifest .artifacts/wpf-development/manifest.json \
  --output eval-runs/private/skill-receipt.json \
  --execute
```

For a later package, upload an immutable version under an existing Skill id:

```bash
python tools/openai_eval_collect.py upload \
  --package .artifacts/wpf-development/skill.zip \
  --manifest .artifacts/wpf-development/manifest.json \
  --skill-id SKILL_ID \
  --output eval-runs/private/skill-receipt.json \
  --execute
```

The receipt records the hosted Skill id and version plus the exact package and content hashes. It contains no API key.

## Run a smoke collection

Use a model that supports both hosted shell and Skills. The default is the fixed `gpt-5.5-2026-04-23` snapshot to reduce model drift.

```bash
python tools/openai_eval_collect.py collect \
  --receipt eval-runs/private/skill-receipt.json \
  --manifest .artifacts/wpf-development/manifest.json \
  --run-id wpf-development-smoke-01 \
  --output eval-runs/wpf-development-smoke-01 \
  --model gpt-5.5-2026-04-23 \
  --reasoning-effort medium \
  --max-cases 2 \
  --execute
```

Inspect `run.json`, `responses.jsonl`, and the raw API objects before committing to a full run.

## Run or resume the complete suite

```bash
python tools/openai_eval_collect.py collect \
  --receipt eval-runs/private/skill-receipt.json \
  --manifest .artifacts/wpf-development/manifest.json \
  --run-id wpf-development-2026-08-05-01 \
  --output eval-runs/wpf-development-2026-08-05-01 \
  --model gpt-5.5-2026-04-23 \
  --reasoning-effort medium \
  --execute
```

The collector writes after every completed request. Resume an interrupted run without repeating successful requests:

```bash
python tools/openai_eval_collect.py collect \
  --receipt eval-runs/private/skill-receipt.json \
  --manifest .artifacts/wpf-development/manifest.json \
  --run-id wpf-development-2026-08-05-01 \
  --output eval-runs/wpf-development-2026-08-05-01 \
  --model gpt-5.5-2026-04-23 \
  --reasoning-effort medium \
  --resume \
  --execute
```

Do not change the model, reasoning effort, package receipt, or manifest when resuming the same run.

## Comparison controls

For every case, both variants receive:

- the same case prompt
- the same model id
- the same reasoning effort and output limit
- the same hosted shell tool with a fresh automatic container

Only the skilled request includes:

```json
{
  "type": "skill_reference",
  "skill_id": "...",
  "version": 1
}
```

The collector does not tell the model to use the Skill. This preserves routing measurement: once mounted, the model decides whether the Skill applies.

## Activation evidence

The OpenAI Skills runtime exposes Skill metadata to the model. When the model invokes a Skill, it reads `SKILL.md` and may read referenced resources. The collector marks `activated=true` only when visible hosted-shell commands show a read of `SKILL.md` or a named `wpf-development` reference/script.

Every inferred activation stores the matching shell command in `activation_evidence`. Review this field before scoring. If the platform changes how Skill reads are surfaced, update and revalidate the detector rather than silently treating missing evidence as activation.

## Blind, judge, and score

After a complete collection:

```bash
python tools/evaluate_skill.py blind \
  --responses eval-runs/wpf-development-2026-08-05-01/responses.jsonl \
  --output eval-runs/wpf-development-2026-08-05-01/judging \
  --seed 0
```

Give an independent judge only `blind-pairs.jsonl` and the judging protocol. Keep `blind-key.json`, `responses.jsonl`, the Skill receipt, and activation evidence hidden until judgments are complete.

The repository includes an optional structured-output judge. Preview it without network access:

```bash
python tools/openai_eval_judge.py \
  --pairs eval-runs/wpf-development-2026-08-05-01/judging/blind-pairs.jsonl \
  --judgments eval-runs/wpf-development-2026-08-05-01/judging/judgments.jsonl
```

Execute only after reviewing the blinded material:

```bash
python tools/openai_eval_judge.py \
  --pairs eval-runs/wpf-development-2026-08-05-01/judging/blind-pairs.jsonl \
  --judgments eval-runs/wpf-development-2026-08-05-01/judging/judgments.jsonl \
  --model gpt-5.5-2026-04-23 \
  --reasoning-effort high \
  --execute
```

The judge request mounts no Skill, exposes no shell or other tools, accepts no blind-key argument, and requires strict JSON Schema output. Response A and B are embedded as untrusted quoted data; the judge is instructed not to follow instructions contained inside either response. Every completed judgment and raw judge response is persisted before the next request, and `--resume` skips completed cases.

Automated judging is evidence, not final authority. Before using it for a stable release, manually audit a representative sample, every critical failure, low-confidence or surprising result, and any case that could affect security, physical equipment, data loss, rollback, or platform boundaries. Use a second blinded judge and adjudication when required by the judging protocol.

Then use the existing score command described in the main evaluation README.

## Protected GitHub workflow

The manually dispatched `Collect OpenAI Skill evaluation` workflow provides the same process without storing plaintext evidence as a public-repository artifact.

Configure repository secrets:

- `OPENAI_API_KEY`
- `EVAL_ARTIFACT_PASSPHRASE`
- optionally `OPENAI_PROJECT_ID`
- optionally `OPENAI_ORG_ID`

The workflow inputs separately record the generation model, judge model, reasoning settings, and candidate evidence version. Prefer fixed model snapshots for reproducibility.

The workflow validates and packages the exact Skill, uploads a hosted version, collects paired responses, creates blind material for complete runs, runs the structured-output blind judge, generates a private candidate score report, encrypts the private directory with AES-256-CBC and PBKDF2, and uploads only the encrypted archive for seven days. The judge step never receives `blind-key.json`; the scorer receives the key only after judging is complete.

Decrypt locally:

```bash
export EVAL_ARTIFACT_PASSPHRASE='the-same-secret-used-by-the-workflow'
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -in RUN_ID.tar.gz.enc \
  -out RUN_ID.tar.gz \
  -pass env:EVAL_ARTIFACT_PASSPHRASE
tar -xzf RUN_ID.tar.gz
```

Do not give the decrypted blind key or labeled responses to the judge.

## Interpretation boundary

This process produces evidence for the OpenAI Responses API hosted Skills runtime. It does not prove that every ChatGPT product surface, workspace policy, model alias, or future runtime behaves identically. Keep the runtime and exact model id in the public report, and perform a small ChatGPT product-surface check before a stable release intended primarily for ChatGPT users.
