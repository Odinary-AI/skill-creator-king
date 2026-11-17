# Unified static report v2

Use one normalized result for Markdown, plain text, and JSON. This full agent report is
different from `validate_skill.py`'s deterministic output. Never turn script
`passed` into semantic completion. Use plain text when the host lacks Markdown
rendering or support is unknown. Honor explicit format and
concise/full requests. Concise omits only explanations for passed items, never
findings, uncertainty, limitations or the claim boundary. JSON always retains
the complete data. No numeric quality score is produced.

## Shape

The root object has:

- `schema`: `skill-creator-king.report.v2`;
- `completed`: true only after the bounded review completed (including honest
  unassessed dispositions); an operational error before valid inspection returns
  `{ "completed": false, "error": { "code": "...", "message": "..." } }`, no verdict;
- `target`, `read_scope`, `next_action`: nonempty strings. `read_scope` records
  actual target-relative files read and required unread files with reasons, for
  example `实际读取：SKILL.md、README.md；应读未读：references/rules.md（被扫描门阻止）`.
  Use `无` for an empty list; never infer actual reads from the eligible read list.
  If a pre-scan read occurred, `limitations` must state it and `read_scope` must
  name the files re-read after the scan; pre-scan content cannot support a finding.
  `next_action` carries the 1–3 ordered next steps, not a task list: sequence,
  trade-off and when to come back, without repeating finding-level fixes or IDs;
- `decisions`: optional array of at most three items, each
  `{ "id": <selected check ID>, "question": "...", "if_a": "...", "if_b": "...", "default": "..." }`.
  Use it only for a fact only the target owner can settle whose answer could change
  the verdict; a decision may not name a check already classified `pass`. Missing
  evidence and authorization questions do not belong here, and decisions never
  change `verdict` or `coverage`;
- `profile`: resolved `generic`, `workbuddy`, or `codex`; `operation`: create/check;
- `files_read`: optional array of target-relative files actually read. Required
  when rendering with `--facts`; it must be a subset of the validator's
  `facts.semantic_read_files` and is never inferred from that eligible list.
  `read_scope` remains the human-readable summary; this array is the machine list;
- `checks`: one entry per common registry ID, plus C01–C02 only for Codex;
- `limitations`, `changes`: string arrays (empty when none).

Successful JSON output retains all input fields and adds/recomputes:

- `verdict`: 无法判定 / 静态不合规 / 静态合规但有建议 / 静态合规;
- `coverage`: an object with integer counts for pass, gap, advisory,
  not_applicable and not_assessed; their sum is 24, or 26 for Codex;
- `claim_boundary`: the renderer’s complete boundary string.

These are derived output fields, not extra agent judgments. Feeding normalized
output back into the renderer recomputes them. Markdown also displays the input
profile and operation; no new schema fields are needed. A partial ID set is not
valid: include an evidence-backed not_assessed disposition for every unfinished
assessment, rather than omitting it.

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
  `reason` starts with `工具侧：` or `对象侧：` so the reader can tell whether the
  unknown comes from the checking tool or from the target. Unresolved applicable
  required checks are material. Scope-excluded runtime correctness belongs only in
  limitations, not in required unknowns. Applicability that only the target owner
  can settle belongs in `decisions`, not here.
- `observations`: `{ "original": <unchanged script issue>, "disposition": "cited contextual decision" }`.
  Preserve every script error, warning and not_assessed item. Context may resolve
  applicability or supply missing semantic evidence; it cannot rewrite the
  original observation. A proven required defect cannot be downgraded.

Resolve `required` for this operation and applicable role, not by copying a
registry label mechanically. S04 is true on create and false on check. L09 is
true when actual local dependencies apply (or their applicability remains
unresolved); for resource organization alone it is false. Under a mixed item,
each finding still uses gap for a confirmed required defect or advisory for an
organization suggestion. Assess the required part fully before declaring the
whole item passed; cite the role and applicability in reason. Unresolved
required assessments remain material; do not hide them by setting required=false.
S10 candidate disposition follows the registry's publishing/nonpublishing rule;
operation=create/check alone does not establish publishing intent.

For one fact and evidence boundary, emit a finding or an unassessed item, not
both. Independent known defects and unknowns may coexist under one check. Status
precedence is not_assessed > gap > advisory > pass; not_applicable has neither
findings nor unknowns. Required/advisory classification governs SCK verdict;
severity orders remediation, not a second verdict system. Cite target evidence
for semantic inferences and deduplicate by root cause, not by matching rule ID.

## Facts-aware checks

`render_report.py --facts <validator.json>` checks observations and citations
without reading the target:

- `checks[].observations` must match all original errors, warnings and not_assessed
  objects exactly, including counts; dispositions remain agent judgments;
- every `files_read` entry is in `facts.semantic_read_files`;
- a finding with `check_type: "semantic"` must cite a file in `files_read`;
- deterministic findings (missing targets, symlinks, credential hits) may cite
  paths that were never read or do not exist, so they are not checked this way.

Pass the complete same-scan validator result (including all three observation
arrays and `facts`), not bare facts. After edits use the new scan. Without `--facts`,
only schema validation runs. Warnings are not automatically upgraded to gaps.

## Rendering

[The renderer](../scripts/render_report.py) validates the result shape, requires
all selected-profile IDs exactly once, and computes `verdict`, `coverage` and
`claim_boundary`. It never reads or executes the target and cannot establish the
truth of supplied semantic judgments. The evidence remains the agent's duty.
The Markdown uses the [report layout](report.md#静态合规报告) for judgement fields
and places the audit trail under `2. 审核明细`.
Observations of the same check are merged into one counted line while JSON keeps
every original object. Follow the report contract for which fields are always
printed and which are omitted when empty.

```bash
python3 "<loaded-sck-directory>/scripts/render_report.py" "<assessed-report.json>" --format json
python3 "<loaded-sck-directory>/scripts/render_report.py" "<assessed-report.json>" --format markdown --verbosity concise --facts "<validator.json>"
```

For plain text, use `--format text` with the same options.

The agent can build and render this same shape in memory. Do not create a report
file unless the user requested one. If a file is requested, validate it with the
renderer and return plain JSON (no Markdown fences) when JSON was selected.
Invalid report input exits 2 with an operational error; valid rendering exits 0
regardless of target quality. Renderer success is not target success.

## Migration

`files_read` is optional and does not change the schema version; without
`--facts` the renderer keeps schema-only validation.

Schema v2 removes the former `SCK-C02` (trigger wording) and `SCK-C03`
(implicit-invocation permission); they now live inside `SCK-L02` and `SCK-L06`.
The former `SCK-C04` (tool declarations) is renumbered to `SCK-C02`. Codex
reports therefore carry 26 IDs, not 28. A stored v1 report is not accepted by the v2 renderer; re-render it
under the current registry rather than editing the ID list by hand.

This replaces the legacy checker report for new calls; it is deliberately a
separate schema. Do not map `blocked` to `无法判定`: the former meant a proven
blocker, the latter means insufficient assessment. No legacy consumer was found
in the bounded local migration inventory; no legacy adapter is shipped. Migrate
actual consumers explicitly if later found. The old static-inspection JSON is also
not the complete semantic report and is not accepted by this renderer.
