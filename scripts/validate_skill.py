#!/usr/bin/env python3
"""Read-only structural validation for one Agent Skill; never executes its code."""

import argparse
import json
import os
import re
from pathlib import Path
from urllib.parse import unquote


NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SIMPLE_LINK_PATTERN = re.compile(
    r"\[[^\]\n]*\]\((<[^>\n]+>|[^()\s]+)(?:\s+[^)\n]+)?\)"
)
INLINE_CODE_PATTERN = re.compile(r"`+[^`\n]*`+")
EXTERNAL_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
CANONICAL_MARKER = "<!-- sck-format: 5 -->"
RESOURCE_DIRECTORIES = {"references", "templates", "assets", "scripts"}
PROFILES = ("auto", "generic", "workbuddy", "codex")

MESSAGES = {
    "skill.directory.missing": "The selected Skill directory does not exist.",
    "skill.directory.unreadable": "The selected Skill directory cannot be fully read.",
    "skill.file.missing": "The selected directory must contain a regular SKILL.md.",
    "skill.file.encoding": "SKILL.md must be readable UTF-8.",
    "frontmatter.invalid": "SKILL.md must begin with valid YAML mapping frontmatter.",
    "frontmatter.not_assessed": "YAML-dependent checks could not be completed.",
    "frontmatter.name.missing": "Frontmatter name must be a nonempty string.",
    "frontmatter.description.too_long": "Frontmatter description must not exceed 1024 characters.",
    "frontmatter.description.missing": "Frontmatter description must be a nonempty string.",
    "frontmatter.compatibility.invalid": "Optional compatibility must be a string of at most 500 characters.",
    "codex.metadata.invalid": "Supported Codex metadata has an invalid shape or value.",
    "frontmatter.name.invalid": "Skill name must use lowercase letters, digits, and single hyphens.",
    "skill.name.directory_mismatch": "The directory basename and declared name differ.",
    "canonical.placeholder.candidate": "Possible unfinished slot; LLM context review is required before classifying S05.",
    "check.not_assessed": "This check could not run because a prerequisite was unavailable.",
    "reference.unreadable": "A routed Markdown resource must be readable UTF-8.",
    "reference.path.absolute": "A local Markdown reference must be relative.",
    "reference.path.escape": "A local Markdown reference resolves outside the Skill.",
    "reference.path.symlink": "A routed local reference cannot be symbolic.",
    "reference.path.unreadable": "A routed local reference cannot be resolved.",
    "reference.missing": "A routed local resource is not a regular file.",
    "path.symlink": "The selected Skill cannot contain symbolic links.",
    "resource.orphan": "A bundled resource has no route from SKILL.md.",
    "content.credential.candidate": "A credential-shaped value may be present; the owner must resolve it before trusting this copy.",
    "content.pii.candidate": "A personal-data-shaped value may be present; the owner must resolve it before sharing this copy.",
}


_SCAN_MAX_BYTES = 2 * 1024 * 1024
_SCAN_EXCLUDED_DIRS = {".git", "__pycache__", ".pytest_cache"}
_VALUE_PLACEHOLDER_MARKERS = (
    "xxx", "your-", "your_", "example", "changeme", "placeholder", "dummy",
    "todo", "fixme", "replace", "<your", "<insert", "fake",
)
_KNOWN_FAKE_NUMBERS = {
    "13800138000", "13000000000", "13900000000",
    "110101199001011234", "110101199003077",
}
_CREDENTIAL_PATTERNS = (
    (
        "assignment",
        re.compile(
            r"(?i)(?:^|[^A-Za-z])(api[_-]?key|api[_-]?secret|client[_-]?secret"
            r"|secret|token|access[_-]?key|private[_-]?key|authorization)"
            r"\s*[:=]\s*[\"']?([A-Za-z0-9_\-+/=.]{16,})[\"']?"
        ),
    ),
    (
        "password",
        re.compile(
            r"(?i)(?:^|[^A-Za-z])(password|passwd|pwd)\s*[:=]\s*[\"']([^\"'\s]{8,})[\"']"
        ),
    ),
    (
        "token-prefix",
        re.compile(
            r"\b(sk-ant-[A-Za-z0-9_\-]{12,}|sk-[A-Za-z0-9_\-]{16,}"
            r"|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|ghu_[A-Za-z0-9]{20,}"
            r"|github_pat_[A-Za-z0-9_]{20,}|glpat-[A-Za-z0-9_\-]{12,}"
            r"|xox[baprs]-[A-Za-z0-9\-]{10,}|AKIA[A-Z0-9]{16}|ASIA[A-Z0-9]{16}"
            r"|AIza[A-Za-z0-9_\-]{20,})\b"
        ),
    ),
    (
        "private-key-block",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY(?: BLOCK)?-----"),
    ),
    (
        "connection-string",
        re.compile(
            r"\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|rediss"
            r"|amqp(?:s)?|rabbitmq|mssql|oracle)://[^\s/:@]+:[^\s/@]+@"
        ),
    ),
)
_PII_PATTERNS = (
    ("cn-mobile", re.compile(r"(?<![\dA-Za-z.])1[3-9]\d{9}(?![\dA-Za-z.])")),
    ("cn-id-card", re.compile(r"(?<![\dA-Za-z.])\d{17}[\dXx](?![\dA-Za-z.])")),
)
_PII_FILE_SUFFIXES = {".md", ".txt", ".py", ".sh", ".yaml", ".yml"}


