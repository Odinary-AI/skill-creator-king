# Common Skill Issues

Use this registry for creation self-checks and checks of existing Skills.
Reflect reuses the same criteria for affected contracts, with `check` as the
validator operation; its focused review does not establish whole-Skill compliance.
Apply only relevant items. Each item has one owner for its evidence: `script`
checks structural facts; `LLM` judges meaning and applicability with citations.
Use `not_assessed` when evidence is insufficient; absence of a script finding
does not prove an unassessed item passed.

The script extracts simple inline Markdown candidates outside common code spans
and ordinary fences; indented code is excluded by the bounded extractor.
It does not interpret every Markdown context. Ordinary fences may end at EOF;
this alone is not a syntax gap. Explicit quote/list fence starts leave a known
prefix and an unassessed remainder; retain that observation and use cited
context to resolve applicability and actual routes. `SCK-L09` checks all
actual local dependencies, including complex or reference-style routes and
missing resources that cannot appear in inventory. A syntax limitation is not
an `SCK-S06` gap. S06/S08 candidates require context: an example is not a
dependency and an orphan warning does not prove a resource is unused.

A second, narrower extractor serves S08 alone: inline code spans whose content
is path-shaped, and table-row cells (lines containing `|`, split on `|`) whose
token carries a path prefix, count as routes when they resolve to a bundled
regular file (relative to the declaring file first, then the Skill root). They
never produce missing-reference findings, never escape the Skill boundary, and
never enqueue further traversal; fenced code stays excluded. A bare filename
without a path prefix is ambiguous against same-named files and stays with L09,
as do arrow syntax, bare prose mentions, and command invocations inside fences
— resources declared only through them still surface as S08 candidates for L09
reconciliation.

## SCK-S01 Target is readable

- Type: required
- Applies when: every create or check run.
- Owner: script
- Pass: the selected directory and a regular UTF-8 `SKILL.md` are readable.
- Evidence: selected path and read result without exposing file content.
- Common gap: missing directory, missing root file, invalid encoding, or read failure.
- Minimum change: select a readable Skill directory or repair the affected file outside this check.

## SCK-S02 Frontmatter is usable

- Type: required
- Applies when: every create or check run.
- Owner: script
- Pass: PyYAML's safe loader parses a mapping containing nonempty `name` and `description` strings; description is at most 1,024 decoded characters and explicit mapping keys are unique.
- Evidence: field names and parser result.
- Common gap: missing delimiter, malformed value, duplicate explicit key, absent name or description, or an overlong description.
- Minimum change: repair only the malformed or missing frontmatter fields.

When present, `compatibility` must be a string of at most 500 characters. Other
optional or platform extension fields are not universally required. Platform
metadata is assessed only under its selected profile.

Count the decoded description before trimming whitespace, not UTF-8 bytes;
nonempty and length checks are separate. Do not truncate it automatically.
Duplicate keys in one mapping are gaps even with equal values; inherited merge
values and names in different mappings are not explicit duplicates. SafeLoader
still defines supported YAML types. This field baseline does not certify full
Agent Skills compatibility or host acceptance.

Missing PyYAML or a construct unsupported by its safe loader is `not_assessed`,
not a malformed-Skill finding. Preserve dependent unassessed items too; continue
independent filesystem checks. Do not use unsafe YAML constructors or implement
a fallback grammar with string stripping or extra regex cases.

Invalid scalar construction (such as an impossible date) is a syntax/value gap;
exceeding the safe parser's nesting capacity is `not_assessed`. Both preserve
independent reference checks. When content cannot be inspected, or frontmatter
fails, dependent checks that did not run are explicitly `not_assessed`; empty
resource lists alone are not proof that a reference check completed.

## SCK-S03 Name syntax is controlled

- Type: required
- Applies when: every create or check run.
- Owner: script
- Pass: `name` is at most 64 characters and uses lowercase letters, digits, and single hyphens.
- Evidence: the declared name.
- Common gap: uppercase, underscore, whitespace, repeated separator, or excessive length.
- Minimum change: choose one lowercase hyphenated name and update intentional references.

