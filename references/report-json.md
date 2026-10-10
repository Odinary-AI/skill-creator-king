# Unified static report v1

Use one normalized result for both Markdown and JSON. This full agent report is
different from `validate_skill.py`'s deterministic output. Never turn script
`passed` into semantic completion. Render Markdown by default; honor JSON and
concise/full requests. Concise omits only explanations for passed items, never
findings, uncertainty, limitations or the claim boundary. JSON always retains
the complete data. No numeric quality score is produced.

## Shape

The root object has:

- `schema`: `skill-creator-king.report.v1`;
- `completed`: true only after the bounded review completed (including honest
  unassessed dispositions); an operational error before valid inspection returns
  `{ "completed": false, "error": { "code": "...", "message": "..." } }`, no verdict;
- `target`, `read_scope`, `next_action`: nonempty strings;
- `profile`: resolved `generic`, `workbuddy`, or `codex`; `operation`: create/check;
- `checks`: one entry per common registry ID, plus C01–C04 only for Codex;
- `limitations`, `changes`: string arrays (empty when none).

Each check has `id`, human-readable `title`, `status` (pass/gap/advisory/
not_applicable/not_assessed), boolean `required` from that item's applicability
and requirement, a cited `reason`, and three arrays:

- `findings`: each has `disposition` (gap/advisory), `severity`
  (blocker/major/minor/info), `check_type` (deterministic/semantic),
  `evidence_strength` (confirmed/inferred respectively), `code`, target-relative
  `file`, positive one-based `line` or null, `evidence`, `impact`, `recommendation`.
  Use blocker only with separately cited `unbounded_scope` and
  `irreversible_consequence`; otherwise keep the proven issue non-blocking.
- `unassessed`: `{ "reason": "...", "needed_evidence": "...", "material": true }`.
  Unresolved applicable required checks are material. Scope-excluded runtime
  correctness belongs only in limitations, not in required unknowns.
- `observations`: `{ "original": <unchanged script issue>, "disposition": "cited contextual decision" }`.
  Preserve every script error, warning and not_assessed item. Context may resolve
  applicability or supply missing semantic evidence; it cannot rewrite the
  original observation. A proven required defect cannot be downgraded.

For one fact and evidence boundary, emit a finding or an unassessed item, not
both. Independent known defects and unknowns may coexist under one check. Status
precedence is not_assessed > gap > advisory > pass; not_applicable has neither
findings nor unknowns. Required/advisory classification governs SCK verdict;
severity orders remediation, not a second verdict system. Cite target evidence
for semantic inferences and deduplicate by root cause, not by matching rule ID.

## Rendering

[The renderer](../scripts/render_report.py) validates the result shape, requires
all selected-profile IDs exactly once, and computes `verdict`, `coverage` and
`claim_boundary`. It never reads or executes the target and cannot establish the
truth of supplied semantic judgments. The evidence remains the agent's duty.

```bash
python3 "<loaded-sck-directory>/scripts/render_report.py" "<assessed-report.json>" --format json
python3 "<loaded-sck-directory>/scripts/render_report.py" "<assessed-report.json>" --format markdown --verbosity concise
```

The agent can build and render this same shape in memory. Do not create a report
file unless the user requested one. If a file is requested, validate it with the
renderer and return plain JSON (no Markdown fences) when JSON was selected.
Invalid report input exits 2 with an operational error; valid rendering exits 0
regardless of target quality. Renderer success is not target success.

## Migration

This replaces the checker report v2 for new calls; it is deliberately a new
schema. Do not map `blocked` to `无法判定`: the former meant a proven blocker,
the latter means insufficient assessment. No legacy consumer was found in the
bounded local migration inventory; no legacy adapter is shipped. Migrate actual
consumers explicitly if later found. The old static-inspection JSON is also not
the complete semantic report and is not accepted by this renderer.
