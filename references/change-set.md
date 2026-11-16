# Change-set v1

A change-set is the machine-readable form of the Change confirmation. Build one
per edit attempt, show it with `--dry-run`, and apply only after the user
confirms the listed paths. The applier is an executor, not a planner: it never
decides what to change.

```json
{
  "schema": "skill-creator-king.change-set.v1",
  "target": "/absolute/path/to/skill",
  "operation": "check",
  "confirmed": true,
  "changes": [
    {"path": "SKILL.md", "action": "modify", "expected_sha256": "<sha256 of the assessed file>", "edits": [{"old": "exact text", "new": "replacement text"}]},
    {"path": "scripts", "action": "mkdir"},
    {"path": "scripts/check.py", "action": "create", "content": "full file content"},
    {"path": "references/old.md", "action": "delete", "expected_sha256": "<sha256>"},
    {"path": "references/a.md", "action": "rename", "destination": "references/b.md", "expected_sha256": "<sha256>"}
  ]
}
```

## Rules

- `confirmed` must be `true`. It records that the user confirmed this exact
  path list; it is a declaration, not proof of consent.
- `target` is absolute and must resolve to an existing directory that is not a
  symbolic link.
- Every `path` and `destination` is relative, uses `/`, and contains no `.` or
  `..` segment. No component may be a symbolic link.
- `modify` replaces exact text. Each `old` must occur exactly once in the
  assessed file, edits must not overlap, and the result must differ. Full-file
  rewrites are not accepted; split them into the smallest edits.
- `mkdir` requires the path to be absent and its parent to exist on disk or be
  created by an earlier `mkdir` entry. It creates one directory; list entries in
  parent-before-child order.
- `create` requires the path to be absent and its parent directory to exist on
  disk or be created by an earlier `mkdir` entry.
- `delete` accepts regular files only. Directories are never deleted.
- `rename` requires the source hash to match, the destination to be absent, and
  the destination parent to exist.
- One path may appear only once across all changes, including destinations.
- At most 100 changes per set.

## Execution and journal

Preflight validates the whole set. POSIX `dir_fd`/`O_NOFOLLOW` support is required;
unsupported hosts refuse, including dry-run. Mutations and temporary cleanup use
pinned parent descriptors: replacement symlinks cannot redirect them. Parent/file
identity and content are checked before each action, results afterwards. Final-check
content races and relocation of already-open directories remain possible; this is
not isolation or crash recovery.

Create/rename publish by exclusive hard link. Rename is link+unlink, not atomic;
unsupported or cross-filesystem links fail without fallback. Originals are staged
outside the target. Write failure attempts guarded recovery of matching files and
empty created directories; conflicts retain backups and leave third-party content.
Successful writing ends the transaction before static recheck. Failed recheck means
edits remain unverified; repair needs a fresh scan and a new authorized change-set.

```bash
python3 "<loaded-sck-directory>/scripts/apply_changes.py" "<change-set.json>" --dry-run
python3 "<loaded-sck-directory>/scripts/apply_changes.py" "<change-set.json>"
```

Exit codes: `0` applied or dry-run valid; `2` preflight refused, nothing written;
`3` apply failed (possibly before any target write), recovery attempted when
staging was available. Every outcome prints one JSON journal:

```json
{
  "schema": "skill-creator-king.change-journal.v1",
  "completed": true,
  "dry_run": false,
  "target": "/absolute/path/to/skill",
  "applied": [
    {
      "path": "SKILL.md",
      "action": "modify",
      "before_sha256": "...",
      "after_sha256": "..."
    }
  ],
  "failure": null,
  "rollback": { "attempted": false, "restored": [], "skipped": [], "temp_dir": null }
}
```

Hashes record changes. `applied` includes effects whose postcheck failed;
`rename_state: destination_linked|renamed` distinguishes partial renames.
`rollback.skipped` names unresolved paths and their `backup_file` in `temp_dir`.
Do not claim complete recovery when skipped paths remain. `failure.kind` is
`conflict`, `io_error` or `cleanup_error`. Cleanup failure reports the retained
location; backups may be incomplete. After successful writes it returns exit 3,
leaves edits in place and does not attempt rollback.