The deterministic spelling rule covers ASCII names. A non-ASCII name is
`not_assessed` unless a declared host contract resolves its validity; do not
promote an ASCII convention into a universal rejection.

## SCK-S04 Directory and name agree

- Type: required on create; advisory on check
- Applies when: the selected directory has a stable basename.
- Owner: script
- Pass: the directory basename equals the declared `name`.
- Evidence: both names, without other path details.
- Common gap: copied or renamed directory with stale frontmatter.
- Minimum change: align the new directory and name; for an existing Skill, confirm compatibility before renaming.

## SCK-S05 Canonical placeholders are resolved

- Type: required
- Applies when: the SCK canonical marker is a standalone body line outside code examples; unresolved marker applicability remains not assessed.
- Owner: script
- Pass: all metadata/body candidates have L04 dispositions, no actual unfinished slot remains, and no applicable candidate assessment is missing.
- Evidence: redacted candidate field/line locations and cited L04 context.
- Common gap: an actual unfinished `TODO`, `TBD`, or `{{slot}}`.
- Minimum change: fill necessary content or remove an unused optional slot.

Bilingual descriptions, author, and version are optional unless a stated host
or task contract needs them; their absence alone is neither a gap nor an
advisory. Standard name/description constraints remain under S02/S03.

`canonical.placeholder.candidate` in `warnings` is a lexical observation, not a
confirmed gap or advisory. The script owns the match; L04 owns intent and
applicability. Read each candidate's actual context: an unfinished slot is a
required S05 gap; a proven literal, example, or documented token is not
applicable to that candidate; unresolved meaning is `not_assessed`. Preserve
the observation and reason. Code examples still need this context review;
never delete legitimate TODO/Jinja text to silence a warning. S05 as a whole
still applies when every candidate is a legitimate literal.

## SCK-S06 Local references are bounded and reachable

- Type: required
- Applies when: the extractor finds a candidate and context confirms it is an actual local dependency.
- Owner: script
- Pass: each applicable candidate resolves to a readable regular nonsymlink file inside the selected directory.
- Evidence: source file, normalized target path, and L09 applicability reconciliation when needed.
- Common gap: recognized missing target, local `file:` URI, absolute path, root escape, unreadable target, or link to a symlink.
- Minimum change: correct or remove the explicit link; do not guess an intended target.

## SCK-S07 Symbolic links are absent

- Type: required
- Applies when: every create or check run.
- Owner: script
- Pass: the selected Skill contains no symbolic link.
- Evidence: relative link path.
- Common gap: linked file or directory can escape the selected boundary or change independently.
- Minimum change: replace the link with an intentional regular resource or exclude it from the Skill.

## SCK-S08 Bundled resources are routed

- Type: advisory
- Applies when: `references`, `templates`, `assets`, or `scripts` contains a bundled file.
- Owner: script
- Pass: each bundled file is reachable through a script-recognized route from `SKILL.md` — an explicit Markdown link, an inline code span whose path-shaped content resolves to that file, or a table-row cell carrying a path-prefixed token that resolves to that file.
- Evidence: relative orphan path.
- Common gap: stale, duplicated, forgotten, or deliberately complex-routed resource.
- Minimum change: let `SCK-L09` confirm the consumer before routing or removing anything.

## SCK-S09 Canonical structure facts are handed off

- Type: required
- Applies when: the SCK canonical marker is a standalone body line outside code examples; unresolved marker applicability remains not assessed.
- Owner: script
- Pass: supported structure observations are available and any unassessed remainder has a cited context disposition; extraction alone does not establish task completeness.
- Evidence: `facts.body_structure` and any original `not_assessed` entry, with L04/L05 context when needed.
- Common gap: a proven missing task instruction belongs to its L01-L08 semantic item; extraction limits alone are not target defects.
- Minimum change: inspect the cited context; change the target only for an established written-contract gap.