def _credential_scan(root):
    """Scan bundled text files for credential-shaped or PII-shaped values.

    Detection is deterministic and local; matched values are never returned.
    Each hit is reported as file, line, pattern family, and a length-only mask
    so downstream judgment can happen without the value entering any context.
    Documented placeholder markers are excluded by the pattern set itself.
    """
    hits = []
    hit_files = set()
    coverage = {}

    def record(path, status, reason):
        coverage[_relative(path, root)] = {"status": status, "reason": reason}

    def walk_error(exc):
        record(Path(exc.filename) if exc.filename else root,
               "not_assessed", type(exc).__name__)

    for current, dirs, files in os.walk(str(root), followlinks=False, onerror=walk_error):
        for name in list(dirs):
            path = Path(current) / name
            if name in _SCAN_EXCLUDED_DIRS or path.is_symlink():
                record(path, "excluded", "cache or VCS directory" if name in
                       _SCAN_EXCLUDED_DIRS else "symbolic link; covered by S07")
                dirs.remove(name)
        for name in files:
            path = Path(current) / name
            relative = _relative(path, root)
            if path.suffix == ".pyc":
                record(path, "excluded", "compiled Python cache")
                continue
            try:
                if path.is_symlink() or not path.is_file():
                    record(path, "excluded", "symbolic or special file")
                    continue
                if path.stat().st_size > _SCAN_MAX_BYTES:
                    record(path, "not_assessed", "exceeds 2 MiB scan limit")
                    continue
                raw = path.read_bytes()
            except OSError as exc:
                record(path, "not_assessed", type(exc).__name__)
                continue
            if b"\x00" in raw[:8192]:
                record(path, "excluded", "binary content")
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                record(path, "not_assessed", "invalid UTF-8")
                continue
            record(path, "scanned", "supported text patterns assessed")
            for line_number, line in enumerate(text.splitlines(), 1):
                found = False
                for family, pattern in _CREDENTIAL_PATTERNS:
                    for match in pattern.finditer(line):
                        value = match.group(match.lastindex or 0)
                        if (any(marker in value.lower() for marker in _VALUE_PLACEHOLDER_MARKERS)
                                or len(set(value)) == 1):
                            continue
                        hits.append({"path": relative, "line": line_number,
                                     "family": family, "mask": "%s chars" % len(value)})
                        hit_files.add(relative)
                        found = True
                        break
                    if found:
                        break
                if not found:
                    if path.suffix.lower() not in _PII_FILE_SUFFIXES:
                        continue
                    for family, pattern in _PII_PATTERNS:
                        for match in pattern.finditer(line):
                            value = match.group(0)
                            if value in _KNOWN_FAKE_NUMBERS or len(set(value)) <= 2:
                                continue
                            hits.append({"path": relative, "line": line_number,
                                         "family": family, "mask": "pii"})
                            hit_files.add(relative)
                            found = True
                            break
                        if found:
                            break
    return hits, sorted(hit_files), dict(sorted(coverage.items()))


def _metadata_strings(metadata, placeholder):
    """Visit safe YAML strings, including extensions, without alias recursion."""
    pending = [('frontmatter', metadata)]
    visited = set()
    while pending:
        path, value = pending.pop()
        if isinstance(value, str):
            yield path, value
        elif isinstance(value, (dict, list, tuple, set)):
            if id(value) in visited:
                continue
            visited.add(id(value))
            if isinstance(value, dict):
                for index, (key, child) in reversed(list(enumerate(value.items()))):
                    # Never reproduce a placeholder-like key as evidence text.
                    label = key if isinstance(key, str) and not placeholder.search(key) else '<key %s>' % index
                    pending.append((path + '.' + label, child))
                    pending.append((path + '.<key %s>' % index, key))
            else:
                values = sorted(value, key=repr) if isinstance(value, set) else value
                pending.extend((path + '[%s]' % index, child)
                               for index, child in reversed(list(enumerate(values))))


class FrontmatterError(ValueError):
    """The frontmatter has a proven syntax or root-type error."""


class FrontmatterUnavailable(RuntimeError):
    """A safe parser is missing or cannot assess the YAML construct."""


