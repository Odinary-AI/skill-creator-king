# Codex target profile

Read only when `facts.profile` is `codex`. The runtime host does not select the
target profile: `auto` selects Codex only when a local `agents/openai.yaml` entry
exists; explicit `codex` also covers Skills without this optional file. Generic
and WorkBuddy targets use the common registry without these two items, which both
read that file.

All evidence reading follows the shared scan gate, including metadata. Unknown
metadata extensions are not invalid merely because the validator ignores them.
Do not infer host acceptance from these bounded checks. One causal issue gets
one primary finding; cross-reference overlapping common items rather than
counting it again. Do not judge host-owned runtime behavior without evidence.

Trigger wording belongs to `SCK-L02`, and implicit-invocation permission to
`SCK-L06`; this profile does not restate them under a second ID.

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

## SCK-C02 Codex tool declarations match required capabilities

- Type: required when the workflow requires Codex tools.
- Owner: LLM.
- Inspect: compare required tools with metadata declarations and unavailable-tool
  branches. A missing, contradictory, or unusable required declaration is a gap
  only when the target's host contract requires it; host-provided tools do not
  automatically need duplicate declarations. C01 owns invalid field types.
- Not assessed: unavailable external host/tool contract; do not call the tool
  or authenticate merely to check availability.
- Minimum change: align the declared dependency or add its bounded unavailable path.