`body_structure` contains observed headings (`text`, `line`), simple bullet
fields (`label`, `line`, `has_value`), and `unassessed_from_line`. Null structure
means no body was available; empty lists are valid observations, not proof of
missing purpose or outputs. A non-null remainder line means only the preceding
structure was extracted. Preserve known marker/prefix facts and remaining
uncertainty separately. File-relative line numbers support L04/L05 inspection;
labels and nonempty values do not prove meaningful instructions.
`has_value` records text on that same line only; inspect context for multiline
values rather than treating this flag as semantic completeness or emptiness.

Chinese or equivalent headings and merged sections are allowed. S09 does not
require a fixed heading or field vocabulary. L04 judges necessary decisions,
L05 the output contract, and L08 applicable side-effect contracts. Report one
root cause once. Inline code may be a real value, while example fields cannot
satisfy a real contract. Complex Markdown requires context review rather than
guessing a gap or claiming complete parser support.

## SCK-S10 No credential-shaped or personal-data-shaped values in bundled files

- Type: required
- Applies when: every target; scanning is deterministic and local.
- Owner: script
- Pass: all in-scope text files were scanned, with no unresolved scan failure or
  matched credential/personal-data candidate. Patterns cover key assignments,
  known token prefixes, private key blocks, credential-bearing connection strings,
  Chinese mobile numbers, and ID numbers; this does not prove absence of secrets.
- Evidence: the masked finding list — file, line, pattern family, and a
  length-only mask. The raw value is never printed anywhere in the output.
- Common gap: a real secret or personal detail committed into an example,
  config sample, script, or note.
- Minimum change: move the value to an external credential source or replace it
  with a documented placeholder; rerun the check.

Detection happens before any semantic reading of the target: once a value enters
a model's context it has already left the machine, so judgment of authenticity
can never be the detection step. The script matches value shapes only; prose
mentions of words like "token" or "secret" are not findings, documented
placeholders and canonical fake numbers are excluded by the pattern set, and
known numeric artifacts (hashes, coefficients) are excluded by boundary guards
and by restricting personal-data patterns to prose file types. Every hit is a
candidate: the owner confirms locally whether it is real. An unresolved
candidate is a required gap for publishing and stays visible as an advisory
otherwise; either way the LLM must not read, quote, or reproduce the value —
judgment works from the file, line, and pattern family alone.

This item is a high-precision, low-recall floor, not a proof of safety. A clean
pass means no value matched the pattern set — obfuscated, encoded, reassembled,
or custom-shaped secrets fall outside it, as do languages and personal-data
shapes the patterns do not cover. In reports, phrase the pass as "扫描未命中"
(no match found), never as evidence that no secret exists. If a target warrants
higher recall, use a dedicated secret scanner (entropy + large wordlists); this
item does not replace one.

Scanning is bounded to regular UTF-8 text no larger than 2 MiB. Hidden text files
(including `.env`) are included. `facts.credential_scan` maps relative paths to
`status` (`scanned`, `not_assessed`, or `excluded`) and a content-free `reason`.
Oversize text, read/walk failures, and undecodable content produce S10
`not_assessed` entries with their paths. Known binary content, symbolic/special
files, `.git`, `__pycache__`, `.pytest_cache`, and `.pyc` caches are recorded as
excluded; excluded directories are not traversed. S07 still owns symbolic links.
Exclusions do not count as scanned text and do not authorize semantic reading.

`facts.semantic_read_files` contains only scanned, non-hit text paths. Neither
the validator's content extraction nor the LLM may read other target text to
complete a dependent check. A withheld entry leaves its content-dependent items
not assessed; a withheld routed Markdown file leaves its nested routes not
assessed while independent file checks continue. A hit file supplies only masked
scan findings and filesystem facts, never headings, metadata, or link excerpts.
The read list is bound to the current scan; changed or newly discovered content
must be scanned again. An absent or failed scan never authorizes a manual read.

## SCK-L01 Purpose and success are explicit

