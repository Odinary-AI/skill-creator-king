# Codex target profile

Read only when `facts.profile` is `codex`. The runtime host does not select the
target profile: `auto` selects Codex only when a local `agents/openai.yaml` entry
exists; explicit `codex` also covers Skills without this optional file. Generic
and WorkBuddy targets use the common registry without these four items.

All evidence reading follows the shared scan gate, including metadata. Unknown
metadata extensions are not invalid merely because the validator ignores them.
Do not infer host acceptance from these bounded checks. One causal issue gets
one primary finding; cross-reference overlapping common items rather than
counting it again. Do not judge host-owned runtime behavior without evidence.

## SCK-C01 Supported interface metadata is well formed

- Type: required when metadata is present; otherwise not applicable.
- Owner: script facts plus LLM consistency review.
- Inspect: the validator checks YAML mapping shape, supported nonempty interface
  strings, exact Skill invocation in an optional default prompt, a true YAML
  boolean for `policy.allow_implicit_invocation`, and nonempty string `type` and
  `value` for each `dependencies.tools` entry. Missing optional fields are valid.
  The LLM compares the supported interface text with the target's actual purpose
  and behavior. Cite both sides for contradictions; no keyword-based matching.
- Not assessed: scan-withheld or unreadable metadata, unavailable parsing, or
  unavailable name needed by the default-prompt comparison.
- Minimum change: repair only the proven field mismatch; do not add optional
  metadata merely to satisfy a convention.

## SCK-C02 Codex trigger distinguishes adjacent requests

- Type: required.
- Owner: LLM.
- Inspect: description, documented uses and exclusions must identify when the
  Skill applies. Report a material vague, process-only or overbroad activation
  promise. Reuse L02 evidence and give a shared problem only one primary finding.
- Not assessed: missing product context needed to choose between plausible uses.
- Minimum change: state the activating user situation and nearest exclusion.

## SCK-C03 Invocation policy respects required user intent

- Type: required when activation policy and consequential actions interact.
- Owner: LLM.
- Inspect: compare implicit invocation policy (absent means host default) with
  authority and side effects. Implicit availability alone is not permission to
  execute: a safe read-only or confirmation-gated path can be valid. Report
  instructions that let implicit activation initiate consequential actions
  without the explicitly required intent. Reuse L06 evidence without duplication.
- Not assessed: required host activation behavior is not established by target
  evidence, or the policy could not be read; do not guess it true or false.
- Minimum change: preserve explicit intent before the action or bound the safe path.

## SCK-C04 Codex tool declarations match required capabilities

- Type: required when the workflow requires Codex tools.
- Owner: LLM.
- Inspect: compare required tools with metadata declarations and unavailable-tool
  branches. A missing, contradictory, or unusable required declaration is a gap
  only when the target's host contract requires it; host-provided tools do not
  automatically need duplicate declarations. C01 owns invalid field types.
- Not assessed: unavailable external host/tool contract; do not call the tool
  or authenticate merely to check availability.
- Minimum change: align the declared dependency or add its bounded unavailable path.
