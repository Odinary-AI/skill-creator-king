#!/usr/bin/env python3
"""Apply one confirmed SCK change-set with hash checks and rollback.

This is an executor, not a planner: it never decides what to change. The
change-set is built and confirmed before this script runs. See
references/change-set.md for the schema and journal contract.
"""
import argparse
import errno
import hashlib
import json
import os
import shutil
import stat
import tempfile
import uuid
from pathlib import Path


SCHEMA = "skill-creator-king.change-set.v1"
JOURNAL_SCHEMA = "skill-creator-king.change-journal.v1"
ACTIONS = ("modify", "create", "delete", "rename", "mkdir")
MAX_CHANGES = 100


class Refused(Exception):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def refuse(label, message):
    raise Refused("%s: %s" % (label, message))


def load(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Refused("change-set: %s" % exc)
    if not isinstance(data, dict):
        refuse("change-set", "expected an object")
    if data.get("schema") != SCHEMA:
        refuse("change-set.schema", "expected %s" % SCHEMA)
    if data.get("confirmed") is not True:
        refuse("change-set.confirmed", "must be true")
    if data.get("operation") not in ("check", "reflect"):
        refuse("change-set.operation", "expected check or reflect")
    target = data.get("target")
    if not isinstance(target, str) or not target:
        refuse("change-set.target", "expected a path")
    root = Path(target)
    if not root.is_absolute():
        refuse("change-set.target", "must be absolute")
    if root.is_symlink() or not root.is_dir():
        refuse("change-set.target", "must be an existing directory")
    changes = data.get("changes")
    if not isinstance(changes, list) or not 1 <= len(changes) <= MAX_CHANGES:
        refuse("change-set.changes", "expected 1..%d items" % MAX_CHANGES)
    # Do not resolve after checking: a newly substituted root symlink must fail
    # the no-follow open, not become a different authorized directory.
    return root, changes


def relative(value, label):
    if not isinstance(value, str) or not value.strip():
        refuse(label, "expected a nonempty relative path")
    if value.startswith("~") or os.path.isabs(value) or "\\" in value or "\x00" in value:
        refuse(label, "must be a relative POSIX path")
    path = Path(value)
    if any(part in ("", ".", "..") for part in value.split("/")):
        refuse(label, "must not contain . or .. segments")
    return path


class Conflict(OSError):
    """The confirmed content or a pinned path no longer matches."""


def identity(info):
    return info.st_dev, info.st_ino, stat.S_IMODE(info.st_mode)


class Target:
    """Pin directory identities; never resolve mutation paths through symlinks.

    This is not a filesystem transaction or a lock on uncooperative writers.
    All final mutations and temporary cleanup use directory-relative syscalls.
    """
    def __init__(self, root):
        needed = (os.open, os.stat, os.mkdir, os.unlink, os.rmdir, os.link, os.rename)
        if (not all(fn in os.supports_dir_fd for fn in needed)
                or os.stat not in os.supports_follow_symlinks
                or os.link not in os.supports_follow_symlinks
                or not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY")):
            raise Refused("applier requires POSIX dir_fd and no-follow filesystem operations")
        self.root = root
        self.dirs = {}
        before = os.stat(root, follow_symlinks=False)
        if not stat.S_ISDIR(before.st_mode):
            raise Refused("target is no longer a nonsymbolic directory")
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        if identity(before) != identity(os.fstat(fd)):
            os.close(fd)
            raise Conflict("target directory identity changed while opening")
        self.dirs[Path(".")] = fd

    def __enter__(self):
        return self

    def __exit__(self, *args):
        for fd in self.dirs.values():
            os.close(fd)

    def verify(self, directory=Path(".")):
        for path, fd in self.dirs.items():
            if path != directory and path not in directory.parents:
                continue
            if path == Path("."):
                current = os.stat(self.root, follow_symlinks=False)
            else:
                current = os.stat(path.name, dir_fd=self.dirs[path.parent], follow_symlinks=False)
            if not stat.S_ISDIR(current.st_mode) or identity(current) != identity(os.fstat(fd)):
                raise Conflict("directory identity changed: %s" % path)

    def directory(self, path):
        self.verify(path)
        current = Path(".")
        for part in path.parts:
            child = current / part
            if child not in self.dirs:
                try:
                    self.dirs[child] = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                              dir_fd=self.dirs[current])
                except OSError as exc:
                    raise Conflict("parent directory unavailable or symbolic: %s (%s)" % (child, exc)) from exc
            current = child
        self.verify(path)
        return self.dirs[current]

    def parent(self, path):
        return self.directory(path.parent)

    def info(self, path):
        fd = self.parent(path)
        try:
            return os.stat(path.name, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            return None

    def absent(self, path, planned=()):
        # Parents scheduled by earlier mkdir operations do not exist yet.
        if any(parent in planned for parent in path.parents):
            self.verify()
            return
        if self.info(path) is not None:
            raise Conflict("path already exists: %s" % path)

    def read(self, path):
        parent = self.parent(path)
        info = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode):
            raise Conflict("not a regular nonsymbolic file (symbolic links are not editable): %s" % path)
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or identity(before) != identity(info):
                raise Conflict("file identity changed: %s" % path)
            data = stream.read()
            after = os.fstat(stream.fileno())
        current = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        if (identity(current) != identity(after) or before.st_mtime_ns != after.st_mtime_ns
                or before.st_ctime_ns != after.st_ctime_ns or before.st_size != after.st_size):
            raise Conflict("file changed while reading: %s" % path)
        self.verify(path.parent)
        return data, identity(after)

    def check(self, path, data, state=None):
        if data is None:
            self.absent(path)
            return
        actual, current = self.read(path)
        if actual != data or (state is not None and current != state):
            raise Conflict("content or file identity changed: %s" % path)


def require_hash(item, data, label):
    expected = item.get("expected_sha256")
    if not isinstance(expected, str) or not expected:
        refuse(label + ".expected_sha256", "required")
    actual = digest(data)
    if actual != expected.lower():
        refuse(label + ".expected_sha256", "content changed: expected %s, found %s" % (expected, actual))


def decode(data, label):
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        refuse(label, "edits require UTF-8 text")


def apply_edits(text, edits, label):
    if not isinstance(edits, list) or not edits:
        refuse(label + ".edits", "expected a nonempty array")
    spans = []
    for index, edit in enumerate(edits):
        item = "%s.edits[%d]" % (label, index)
        if not isinstance(edit, dict):
            refuse(item, "expected an object")
        old, new = edit.get("old"), edit.get("new")
        if not isinstance(old, str) or not old:
            refuse(item + ".old", "expected nonempty text")
        if not isinstance(new, str):
            refuse(item + ".new", "expected text")
        start = text.find(old)
        if start < 0:
            refuse(item + ".old", "text not found")
        if text.find(old, start + 1) >= 0:
            refuse(item + ".old", "text occurs more than once")
        spans.append((start, start + len(old), new))
    spans.sort()
    for left, right in zip(spans, spans[1:]):
        if left[1] > right[0]:
            refuse(label + ".edits", "edits overlap")
    pieces = []
    cursor = 0
    for start, end, new in spans:
        pieces.append(text[cursor:start])
        pieces.append(new)
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def prepare(tree, changes):
    seen, planned_dirs, ops = set(), set(), []
    for index, item in enumerate(changes):
        label = "changes[%d]" % index
        if not isinstance(item, dict):
            refuse(label, "expected an object")
        action = item.get("action")
        if action not in ACTIONS:
            refuse(label + ".action", "expected one of %s" % ", ".join(ACTIONS))
        path = relative(item.get("path"), label + ".path")
        if path in seen:
            refuse(label + ".path", "duplicate path: %s" % path)
        seen.add(path)
        op = {"index": index, "action": action, "path": path, "relative": str(path),
              "before": None, "after": None, "before_state": None}
        if action in ("mkdir", "create"):
            tree.absent(path, planned_dirs)
            if action == "mkdir":
                planned_dirs.add(path)
                op["mode"] = 0o755
            else:
                if not isinstance(item.get("content"), str):
                    refuse(label + ".content", "expected text")
                op.update(after=item["content"].encode("utf-8"), mode=0o644)
        else:
            before, state = tree.read(path)
            require_hash(item, before, label)
            op.update(before=before, before_state=state, mode=state[2])
            if action == "modify":
                after = apply_edits(decode(before, label + ".path"), item.get("edits"), label).encode("utf-8")
                if after == before:
                    refuse(label + ".edits", "result is unchanged")
                op["after"] = after
            elif action == "rename":
                destination = relative(item.get("destination"), label + ".destination")
                if destination in seen:
                    refuse(label + ".destination", "duplicate path: %s" % destination)
                seen.add(destination)
                tree.absent(destination, planned_dirs)
                op.update(destination=destination, destination_relative=str(destination))
        ops.append(op)
    return ops


def replace_file(source, destination, *, src_dir_fd, dst_dir_fd):
    """Use the POSIX replacement primitive checked by Target's preflight."""
    try:
        os.rename(source, destination, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd)
    except (TypeError, NotImplementedError) as exc:
        # A runtime may reject advertised kwargs. Keep this narrowly scoped to
        # the syscall so apply/restore can still report effects and recover.
        raise OSError(errno.ENOTSUP, "directory-relative replacement unsupported: %s" % exc) from exc


def atomic_write(tree, path, data, mode, expected=None, state=None, record=lambda state: None):
    """Publish a complete temporary file; absent destinations are never replaced."""
    parent = tree.parent(path)
    tree.check(path, expected, state)
    name = ".sck-%s.tmp" % uuid.uuid4().hex
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
    temporary_state = identity(os.fstat(fd))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            temporary_state = identity(os.fstat(stream.fileno()))
            os.fsync(stream.fileno())
        tree.check(path, expected, state)
        if identity(os.stat(name, dir_fd=parent, follow_symlinks=False)) != temporary_state:
            raise Conflict("temporary file identity changed: %s" % path)
        if expected is None:
            os.link(name, path.name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
        else:
            replace_file(name, path.name, src_dir_fd=parent, dst_dir_fd=parent)
        record(temporary_state)  # Record the side effect before any fallible postcheck.
        tree.check(path, data, temporary_state)
    finally:
        try:
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            if identity(info) == temporary_state:
                os.unlink(name, dir_fd=parent)
            else:
                raise Conflict("temporary file replaced; cleanup refused: %s" % path)


def remove_file(tree, path, data, state):
    parent = tree.parent(path)
    tree.check(path, data, state)
    os.unlink(path.name, dir_fd=parent)


def link_file(tree, source, destination, data, state):
    source_fd, dest_fd = tree.parent(source), tree.parent(destination)
    tree.check(source, data, state)
    tree.absent(destination)
    # link() fails atomically if destination exists; rename() would overwrite it.
    os.link(source.name, destination.name, src_dir_fd=source_fd, dst_dir_fd=dest_fd,
            follow_symlinks=False)


def summary(op):
    result = {
        "path": op["relative"],
        "action": op["action"],
        "destination": op.get("destination_relative"),
        "before_sha256": digest(op["before"]) if op["before"] is not None else None,
        "after_sha256": digest(op["after"]) if op["after"] is not None else None,
    }
    if "source_removed" in op:
        result["rename_state"] = "renamed" if op["source_removed"] else "destination_linked"
    return result


def cleanup_backups(backup_dir):
    try:
        shutil.rmtree(backup_dir)
    except OSError as exc:
        return {"temp_dir": str(backup_dir), "cleanup_error": str(exc)}
    return {"temp_dir": None}


def restore(tree, applied, backup_dir):
    restored, skipped = [], []
    for op in reversed(applied):
        path, action = op["path"], op["action"]
        backup = backup_dir / ("%d.orig" % op["index"])
        try:
            tree.verify()
            if action == "modify":
                atomic_write(tree, path, backup.read_bytes(), op["mode"], op["after"], op["written_state"])
            elif action == "create":
                remove_file(tree, path, op["after"], op["written_state"])
                tree.absent(path)
            elif action == "mkdir":
                info = tree.info(path)
                if info is None or not stat.S_ISDIR(info.st_mode) or identity(info) != op["written_state"]:
                    raise Conflict("created directory changed: %s" % path)
                parent = tree.parent(path)
                os.rmdir(path.name, dir_fd=parent)  # Refuses nonempty directories.
                if path in tree.dirs:
                    os.close(tree.dirs.pop(path))
                tree.absent(path)
            elif action == "delete":
                atomic_write(tree, path, backup.read_bytes(), op["mode"])
            else:
                destination = op["destination"]
                tree.check(destination, op["before"], op["before_state"])
                if op.get("source_removed"):
                    link_file(tree, destination, path, op["before"], op["before_state"])
                tree.check(path, op["before"], op["before_state"])
                remove_file(tree, destination, op["before"], op["before_state"])
                tree.absent(destination)
            restored.append(op["relative"])
        except OSError as exc:
            item = {"path": op["relative"], "reason": str(exc)}
            if op["before"] is not None:
                item["backup_file"] = backup.name
            if action == "rename":
                item["destination"] = op["destination_relative"]
            skipped.append(item)
    if skipped:
        return {"attempted": True, "restored": restored, "skipped": skipped, "temp_dir": str(backup_dir)}
    return {"attempted": True, "restored": restored, "skipped": [], **cleanup_backups(backup_dir)}


def verify_applied(tree, op):
    if op["action"] == "mkdir":
        info = tree.info(op["path"])
        if info is None or not stat.S_ISDIR(info.st_mode) or identity(info) != op["written_state"]:
            raise Conflict("created directory changed: %s" % op["path"])
    elif op["action"] == "rename":
        tree.absent(op["path"])
        tree.check(op["destination"], op["before"], op["before_state"])
    else:
        tree.check(op["path"], op["after"], op.get("written_state"))


def apply(ops, tree):
    backup_dir, applied, current = None, [], None
    try:
        backup_dir = Path(tempfile.mkdtemp(prefix="sck-rollback-"))
        for op in ops:
            current = op
            path, action = op["path"], op["action"]
            tree.check(path, op["before"], op["before_state"])
            if op["before"] is not None:
                (backup_dir / ("%d.orig" % op["index"])).write_bytes(op["before"])

            def record(state):
                op["written_state"] = state
                applied.append(op)

            if action == "mkdir":
                parent = tree.parent(path)
                os.mkdir(path.name, mode=op["mode"], dir_fd=parent)
                record(identity(os.stat(path.name, dir_fd=parent, follow_symlinks=False)))
                tree.directory(path)
            elif action in ("modify", "create"):
                atomic_write(tree, path, op["after"], op["mode"], op["before"], op["before_state"], record)
            elif action == "delete":
                remove_file(tree, path, op["before"], op["before_state"])
                record(None)
            else:
                link_file(tree, path, op["destination"], op["before"], op["before_state"])
                record(op["before_state"])
                op["source_removed"] = False
                tree.check(op["destination"], op["before"], op["before_state"])
                remove_file(tree, path, op["before"], op["before_state"])
                op["source_removed"] = True
            verify_applied(tree, op)
        for op in applied:
            current = op
            verify_applied(tree, op)
    except OSError as exc:
        rollback = (restore(tree, applied, backup_dir) if backup_dir is not None else
                    {"attempted": False, "restored": [], "skipped": [], "temp_dir": None})
        return {
            "completed": False,
            "applied": [summary(op) for op in applied],
            "failure": {"path": current["relative"] if current else None, "reason": str(exc),
                        "kind": "conflict" if isinstance(exc, (Conflict, FileExistsError)) else "io_error"},
            "rollback": rollback,
        }
    cleanup = cleanup_backups(backup_dir)
    failure = ({"path": None, "kind": "cleanup_error",
                "reason": "writes completed; backup cleanup failed: " + cleanup["cleanup_error"]}
               if "cleanup_error" in cleanup else None)
    return {
        "completed": failure is None,
        "applied": [summary(op) for op in applied],
        "failure": failure,
        "rollback": {"attempted": False, "restored": [], "skipped": [], **cleanup},
    }


def journal(payload):
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("change_set")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        root, changes = load(args.change_set)
        with Target(root) as tree:
            ops = prepare(tree, changes)
            if args.dry_run:
                result = {"completed": True, "applied": [summary(op) for op in ops], "failure": None,
                          "rollback": {"attempted": False, "restored": [], "skipped": [], "temp_dir": None}}
            else:
                result = apply(ops, tree)
        journal({"schema": JOURNAL_SCHEMA, "dry_run": args.dry_run, "target": str(root), **result})
        return 0 if result["completed"] else 3
    except (Refused, OSError) as exc:
        journal({
            "schema": JOURNAL_SCHEMA, "completed": False, "dry_run": args.dry_run, "target": None,
            "applied": [], "failure": {"path": None, "reason": str(exc)},
            "rollback": {"attempted": False, "restored": [], "skipped": [], "temp_dir": None},
        })
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