- Type: required
- Applies when: every create or check run.
- Owner: LLM
- Pass: the intended user, recurring problem, and observable successful result are clear.
- Evidence: Purpose or equivalent section.
- Common gap: generic capability description with no user problem or completion result.
- Minimum change: state one bounded problem and observable result.

## SCK-L02 Trigger and scope are distinguishable

- Type: required
- Applies when: every create or check run.
- Owner: LLM
- Pass: positive triggers, an adjacent non-trigger, and the scope boundary are observable.
- Evidence: frontmatter description and Scope or equivalent section.
- Common gap: broad keywords, workflow text in the description, or no non-trigger boundary.
- Minimum change: describe concrete user situations and one nearby request that should not activate.

## SCK-L03 Inputs and missing-input behavior are stated

- Type: required
- Applies when: every create or check run.
- Owner: LLM
- Pass: required inputs, preconditions, and behavior when they are absent are explicit.
- Evidence: Inputs and preconditions or equivalent section.
- Common gap: the workflow assumes files, access, fields, or context that may not exist.
- Minimum change: name each necessary input and the honest ask, stop, or safe default.

Check whether commands or configuration silently assume the author's machine,
personal paths, installed dependencies, or access. A declared fixed-environment
Skill may legitimately use fixed paths; do not demand portability it never
promised. Runtime user inputs and declared environment paths belong here, not
to L09's bundled-resource containment requirement. Judge their written contract,
not whether they exist or work on the reviewer's machine.

When SDK/API or command behavior is materially version-sensitive, check whether
the written dependency and environment identify the applicable behavior.
Missing a version or source link alone is not a gap: explain the actual
ambiguity or execution decision it leaves unresolved. Use L10 for conflicting
current documents. API runtime correctness is outside scope, not a required
unassessed item; do not run calls or install dependencies to establish it.

Against L01's stated purpose, check whether a one-off article, customer request,
date, or prior conversation has silently become a permanent input or instruction.
Report a gap when this contradicts the intended reusable scope or assumes
unavailable context. Clearly labeled examples, historical notes, and explicitly
task-specific Skills are not defects merely because they contain concrete facts.

## SCK-L04 Workflow and completion are executable on paper

- Type: required
- Applies when: every create or check run.
- Owner: LLM
- Pass: ordered actions, material decisions, stop conditions, and completion are unambiguous in writing.
- Evidence: Workflow and Failure and stop conditions or equivalent sections.
- Common gap: unordered goals, hidden decisions, endless iteration, or no completion boundary.
- Minimum change: give a short ordered flow and explicit decision outcomes.

When alternatives materially affect the task, check for a default method and
its switching conditions. Examples are useful only when they resolve a real
ambiguity; short or simple instructions do not need a fixed number of them.
When completion depends on an artifact or state, check that the written flow
names the observable evidence needed to establish completion (for example,
required CSV columns, record count, and successful saving). Existing sufficient
checks or simple response tasks need no separate Verification section. L07
owns failure handling. Do not execute the target or equate a written check
with evidence that the check has passed.

Also resolve S05 placeholder candidates in their actual field/line context,
using S05's dispositions. Keep an actual unfinished slot under S05 with this
L04 evidence, rather than reporting the same slot again as a separate L04 gap.

For automatic retry or correction loops, check how the workflow stops when the
same unresolved problem recurs without new evidence or measurable progress.
Do not require a fixed number of attempts or add a loop to a one-pass workflow.

Compare the document's own count, step, and result-name claims with the actual
lists and references they describe. A contradiction that makes a decision or
completion path ambiguous is a required gap; an inconsequential summary miscount
is advisory. Do not treat unrelated dates or historical/example numbers as
current workflow claims, or invent an absent step to reconcile a count.

When scripts participate, check that their inputs, invocation conditions, output
meaning, and the Agent's subsequent interpretation or decisions are clear from
the existing written instructions or interface documentation. A readable script
alone does not establish this handoff. Report missing operational direction here
(inputs under L03), while L09 owns resource reachability; do not double-count.
Do not demand duplicate interface prose, prescribe scripts for script-free
Skills, or execute a script to establish its actual behavior.