def _frontmatter_parts(text):
    """Locate only Markdown delimiters; leave all YAML grammar to PyYAML."""
    text = text.lstrip("\ufeff")
    if not text.startswith("---\n"):
        raise FrontmatterError("opening delimiter is absent")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise FrontmatterError("closing delimiter is absent")
    # Retain the YAML line break before the closing Markdown delimiter: it
    # affects the decoded value of literal/folded block scalars.
    return text[4:end + 1], text[end + 5 :]


def parse_frontmatter(text):
    """Delegate YAML grammar and types to PyYAML's safe loader."""
    source, body = _frontmatter_parts(text)
    return parse_yaml_mapping(source, "SKILL.md", 2), body


def parse_yaml_mapping(source, filename, line_offset=1):
    """Share the safe, duplicate-aware parser with platform metadata."""

    try:
        import yaml
    except ImportError as exc:
        raise FrontmatterUnavailable(
            "PyYAML is unavailable in this Python environment; use an approved "
            "environment with PyYAML 6.x. No dependency was installed."
        ) from exc
    class UniqueSafeLoader(yaml.SafeLoader):
        def __init__(self, stream):
            super().__init__(stream)
            self.checked_mappings = set()
            self.merge_key = object()

        def flatten_mapping(self, node):
            # Inspect explicit pairs BEFORE merge expansion mutates this node.
            # Revisited aliases must not mistake inherited keys for duplicates.
            if id(node) not in self.checked_mappings:
                self.checked_mappings.add(id(node))
                seen = {}
                for key_node, _ in node.value:
                    # Match SafeConstructor's treatment of the YAML value key
                    # before constructing it for duplicate comparison.
                    if key_node.tag == 'tag:yaml.org,2002:value':
                        key_node.tag = 'tag:yaml.org,2002:str'
                    key = (self.merge_key if key_node.tag == 'tag:yaml.org,2002:merge'
                           else self.construct_object(key_node, deep=False))
                    try:
                        previous = seen.get(key)
                    except TypeError:
                        # Let SafeLoader classify unsupported unhashable keys.
                        continue
                    if previous is not None:
                        label = (repr(key) if isinstance(key, str)
                                 and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]{0,63}', key)
                                 else '<key>')
                        raise FrontmatterError(
                            'duplicate key %s at %s lines %s and %s'
                            % (label, filename, previous + line_offset,
                               key_node.start_mark.line + line_offset)
                        )
                    seen[key] = key_node.start_mark.line
            super().flatten_mapping(node)

    try:
        metadata = yaml.load(source, Loader=UniqueSafeLoader)
    except FrontmatterError:
        raise
    except yaml.constructor.ConstructorError as exc:
        raise FrontmatterUnavailable(
            "Safe YAML construction is unsupported; do not use an unsafe loader."
        ) from exc
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        location = " at %s line %s" % (filename, mark.line + line_offset) if mark else ""
        raise FrontmatterError(type(exc).__name__ + location) from exc
    except (ValueError, OverflowError) as exc:
        # Safe scalar constructors (notably dates) can raise outside YAMLError.
        raise FrontmatterError(type(exc).__name__ + " in YAML scalar construction") from exc
    except RecursionError as exc:
        raise FrontmatterUnavailable("Safe YAML parsing exceeded the interpreter's nesting capacity.") from exc
    if not isinstance(metadata, dict):
        raise FrontmatterError("YAML root must be a mapping")
    return metadata


def _issue(check_id, code, evidence, path="SKILL.md"):
    return {
        "check_id": check_id,
        "code": code,
        "message": MESSAGES[code],
        "path": path,
        "evidence": evidence,
    }


def _result(errors, warnings, facts, not_assessed=()):
    return {
        "passed": not errors and not not_assessed,
        "errors": errors,
        "warnings": warnings,
        "not_assessed": list(not_assessed),
        "facts": facts,
    }


def _unassessed(check_ids, reason):
    return [_issue(check_id, "check.not_assessed", reason) for check_id in check_ids]


def _unreadable_result(errors, warnings, facts, inventory_checked=False, not_assessed=()):
    # No content-dependent item has run, and applicability cannot be inferred.
    observed = {item['check_id'] for item in errors + warnings + list(not_assessed)}
    if inventory_checked:
        observed.add('SCK-S07')
    pending = ['SCK-S%02d' % n for n in range(2, 11) if 'SCK-S%02d' % n not in observed]
    return _result(errors, warnings, facts, list(not_assessed) +
                   _unassessed(pending, 'Target content could not be inspected.'))


def _relative(path, root):
    try:
        return str(path.relative_to(root))
    except ValueError:
        return "."


