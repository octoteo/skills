# Paired blind judging protocol

## Roles

Use three logically separate roles whenever possible:

- **Collector**: runs prompts in baseline and skilled configurations and records activation.
- **Blinder**: runs `tools/evaluate_skill.py blind` and protects `blind-key.json`.
- **Judge**: sees only `blind-pairs.jsonl` and writes `judgments.jsonl`.

One person may perform multiple roles only if the A/B identity remains hidden during judging.

## Configuration control

Keep these conditions equivalent between variants:

- model and model version
- inference mode and sampling settings
- tool and connector availability, except for the skill itself
- user prompt and attached repository context
- time budget and retry policy
- system or organization policies unrelated to the skill

Record any unavoidable difference in the run metadata and evaluation report.

## Response collection

For each scenario:

1. Start a fresh conversation or equivalent isolated context.
2. Run the baseline prompt with the skill unavailable or disabled.
3. Run the skilled prompt with `wpf-development` installed and available.
4. Record the full responses without polishing or selecting only favorable excerpts.
5. Record whether the skilled run visibly activated or loaded the skill.
6. Do not rerun only the weaker variant. Apply any retry policy symmetrically.

For repository scenarios, use the same immutable fixture or commit for both variants.

## Judging rules

Judge each rubric item independently:

- **0** when the requirement is absent, wrong, unsafe, fabricated, or unusable.
- **1** when it is directionally correct but incomplete, generic, weakly evidenced, or missing validation.
- **2** when it is correct, concrete, evidence-oriented, and operationally usable.

Do not reward verbosity, formatting, brand references, or keyword repetition. Reward decisions, correctness, constraints, validation, recovery, and truthful uncertainty.

Mark a critical failure when a response does any of the following:

- recommends an unsafe production action with material data, equipment, security, or rollback risk
- claims a build, test, Windows execution, or repository modification that did not occur
- removes the only working version before an update health check
- ignores a stated WPF, Windows, .NET version, migration, or interoperability boundary
- proposes destructive broad rewrites without a bounded migration or recovery path

## Reusable judge prompt

Use the following instruction with an independent judge model, followed by one record from `blind-pairs.jsonl`:

```text
Act as a strict, blind software-engineering evaluator. You are comparing Response A and Response B for the same prompt. You do not know which response used a skill and must not guess.

For each rubric item, assign an integer score from 0 to 2 to A and B:
0 = missing, incorrect, unsafe, or materially unusable
1 = partially correct but incomplete, generic, weakly justified, or insufficiently validated
2 = correct, specific, evidence-oriented, and operationally usable

Also mark critical_failure for each response only when it recommends a materially unsafe production action, fabricates validation, destroys rollback capability, or violates an explicit platform boundary.

Do not reward length, formatting, or keyword repetition. Base every score on concrete evidence in the response. Return only the completed judgment JSON object using the supplied case identifier and score-array lengths.
```

## Adjudication

When two judges disagree by more than one point on any rubric item or disagree on a critical failure:

1. keep both original judgments
2. ask a third blinded judge to adjudicate only the disputed items
3. record the adjudicated result and rationale
4. do not reveal the A/B key until adjudication is complete

## Evidence retention

Retain privately:

- exact prompts and repository fixture commit
- full raw responses
- model identifiers and configuration
- activation observations
- blind key
- original and adjudicated judgments
- scorer command and generated report

Publish only sanitized evidence suitable for the public repository.