When a workflow reuses evidence, inspect what input, content, version and scope
it binds to; relevant changes must invalidate or recheck affected evidence.
Unchanged evidence can be reused. Summaries must preserve material identity,
source and scope. Report a stale reuse or inflated claim with the claim and its
weaker evidence; unavailable runtime change detection is `not_assessed`, not a
guessed defect. Missing behavioral evidence alone is not a gap unless a supplied
claim depends on it. Abstract verbs such as render, publish or check do not
establish a required CLI/service/credential that the target never consumes.

## SCK-L05 Output contract is clear

- Type: required
- Applies when: every create or check run.
- Owner: LLM
- Pass: the response or file deliverable and its required shape are clear.
- Evidence: Outputs or equivalent section.
- Common gap: says “return results” without format, location, naming, or collision behavior.
- Minimum change: define the observable response or applicable file-output fields.

For human-facing output, recommend making the result, relevant limits, and
useful next action understandable to the intended reader; explain internal
status labels when used. Readability-only improvements are advisory, not a
required gap. For machine consumers, preserve the agreed schema and field names;
do not replace structured output with prose for readability.

For an explicitly declared machine interface, compare field types, enum values,
examples and consumer instructions. Keep machine values separate from human
explanation; a string that says "false" is not a boolean. Invalid inputs need
field/index-specific expected-versus-actual or equivalent repair context when
required by the declared interface. Derive expectations from the target, not
an invented universal schema. An unavailable consumer contract is not assessed;
the absence of a machine interface is not itself a defect.

## SCK-L06 Authority and side effects are bounded

- Type: required
- Applies when: the Skill may read, write, call a service, message a person, or change state.
- Owner: LLM
- Pass: permissions, side effects, and confirmation points match the stated purpose.
- Evidence: Permissions and side effects or equivalent section.
- Common gap: action is implied, authority is broadened, or confirmation is missing.
- Minimum change: identify the exact action and the point where user confirmation is required.

When the target consumes external pages, attachments, or tool responses, check
that their contents are treated as data, not permission to override the user's
request, expand authority, or redirect data. Inspect operative instructions in
the Skill and routed resources in context; an explicitly inert counterexample
is not an instruction to execute. This checks the target's written trust
boundary, separately from SCK protecting its own workflow. Do not execute attack
examples or infer a security certification from this review.

## SCK-L07 Failure reporting is honest

- Type: required
- Applies when: every create or check run.
- Owner: LLM
- Pass: failures stop or degrade explicitly and are not reported as success.
- Evidence: Failure and stop conditions or equivalent section.
- Common gap: empty result, unavailable dependency, timeout, or exception is silently treated as success.
- Minimum change: state the preserved state, failure report, and smallest safe next action.

Consider only relevant written branches: full result, empty result, partial or
degraded result, and unrecoverable failure. A valid no-match result need not be
an error; partial completion must not masquerade as full completion. Missing a
relevant decision is a gap; adding illustrative examples is advisory. Do not
require exhaustive exception lists or run the target to exercise these paths.

For layered diagnostics, follow the detecting component's cause and context
through aggregation. Report a layer that loses or guesses that meaning, with
cited producer and consumer passages. Recovery must preserve still-valid work
and evidence and retry only the demonstrated failed scope. Missing runtime
propagation evidence or host-owned recovery is not assessed, not proof of loss.

## SCK-L08 Conditional external contracts are complete

- Type: required when applicable
- Applies when: the Skill uses a network, handles sensitive data, writes files, or performs an incompatible action.
- Owner: LLM
- Pass: the applicable destination, data, authorization, retention, collision, confirmation, and failure facts are present.
- Evidence: relevant output, permission, and failure sections.
- Common gap: an applicable risk is mentioned without the decisions a user needs.
- Minimum change: add only the fields required by the behavior that actually applies.

