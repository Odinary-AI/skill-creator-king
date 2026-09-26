---
name: example-skill
description: Use when {{observable user situations that should activate this Skill}}.
---
<!-- sck-format: 5 -->

Use the following headings as a starting point; equivalent headings or merged
sections are allowed. Add author, version, or bilingual descriptions only when
needed by the host or task. Remove this guidance from the finished Skill.

# {{Skill title}}

## Purpose

{{State the intended user, problem, and successful outcome.}}

## Scope

- Use when: {{positive trigger stated in user language}}.
- Do not use when: {{non-trigger or adjacent task}}.

## Inputs and preconditions

- Required: {{input or existing context}}.
- Missing input: {{ask, stop, or use a safe explicit default}}.
- Environment: {{required tools, access, or path assumptions; none if absent}}.

## Workflow

1. {{Observable action and decision.}}
2. {{Next action, including the stop condition when it can fail.}}

Where needed, state the default method, switching condition, and observable
completion evidence. Omit unnecessary branches or checks and remove this guidance.

## Outputs

- Produces files: no
- Response: {{intended reader or machine consumer, format, and required fields}}.

For a file-producing Skill, change `Produces files` to `yes` and use the applicable
contract prompts below; equivalent wording or grouping is allowed. Remove unused
prompts and this guidance:

- Directory: {{destination rule}}.
- Naming: {{filename rule}}.
- Format: {{file format}}.
- Directory creation: {{create, request permission, or stop when the directory is absent}}.
- Overwrite: {{confirmation or collision rule}}.
- Failure: {{error report and preservation rule}}.

## Permissions and side effects

- Read/write actions: {{none or explicit boundary}}.
- Network/external actions: {{none or destination, transmitted data,
  authorization point, and failed/unavailable behavior}}.
- Sensitive data: {{none or access, redaction, retention, disclosure, and safe
  failure behavior}}.
- Confirmation: {{observable confirmation point}}.

If external content is consumed, state how it remains data rather than authority
to change the user's request or permissions. Remove this instruction otherwise.
Use sanitized examples and external credential references, not real private data.

## Failure and stop conditions

- Stop when: {{condition, preserved state, and safe next action}}.

State only applicable empty, partial, or unrecoverable-result behavior. If the
workflow retries automatically, include its no-progress stop condition. Replace
these instructions with concrete applicable behavior, not an exception catalog.

## Resources

- Load a relative Markdown resource link when {{observable condition}}.
- Remove this section when no bundled resource is needed.