def _inside(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _inventory(root, errors):
    """Return regular bundled resources while recording walk and symlink facts."""
    resources = []

    def walk_error(exc):
        errors.append(
            _issue("SCK-S01", "skill.directory.unreadable", type(exc).__name__, ".")
        )

    for current, directory_names, file_names in os.walk(
        str(root), followlinks=False, onerror=walk_error
    ):
        current_path = Path(current)
        for name in list(directory_names):
            path = current_path / name
            try:
                symbolic = path.is_symlink()
            except OSError as exc:
                walk_error(exc)
                symbolic = True
            if symbolic:
                errors.append(
                    _issue(
                        "SCK-S07",
                        "path.symlink",
                        "symbolic link",
                        _relative(path, root),
                    )
                )
                directory_names.remove(name)
        for name in file_names:
            path = current_path / name
            try:
                if path.is_symlink():
                    errors.append(
                        _issue(
                            "SCK-S07",
                            "path.symlink",
                            "symbolic link",
                            _relative(path, root),
                        )
                    )
                    continue
                if not path.is_file():
                    continue
            except OSError as exc:
                walk_error(exc)
                continue
            relative = path.relative_to(root)
            if (
                relative.parts[0] in RESOURCE_DIRECTORIES
                and "__pycache__" not in relative.parts
                and path.suffix != ".pyc"
            ):
                resources.append(str(relative))
    return sorted(resources)


def _link_target(raw_target):
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        target = target.split(maxsplit=1)[0]
        if " " in raw_target:
            # A bare target containing whitespace was split mid-path; the
            # link syntax is ambiguous, so leave it to semantic review (L09)
            # instead of reporting a fabricated fragment as missing.
            return None
    return target


def _scan_fences(text):
    """Return visible lines and the first unsupported container-fence line.

    Common flat fences and indented code are excluded. An ordinary fence may
    end at EOF. Explicit quote/list fences need container parsing: retain only
    the known prefix and hand the remaining context to semantic review.
    """
    fence = None
    uncertain_at = None
    lines = []
    for index, raw in enumerate(text.splitlines(), start=1):
        line = raw.expandtabs(4)
        if uncertain_at is not None:
            lines.append('')
            continue
        marker = re.match(r' {0,3}(`{3,}|~{3,})(.*)$', line)
        if fence:
            if (marker and marker.group(1)[0] == fence[0]
                    and len(marker.group(1)) >= len(fence)
                    and not marker.group(2).strip()):
                fence = None
            lines.append('')
            continue
        if line.startswith('    '):
            lines.append('')
            continue
        if re.match(r' {0,3}(?:(?:> ?|[-+*] +|[0-9]+[.)] +))+(`{3,}|~{3,})', line):
            uncertain_at = index
            lines.append('')
            continue
        if marker and not (marker.group(1)[0] == '`' and '`' in marker.group(2)):
            fence = marker.group(1)
            lines.append('')
            continue
        lines.append(raw)
    return lines, uncertain_at


def _canonical_state(body):
    if body is None:
        return None
    lines, uncertain_at = _scan_fences(body)
    if any(line.strip() == CANONICAL_MARKER for line in lines):
        return True
    return None if uncertain_at is not None else False


def _body_structure(body, start_line):
    """Cited observations for L04/L05; no required heading or field vocabulary."""
    lines, uncertain_at = _scan_fences(body)
    headings, fields = [], []
    for index, line in enumerate(lines, start=start_line):
        heading = re.match(r' {0,3}#{1,6} +(.+?) *$', line)
        field = re.match(r' {0,3}[-+*] +([^:\n]+):([^\n]*)$', line)
        if heading:
            headings.append({'line': index, 'text': heading.group(1)})
        if field:
            fields.append({'line': index, 'label': field.group(1).strip(),
                           'has_value': bool(field.group(2).strip())})
    return {'headings': headings, 'fields': fields,
            'unassessed_from_line': (start_line + uncertain_at - 1
                                     if uncertain_at is not None else None)}


def _simple_markdown_link_targets(text):
    """Yield only unambiguous links outside common code spans and fences.

    A bare target followed by more content before the closing parenthesis
    was split mid-path (spaces) or carries a title; without angle brackets
    the syntax is ambiguous, so such matches are skipped and left to
    semantic review (L09) rather than reported as fabricated fragments.
    """
    lines, _ = _scan_fences(text)
    for line in lines:
        visible = INLINE_CODE_PATTERN.sub("", line)
        for match in SIMPLE_LINK_PATTERN.finditer(visible):
            first = match.group(1)
            if first.startswith("<"):
                yield first
                continue
            inner = match.group(0)
            inner = inner[inner.index("(") + 1 :].rstrip(")").rstrip()
            if inner != first:
                continue
            yield first


def _inline_code_path_candidates(text):
    """Yield inline code span contents as path-shaped route candidates.

    Fenced code stays excluded: a command inside a fence is an example of
    use, not a declaration of a bundled dependency.
    """
    lines, _ = _scan_fences(text)
    for line in lines:
        for match in INLINE_CODE_PATTERN.finditer(line):
            content = match.group(0).strip("`").strip()
            if content:
                yield content


def _table_cell_path_candidates(text):
    """Yield bare table-cell tokens carrying a path prefix as route candidates.

    Only cells of lines containing '|' qualify, and the token must contain
    a path prefix ('/'): a bare filename is ambiguous against same-named
    files in other directories, so it stays with L09 semantic review.
    """
    lines, _ = _scan_fences(text)
    for line in lines:
        if "|" not in line:
            continue
        for cell in line.split("|"):
            token = cell.strip().strip("`").strip()
            if "/" in token:
                yield token


def _resolve_inline_code_route(root, source, content):
    """Resolve a declared path to a bundled regular file, or None.

    Inline-code and table-cell declarations only add S08 routes. Misses,
    escapes, absolute paths, and ambiguous forms produce no finding and are
    left to L09 semantic review; a declared route never enqueues further
    traversal.
    """
    if (
        any(character.isspace() for character in content)
        or content.startswith(("#", "<", "//"))
        or content.lower().startswith("file:")
        or EXTERNAL_PATTERN.match(content)
    ):
        return None
    path_part = content.split("#", 1)[0].split("?", 1)[0]
    if not path_part:
        return None
    target = Path(unquote(path_part))
    if target.is_absolute():
        return None
    for base in (source.parent, root):
        candidate = base / target
        try:
            if any(
                path.is_symlink()
                for path in (candidate, *candidate.parents)
                if path != root and _inside(path, root)
            ):
                continue
            resolved = candidate.resolve()
            if (
                _inside(resolved, root)
                and resolved.is_file()
                and not resolved.is_symlink()
            ):
                return str(resolved.relative_to(root))
        except (OSError, ValueError, RuntimeError):
            continue
    return None


def _collect_references(root, skill_file, skill_text, errors, not_assessed, semantic_read_files):
    """Follow only explicit local Markdown links, starting at SKILL.md."""
    queue = [(skill_file, skill_text)]
    visited = set()
    reachable = set()
    declared_routes = set()

    while queue:
        source, supplied_text = queue.pop(0)
        try:
            source_key = source.resolve()
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(
                _issue(
                    "SCK-S06",
                    "reference.path.unreadable",
                    type(exc).__name__,
                    _relative(source, root),
                )
            )
            continue
        if source_key in visited:
            continue
        visited.add(source_key)
        try:
            text = (
                supplied_text
                if supplied_text is not None
                else source.read_text(encoding="utf-8-sig")
            )
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(
                _issue(
                    "SCK-S06",
                    "reference.unreadable",
                    type(exc).__name__,
                    _relative(source, root),
                )
            )
            continue

        _, uncertain_at = _scan_fences(text)
        if uncertain_at is not None:
            for check_id in ('SCK-S06', 'SCK-S08'):
                not_assessed.append(_issue(
                    check_id, 'check.not_assessed',
                    'Container fence at line %s; remaining routes require L09 context review.' % uncertain_at,
                    _relative(source, root)))
        for raw_target in _simple_markdown_link_targets(text):
            target = _link_target(raw_target)
            if target is None:
                continue
            if target.lower().startswith("file:"):
                errors.append(
                    _issue(
                        "SCK-S06",
                        "reference.path.absolute",
                        target,
                        _relative(source, root),
                    )
                )
                continue
            if (
                not target
                or target.startswith(("#", "//"))
                or EXTERNAL_PATTERN.match(target)
            ):
                continue
            # Split the URL fragment and query before decoding literal
            # filename characters; neither is part of the local path.
            path_part = target.split("#", 1)[0].split("?", 1)[0]
            target_path = Path(unquote(path_part))
            if target_path.is_absolute():
                errors.append(
                    _issue(
                        "SCK-S06",
                        "reference.path.absolute",
                        target,
                        _relative(source, root),
                    )
                )
                continue
            candidate = source.parent / target_path
            try:
                if any(path.is_symlink() for path in (candidate, *candidate.parents) if path != root and _inside(path, root)):
                    errors.append(
                        _issue(
                            "SCK-S06",
                            "reference.path.symlink",
                            target,
                            _relative(source, root),
                        )
                    )
                    continue
                resolved = candidate.resolve()
                regular = resolved.is_file() and not resolved.is_symlink()
            except (OSError, ValueError, RuntimeError) as exc:
                errors.append(
                    _issue(
                        "SCK-S06",
                        "reference.path.unreadable",
                        type(exc).__name__,
                        _relative(source, root),
                    )
                )
                continue
            if not _inside(resolved, root):
                errors.append(
                    _issue(
                        "SCK-S06",
                        "reference.path.escape",
                        target,
                        _relative(source, root),
                    )
                )
                continue
            if not regular:
                errors.append(
                    _issue(
                        "SCK-S06",
                        "reference.missing",
                        target,
                        _relative(source, root),
                    )
                )
                continue
            try:
                # A binary open/read proves readability without importing or
                # executing scripts, or imposing UTF-8 on binary assets.
                with resolved.open('rb') as resource:
                    resource.read(1)
            except OSError as exc:
                errors.append(_issue('SCK-S06', 'reference.path.unreadable',
                                     type(exc).__name__ + ': ' + target, _relative(source, root)))
                continue
            relative = str(resolved.relative_to(root))
            reachable.add(relative)
            if resolved.suffix.lower() == ".md":
                if relative in semantic_read_files:
                    queue.append((resolved, None))
                else:
                    for check_id in ('SCK-S06', 'SCK-S08'):
                        not_assessed.append(_issue(
                            check_id, 'check.not_assessed',
                            'Content withheld by S10; nested routes were not inspected.', relative))
        for content in _inline_code_path_candidates(text):
            routed = _resolve_inline_code_route(root, source, content)
            if routed is not None:
                declared_routes.add(routed)
        for token in _table_cell_path_candidates(text):
            routed = _resolve_inline_code_route(root, source, token)
            if routed is not None:
                declared_routes.add(routed)
    return sorted(reachable), sorted(declared_routes)


def _metadata_strings(metadata, placeholder):
    """Visit safe YAML strings, including extensions, without alias recursion."""
    pending = [('frontmatter', metadata)]
    visited = set()
    while pending:
        path, value = pending.pop()
        if isinstance(value, str):
            yield path, value
        elif isinstance(value, (dict, list, tuple, set)):
            if id(value) in visited:
                continue
            visited.add(id(value))
            if isinstance(value, dict):
                for index, (key, child) in reversed(list(enumerate(value.items()))):
                    # Never reproduce a placeholder-like key as evidence text.
                    label = key if isinstance(key, str) and not placeholder.search(key) else '<key %s>' % index
                    pending.append((path + '.' + label, child))
                    pending.append((path + '.<key %s>' % index, key))
            else:
                values = sorted(value, key=repr) if isinstance(value, set) else value
                pending.extend((path + '[%s]' % index, child)
                               for index, child in reversed(list(enumerate(values))))


def _placeholder_candidates(metadata, body, body_start_line):
    candidates = []
    placeholder = re.compile(r"\b(?:TODO|TBD)\b|\{\{[^}]+\}\}", re.IGNORECASE)
    if metadata is not None:
        for field, value in _metadata_strings(metadata, placeholder):
            if placeholder.search(value):
                candidates.append(_issue('SCK-S05', 'canonical.placeholder.candidate',
                                         'frontmatter field: ' + field))
    lines = {body_start_line + body.count('\n', 0, match.start())
             for match in placeholder.finditer(body)}
    for line in sorted(lines):
        candidates.append(_issue('SCK-S05', 'canonical.placeholder.candidate',
                                 'SKILL.md line %s: possible slot (value redacted)' % line))

    return candidates


def _codex_metadata(root, facts, errors, not_assessed):
    """Read only scan-cleared metadata; keep values out of diagnostic messages."""
    relative = "agents/openai.yaml"
    path = root / relative
    facts["codex_metadata"] = None
    if not path.exists() and not path.is_symlink():
        # The interface file is optional, including when codex is explicit.
        facts["codex_metadata"] = {}
        return
    if relative not in facts["semantic_read_files"]:
        not_assessed.append(_issue("SCK-C01", "check.not_assessed",
                                   "Metadata was not cleared by the scan.", relative))
        return
    # A parent could be a symbolic link, even if the leaf is not.
    if any(p.is_symlink() for p in (path, path.parent)) or not _inside(path.resolve(), root):
        not_assessed.append(_issue("SCK-C01", "check.not_assessed",
                                   "Metadata path is not contained and regular.", relative))
        return
    try:
        metadata = parse_yaml_mapping(path.read_text(encoding="utf-8"), relative)
    except FrontmatterUnavailable as exc:
        not_assessed.append(_issue("SCK-C01", "check.not_assessed", str(exc), relative))
        return
    except (FrontmatterError, OSError, UnicodeError) as exc:
        errors.append(_issue("SCK-C01", "codex.metadata.invalid",
                             str(exc) if isinstance(exc, FrontmatterError) else type(exc).__name__, relative))
        return

    def invalid(field, expectation):
        errors.append(_issue("SCK-C01", "codex.metadata.invalid",
                             "%s: expected %s" % (field, expectation), relative))

    # Return only supported fields; do not reflect arbitrary extension values.
    supported = {}
    for section in ("interface", "policy", "dependencies"):
        value = metadata.get(section, {})
        if not isinstance(value, dict):
            invalid(section, "mapping")
            continue
        supported[section] = {}
        if section == "interface":
            for field in ("display_name", "short_description", "default_prompt"):
                if field not in value:
                    continue
                item = value[field]
                if not isinstance(item, str) or not item.strip():
                    invalid("interface." + field, "nonempty string")
                else:
                    supported[section][field] = item
            prompt = supported[section].get("default_prompt")
            name = facts.get("name")
            if prompt is not None:
                if name is None:
                    not_assessed.append(_issue("SCK-C01", "check.not_assessed",
                                               "Skill name unavailable for default_prompt comparison.", relative))
                elif re.findall(r"\$([a-z0-9]+(?:-[a-z0-9]+)*)", prompt) != [name]:
                    invalid("interface.default_prompt", "exactly one invocation of the declared Skill name")
        elif section == "policy" and "allow_implicit_invocation" in value:
            item = value["allow_implicit_invocation"]
            if type(item) is not bool:
                invalid("policy.allow_implicit_invocation", "YAML boolean")
            else:
                supported[section]["allow_implicit_invocation"] = item
        elif section == "dependencies" and "tools" in value:
            items = value["tools"]
            if not isinstance(items, list):
                invalid("dependencies.tools", "list")
                continue
            supported[section]["tools"] = []
            for index, item in enumerate(items):
                prefix = "dependencies.tools[%s]" % index
                if not isinstance(item, dict):
                    invalid(prefix, "mapping")
                    continue
                tool = {}
                for field in ("type", "value"):
                    if not isinstance(item.get(field), str) or not item[field].strip():
                        invalid(prefix + "." + field, "nonempty string")
                    else:
                        tool[field] = item[field]
                supported[section]["tools"].append(tool)
    facts["codex_metadata"] = supported


def validate_skill(skill_dir, operation="check", profile="auto"):
    """Return deterministic static facts without executing target content."""
    if operation not in ("create", "check"):
        raise ValueError("operation must be create or check")
    if profile not in PROFILES:
        raise ValueError("unsupported profile")

    selected = Path(skill_dir)
    errors, warnings, not_assessed = [], [], []
    facts = {
        "operation": operation,
        "profile": profile if profile != "auto" else "generic",
        "root": str(selected.absolute()),
        "name": None,
        "description": None,
        "canonical_sck_format": None,
        "body_structure": None,
        "reachable_resources": [],
        "declared_routes": [],
        "resource_files": [],
        "credential_candidates": [],
        "credential_hit_files": [],
        "credential_scan": {},
        "semantic_read_files": [],
    }
    try:
        if not selected.is_dir():
            errors.append(
                _issue("SCK-S01", "skill.directory.missing", "not a directory", ".")
            )
            return _unreadable_result(errors, warnings, facts)
        if selected.is_symlink():
            errors.append(_issue("SCK-S07", "path.symlink", "symbolic root", "."))
            return _unreadable_result(errors, warnings, facts)
        root = selected.resolve()
    except (OSError, ValueError, RuntimeError) as exc:
        errors.append(
            _issue("SCK-S01", "skill.directory.unreadable", type(exc).__name__, ".")
        )
        return _unreadable_result(errors, warnings, facts)
    facts["root"] = str(root)
    if profile == "auto":
        # Observe only the local entry, never follow a linked agents directory.
        agents = root / "agents"
        facts["profile"] = ("codex" if not agents.is_symlink() and
                            os.path.lexists(str(agents / "openai.yaml")) else "generic")

    resources = _inventory(root, errors)
    facts["resource_files"] = resources
    try:
        hits, hit_files, coverage = _credential_scan(root)
    except OSError as exc:
        not_assessed.append(
            _issue("SCK-S10", "check.not_assessed", "scan failed: %s" % type(exc).__name__)
        )
    else:
        facts["credential_candidates"] = hits
        facts["credential_hit_files"] = hit_files
        facts["credential_scan"] = coverage
        facts["semantic_read_files"] = [path for path, entry in coverage.items()
                                        if entry["status"] == "scanned" and path not in hit_files]
        for path, entry in coverage.items():
            if entry["status"] == "not_assessed":
                not_assessed.append(_issue("SCK-S10", "check.not_assessed", entry["reason"], path))
        for hit in hits:
            family = hit["family"]
            pii = family.startswith("cn-")
            code = "content.pii.candidate" if pii else "content.credential.candidate"
            warnings.append(
                _issue(
                    "SCK-S10",
                    code,
                    "%s at line %s; masked (%s)" % (family, hit["line"], hit["mask"]),
                    hit["path"],
                )
            )
    skill_file = root / "SKILL.md"
    try:
        if not skill_file.is_file() or skill_file.is_symlink():
            errors.append(
                _issue("SCK-S01", "skill.file.missing", "not a regular file")
            )
            return _unreadable_result(errors, warnings, facts, inventory_checked=True,
                                      not_assessed=not_assessed)
        if "SKILL.md" not in facts["semantic_read_files"]:
            scan = facts["credential_scan"].get("SKILL.md", {})
            if scan.get("reason") in ("invalid UTF-8", "binary content"):
                errors.append(_issue("SCK-S01", "skill.file.encoding", scan["reason"]))
            elif scan.get("status") != "scanned":
                not_assessed.append(_issue("SCK-S01", "check.not_assessed",
                                           "Entry content withheld by S10."))
            return _unreadable_result(errors, warnings, facts, inventory_checked=True,
                                      not_assessed=not_assessed)
        text = skill_file.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(_issue("SCK-S01", "skill.file.encoding", type(exc).__name__))
        return _unreadable_result(errors, warnings, facts, inventory_checked=True,
                                  not_assessed=not_assessed)

    try:
        metadata, body = parse_frontmatter(text)
    except FrontmatterUnavailable as exc:
        # Delimiters were checked before parser availability/construction failed.
        metadata, body = None, _frontmatter_parts(text)[1]
        pending = ["SCK-S02", "SCK-S03", "SCK-S04"]
        if _canonical_state(body) is not False:
            pending.append("SCK-S05")
        not_assessed.extend(
            _issue(check_id, "frontmatter.not_assessed", str(exc))
            for check_id in pending
        )
    except FrontmatterError as exc:
        errors.append(_issue("SCK-S02", "frontmatter.invalid", str(exc)))
        metadata = None
        try:
            body = _frontmatter_parts(text)[1]
        except FrontmatterError:
            body = None
        pending = ['SCK-S03', 'SCK-S04']
        if body is None:
            pending.extend(['SCK-S05', 'SCK-S09'])
        elif _canonical_state(body) is not False:
            pending.append('SCK-S05')
        not_assessed.extend(_unassessed(pending, 'Frontmatter is invalid; dependent checks did not run.'))

    name_value = metadata.get("name", "") if metadata is not None else ""
    description_value = metadata.get("description", "") if metadata is not None else ""
    name = name_value if isinstance(name_value, str) else ""
    description = (
        description_value.strip() if isinstance(description_value, str) else ""
    )
    canonical = _canonical_state(body)
    if body is not None:
        body_start_line = len(text.splitlines()) - len(body.splitlines()) + 1
        facts['body_structure'] = _body_structure(body, body_start_line)
        uncertain_line = facts['body_structure']['unassessed_from_line']
        if uncertain_line is not None:
            pending = ['SCK-S09']
            if canonical is None:
                pending.append('SCK-S05')
            not_assessed.extend(_unassessed(
                pending, 'Container fence at SKILL.md line %s; remaining structure requires context review.'
                % uncertain_line))
    facts.update(
        name=name or None,
        description=description or None,
        canonical_sck_format=canonical,
    )

    if metadata is not None and not name.strip():
        errors.append(_issue("SCK-S02", "frontmatter.name.missing", "name: expected nonempty string"))
    elif name and (len(name) > 64 or (name.isascii() and not NAME_PATTERN.fullmatch(name))):
        errors.append(_issue("SCK-S03", "frontmatter.name.invalid", name))
    elif name and not name.isascii():
        not_assessed.append(_issue("SCK-S03", "check.not_assessed",
                                   "Non-ASCII name validity requires a declared host contract."))
    if metadata is not None and "compatibility" in metadata:
        compatibility = metadata["compatibility"]
        if not isinstance(compatibility, str) or len(compatibility) > 500:
            errors.append(_issue("SCK-S02", "frontmatter.compatibility.invalid",
                                 "compatibility: expected string of at most 500 characters"))
    if metadata is not None and not description:
        errors.append(
            _issue(
                "SCK-S02",
                "frontmatter.description.missing",
                "description: expected nonempty string",
            )
        )
    if isinstance(description_value, str) and len(description_value) > 1024:
        errors.append(_issue('SCK-S02', 'frontmatter.description.too_long',
                             'description: %s characters; maximum 1024' % len(description_value)))
    if name.strip() and root.name != name:
        mismatch = _issue(
            "SCK-S04",
            "skill.name.directory_mismatch",
            "%s != %s" % (root.name, name),
            ".",
        )
        (errors if operation == "create" else warnings).append(mismatch)

    reachable, declared_routes = _collect_references(
        root, skill_file, text, errors, not_assessed,
        set(facts["semantic_read_files"]))
    facts["reachable_resources"] = reachable
    facts["declared_routes"] = declared_routes
    for orphan in sorted(set(resources) - set(reachable) - set(declared_routes)):
        warnings.append(_issue("SCK-S08", "resource.orphan", "not reachable", orphan))
    if canonical is True:
        warnings.extend(_placeholder_candidates(metadata, body, body_start_line))
    if facts["profile"] == "codex":
        _codex_metadata(root, facts, errors, not_assessed)
    return _result(errors, warnings, facts, not_assessed)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_dir")
    parser.add_argument("--operation", choices=("create", "check"), default="check")
    parser.add_argument("--profile", choices=PROFILES, default="auto")
    args = parser.parse_args(argv)
    result = validate_skill(args.skill_dir, args.operation, args.profile)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