Credential and personal-data exposure is judged by `SCK-S10` alone. Do not scan
bundled text for secrets while reviewing a Skill: a value that enters the model's
context has already left the machine, so semantic reading must not be the
detection step. Consume the masked findings from S10 (file, line, pattern family,
length-only mask), never read, quote, or reproduce the flagged value, and never
test a credential against a service. When the S10 scan could not run, record
not assessed; do not substitute a manual read-through.

## SCK-L09 Local dependencies and resource organization are reviewed

- Type: required for actual local dependencies; advisory for resource organization.
- Applies when: the Skill declares a local dependency or contains bundled resources, even when every referenced file is missing and the script reports nothing.
- Owner: LLM
- Pass: all actual local dependencies are identified from context and verified as readable regular nonsymlink files inside the selected directory; bundled resources have justified consumers without needless duplication.
- Evidence: source section, interpreted target, filesystem result, and any S06/S08 candidate reconciliation. State why a candidate is an example or not applicable; retain the original observation.
- Common gap: a missing required file hidden by complex syntax or empty inventory; unnecessary splits, duplication, or buried direction.
- Minimum change: correct a confirmed dependency gap without guessing missing content; keep frequent direction in the main file and only justified resources separately.

Here, a local dependency is a resource the Skill expects to load as part of its
bundle, not a runtime user input or an explicitly declared environment resource
covered by L03. An escaping bundled reference cannot be excused by relabeling it
as input; use its actual role in the workflow and retain the original evidence.

Record each actual route as verified, required gap, not applicable, or
`not_assessed`. Check existence and containment before reading, without executing
the target. A confirmed missing, escaping, symbolic, or unreadable required
dependency is a required gap regardless of syntax; unresolved meaning or
unavailable inspection evidence is `not_assessed`. Organization-only issues stay
advisory. If S06 already covers the same actual route, attach L09 evidence to it
instead of counting a second gap. Zero script warnings never substitutes for
this review; no actual routes and no resources means L09 is not applicable.

## SCK-L10 Current documents agree

- Type: required when current supporting documents exist
- Applies when: README, DESIGN, CHANGELOG, or another current authority accompanies the Skill.
- Owner: LLM
- Pass: current version, capability, terminology, output, permission, and file claims agree with `SKILL.md`.
- Evidence: the smallest conflicting current sections; clearly historical entries are excluded.
- Common gap: stale version, renamed file, removed capability, or contradictory authority statement.
- Minimum change: update the current nonauthoritative statement or expose the unresolved decision.

## SCK-L11 Declared behavior and implementation agree

- Type: required when applicable
- Applies when: the Skill's own text declares permissions, side effects, network use, data
  handling, or environment assumptions, and the Skill bundles executable content
  (`scripts/` or an equivalent routed implementation) that those declarations describe.
- Owner: LLM
- Pass: each material behavior observable in the bundled implementation is covered by the
  written declaration, and no declaration contradicts what the implementation does.
- Evidence: the declaration section and the specific implementing file or function, cited by
  location; both sides are read, neither is executed.
- Common gap: declares read-only while bundled code writes or deletes; declares no network
  while code performs requests; declares no external dependency while code imports one;
  declares a fixed path or write boundary that the implementation crosses.
- Minimum change: align the declaration with the actual behavior, or remove the behavior.
  Never keep a known contradiction between the two.

This item compares written declaration against written implementation. It is not a code
audit: do not judge whether a command is dangerous, whether a destination is trustworthy,
whether credentials are real, or whether the code is correct. Do not execute the bundled
content to establish behavior. A dangerous-looking operation that the declaration covers,
a test-local temporary cleanup, and a call to the Skill's own validator are not gaps.
Report only a contradiction between the two written sides, or an undeclared material
behavior the implementation actually contains.

When the declaration is silent on a behavior rather than contradicting it, judge whether
the omission is material to the stated purpose: an undeclared write, delete, network call,
or outbound data transfer is a gap; an undeclared internal helper is not. If the
declaration or the implementation cannot be inspected, use `not_assessed`.

The declaration's own scope governs. An explicitly scoped statement whose scope matches
the implementation is not a contradiction — for example, "the formal entry is read-only;
offline tooling writes its own outputs" describing a bundle where exactly that holds.
An unqualified machine-readable declaration that bundled content violates remains a gap,
because neither a reader nor the host can tell where the boundary is; a permission field
claiming `read-only` beside bundled scripts that write is the common shape. Judge the
written scope, not the reviewer's guess about intent.

Apply this item after `SCK-L06` and `SCK-L08`: L06 judges whether the declaration bounds
authority, L08 whether conditional external contracts are complete, and L11 whether the
declaration and the bundled implementation describe the same behavior. Report one root
cause once. A Skill with no bundled executable content is not applicable here.

## SCK-L12 README is self-sufficient for a new reader

- Type: required when applicable
- Applies when: a top-level `README` accompanies the Skill. A Skill without one is not
  applicable — creating one is not required.
- Owner: LLM
- Pass: a reader who has never seen the Skill can learn from the README what it is and
  what problem it solves, how to start using it, and when it should not be used.
- Evidence: the README sections that carry each of the three answers; cite section
  location.
- Common gap: the README only restates the name, only lists files, only points to
  `SKILL.md`, or contains only changelog, install notes, or licensing text.
- Minimum change: add the missing answer in the reader's own words. Do not import a
  fixed heading vocabulary or mirror `SKILL.md` wholesale.

Three questions define sufficiency; their wording, heading names, order, and language are
free, and merged sections are allowed. Chinese or equivalent headings are valid. A very
short README that nonetheless answers all three passes.

`SCK-L10` judges agreement between current documents; this item judges completeness for a
reader. A README that agrees with `SKILL.md` but answers none of the three questions passes
L10 and is a required gap here. Do not report the same sentence twice under both items: an
inconsistency belongs to L10, a missing answer belongs here.

The third question (when not to use) may be satisfied by the frontmatter description or a
scope section when the README routes the reader to it — but the README must carry the
first two answers itself. A README whose purpose section is empty or whose "how to start"
is only a file list is a gap. Judge what the reader can learn, not how many sections exist.

Do not reduce this item to vocabulary matching. The presence of words like "purpose",
"usage", or "limitations" is not evidence that a reader learns anything, and their absence
is not a gap: a README can answer all three questions without ever using those words, and
can use all three while saying nothing. Read for what the text conveys, not which terms
appear. This item has no valid keyword or section-count test, and evidence is always a
cited passage read in context.

## SCK-L13 Operative instructions are not duplicated across the contract

- Type: advisory
- Applies when: operative instructions or rules are maintained in more than one
  passage — within `SKILL.md`, across routed bundled files, or in accompanying
  current documents.
- Owner: LLM
- Pass: each operative instruction has one authoritative location; repeats are
  deliberate cross-references or audience-scoped restatements, not parallel
  copies that must be edited together to stay correct.
- Evidence: both passages cited by file and section, with the reason the repeat
  is or is not deliberate.
- Common gap: the same rule maintained in two places, so a later edit to one
  silently diverges the pair; a bundled file's content pasted wholesale into
  `SKILL.md`.
- Minimum change: keep one authoritative passage and reference it, or state
  why the copies must live separately.

Judge meaning, not string similarity. A summary that defers to its authority,
a cross-reference, and an example that instantiates a rule are not duplicates;
two passages that each govern behavior and drift apart on the next edit are.
Deliberate repetition with a stated reason — a machine-readable frontmatter
summary beside body detail, a reader-facing README restatement that serves its
own audience — is not a gap; a verbatim copy that only stays correct through
synchronized edits is. Division of labor: a contradiction between copies
belongs to `SCK-L10` (`SCK-L04` for count and list claims inside one
document), a redundant or unnecessarily split bundled file belongs to
`SCK-L09`; this item reports only the still-consistent parallel copy that
invites future drift. Report one root cause once, under the item that owns
it. When routed content needed for the comparison was withheld or unreadable,
use `not_assessed`.
