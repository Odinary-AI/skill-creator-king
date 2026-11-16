#!/usr/bin/env python3
"""Validate and render an agent-assessed SCK report, without reading its target.

This is a report consumer, not an automatic semantic reviewer. Invalid input
returns an operational error, never a quality verdict.

With --facts, original observations are reconciled against the complete validator
result, and semantic citations against readable/reported files. The renderer
still never reads the target itself or judges disposition semantics.
"""
import argparse
import copy
import json
from collections import Counter
from pathlib import Path


SCHEMA = "skill-creator-king.report.v2"
BASE_IDS = ["SCK-S%02d" % n for n in range(1, 11)] + ["SCK-L%02d" % n for n in range(1, 15)]
CODEX_IDS = ["SCK-C%02d" % n for n in range(1, 3)]
STATUSES = ("pass", "gap", "advisory", "not_applicable", "not_assessed")
# JSON keeps the full boundary claim; user-facing lines use the short template form.
CLAIM = "实际运行：未评估（SCK 只做静态检查）。静态检查不证明运行行为、安全、宿主验收、发布就绪或人工批准。"
CLAIM_LINE = "实际运行：未评估（SCK 只做静态检查）"
LABELS = {"pass": "通过", "gap": "必修", "advisory": "建议", "not_applicable": "不适用", "not_assessed": "未评估"}
# 结论句由判词映射生成，不让模型自由书写，避免说法与判词打架。
VERDICT_SENTENCE = {
    "静态合规": "没有必须改的书面缺口",
    "静态合规但有建议": "没有必须改的书面缺口，另有可缓改项",
    "静态不合规": "有必须改的书面缺口",
    "无法判定": "有一项必需检查没判成，先别下结论",
}
OPERATION_LABEL = {"create": "创建后自检", "check": "只读检查"}
SEPARATOR = "—— 以下为审计明细，供维护者追溯 ——"


def require(condition, path, expected):
    if not condition:
        raise ValueError("%s: expected %s" % (path, expected))


def string(value, path):
    require(isinstance(value, str) and bool(value.strip()), path, "nonempty string")


def array(value, path):
    require(isinstance(value, list), path, "array")


def normalize(source):
    require(isinstance(source, dict), "$", "object")
    report = copy.deepcopy(source)
    require(report.get("schema") == SCHEMA, "schema", SCHEMA)
    for field in ("target", "read_scope", "next_action"):
        string(report.get(field), field)
    require(report.get("profile") in ("generic", "workbuddy", "codex"), "profile", "resolved profile")
    require(report.get("operation") in ("create", "check"), "operation", "create or check")
    require(report.get("completed") is True, "completed", "true; otherwise return an operational error")
    reads = report.get("files_read")
    if reads is not None:
        array(reads, "files_read")
        for index, value in enumerate(reads):
            string(value, "files_read[%s]" % index)
            require(
                not Path(value).is_absolute() and "\\" not in value and ".." not in Path(value).parts,
                "files_read[%s]" % index,
                "target-relative POSIX path",
            )
        require(len(reads) == len(set(reads)), "files_read", "unique paths")
    checks = report.get("checks")
    array(checks, "checks")
    expected_ids = BASE_IDS + (CODEX_IDS if report["profile"] == "codex" else [])
    ids = []
    has_gap = has_advisory = has_unknown = False
    for i, check in enumerate(checks):
        prefix = "checks[%s]" % i
        require(isinstance(check, dict), prefix, "object")
        ids.append(check.get("id"))
        string(check.get("title"), prefix + ".title")
        require(check.get("status") in STATUSES, prefix + ".status", "/".join(STATUSES))
        require(type(check.get("required")) is bool, prefix + ".required", "boolean")
        string(check.get("reason"), prefix + ".reason")
        for field in ("findings", "unassessed", "observations"):
            array(check.get(field), prefix + "." + field)
        dispositions = []
        for j, item in enumerate(check["findings"]):
            loc = prefix + ".findings[%s]" % j
            require(isinstance(item, dict), loc, "object")
            require(item.get("disposition") in ("gap", "advisory"), loc + ".disposition", "gap or advisory")
            require(item.get("severity") in ("blocker", "major", "minor", "info"), loc + ".severity", "blocker/major/minor/info")
            require((item.get("check_type"), item.get("evidence_strength")) in
                    (("deterministic", "confirmed"), ("semantic", "inferred")), loc, "matching evidence kind and strength")
            for field in ("code", "file", "evidence", "impact", "recommendation"):
                string(item.get(field), loc + "." + field)
            require(item.get("line") is None or (type(item["line"]) is int and item["line"] > 0), loc + ".line", "positive integer or null")
            if item["severity"] == "blocker":
                for field in ("unbounded_scope", "irreversible_consequence"):
                    string(item.get(field), loc + "." + field)
            dispositions.append(item["disposition"])
        for j, item in enumerate(check["unassessed"]):
            loc = prefix + ".unassessed[%s]" % j
            require(isinstance(item, dict), loc, "object")
            for field in ("reason", "needed_evidence"):
                string(item.get(field), loc + "." + field)
            require(type(item.get("material")) is bool, loc + ".material", "boolean")
            require(not check["required"] or item["material"], loc + ".material",
                    "true for an unresolved applicable required assessment")
        for j, item in enumerate(check["observations"]):
            loc = prefix + ".observations[%s]" % j
            require(isinstance(item, dict) and isinstance(item.get("original"), dict), loc, "original static observation object")
            for field in ("check_id", "code", "path", "evidence", "message"):
                string(item["original"].get(field), loc + ".original." + field)
            require(item["original"]["check_id"] == check["id"], loc, "observation belonging to this check")
            string(item.get("disposition"), loc + ".disposition")
        status = ("not_assessed" if check["unassessed"] else "gap" if "gap" in dispositions
                  else "advisory" if dispositions else check["status"])
        require(status == check["status"], prefix + ".status", "classification preserving findings and uncertainty: " + status)
        if status in ("gap", "advisory", "not_assessed"):
            require(bool(dispositions or check["unassessed"]), prefix, "supporting finding or unassessed item")
        if "gap" in dispositions:
            require(check["required"], prefix + ".required", "true for a required gap")
        has_gap |= "gap" in dispositions
        has_advisory |= "advisory" in dispositions
        has_unknown |= check["required"] and any(x["material"] for x in check["unassessed"])
    require(len(ids) == len(set(ids)) and set(ids) == set(expected_ids), "checks", "every selected-profile ID exactly once")
    decisions = report.get("decisions")
    if decisions is None:
        decisions = []
    array(decisions, "decisions")
    require(len(decisions) <= 3, "decisions", "at most 3 items")
    # 已经判为通过的项没有可决定的内容；有待定假设的项不应同时列在通过块里。
    status_by_id = {c["id"]: c["status"] for c in checks}
    for i, item in enumerate(decisions):
        loc = "decisions[%s]" % i
        require(isinstance(item, dict), loc, "object")
        for field in ("id", "question", "if_a", "if_b", "default"):
            string(item.get(field), loc + "." + field)
        require(item["id"] in expected_ids, loc + ".id", "a selected check ID")
        require(status_by_id[item["id"]] != "pass", loc + ".id", "a check that is not classified pass")
    report["decisions"] = decisions
    for field in ("limitations", "changes"):
        array(report.get(field), field)
        for i, value in enumerate(report[field]):
            string(value, "%s[%s]" % (field, i))
    verdict = ("无法判定" if has_unknown else "静态不合规" if has_gap else
               "静态合规但有建议" if has_advisory else "静态合规")
    report["verdict"] = verdict
    report["coverage"] = {s: sum(c["status"] == s for c in checks) for s in STATUSES}
    report["claim_boundary"] = CLAIM
    report["checks"] = sorted(checks, key=lambda c: expected_ids.index(c["id"]))
    return report


def _same_target(left, right):
    """Compare two target paths without reading either one."""
    try:
        return Path(str(left)).expanduser().resolve() == Path(str(right)).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        return False


def validate_evidence(report, facts):
    """Reconcile observations and semantic citations; never read the target."""
    require(isinstance(facts, dict), "facts", "object")
    originals = []
    for category in ("errors", "warnings", "not_assessed"):
        entries = facts.get(category)
        array(entries, "facts." + category)
        require(all(isinstance(item, dict) for item in entries), "facts." + category, "observation objects")
        originals.extend(entries)
    key = lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False, allow_nan=False)
    supplied = [item["original"] for check in report["checks"] for item in check["observations"]]
    require(Counter(map(key, originals)) == Counter(map(key, supplied)), "observations",
            "every validator error, warning and not_assessed observation unchanged, with matching multiplicity")
    payload = facts.get("facts")
    require(isinstance(payload, dict), "facts", "validator facts object")
    require(_same_target(report.get("target"), payload.get("root")),
            "facts.root", "same target as the report")
    require(payload.get("operation") == report.get("operation"),
            "facts.operation", "same operation as the report")
    require(payload.get("profile") == report.get("profile"),
            "facts.profile", "same profile as the report")
    eligible = payload.get("semantic_read_files")
    require(
        isinstance(eligible, list) and all(isinstance(item, str) for item in eligible),
        "facts.semantic_read_files",
        "string array",
    )
    reads = report.get("files_read")
    require(isinstance(reads, list), "files_read", "required when --facts is supplied")
    allowed = set(eligible)
    for value in reads:
        require(value in allowed, "files_read", "subset of facts.semantic_read_files")
    cited = set(reads)
    for check_index, check in enumerate(report["checks"]):
        for item_index, item in enumerate(check["findings"]):
            if item["check_type"] == "semantic":
                require(
                    item["file"] in cited,
                    "checks[%s].findings[%s].file" % (check_index, item_index),
                    "a cited file in files_read",
                )


def render_markdown(report, verbosity="full"):
    report = normalize(report)
    checks = report["checks"]
    counts = " · ".join("%s %s" % (n, LABELS[s])
                        for s, n in report["coverage"].items() if n)
    # 前两行回答「查了谁、要不要动」；判词句由固定映射生成，避免说法与判词打架。
    # 项数只报数字：C01–C02 是目标带 agents/openai.yaml 时随 profile 启用的补充项，
    # 它们检查该文件与调用策略，不代表读者的运行宿主。
    scope = "%s 项" % len(checks)
    lines = [
        "静态合规报告",
        "",
        "检查对象：%s（%s · %s）" % (
            report["target"], OPERATION_LABEL[report["operation"]], scope),
        "结论：%s——%s（%s 项：%s）" % (
            VERDICT_SENTENCE[report["verdict"]], report["verdict"], len(checks), counts),
        "",
    ]
    # 纯检查且无变更证据时，修改动作只是「若要改」的选项，不是已执行的动作。
    unchanged = report["operation"] == "check" and not report["changes"]
    for disposition, label in (("gap", "必修项（不修=静态不合规）"), ("advisory", "建议项（不影响合格判定）")):
        items = [(c, f) for c in checks for f in c["findings"] if f["disposition"] == disposition]
        lines.append(label + ("：" if items else "：无"))
        for check, finding in items:
            location = finding["file"] + (" 第 %s 行" % finding["line"] if finding["line"] else "")
            kind = "脚本事实" if finding["check_type"] == "deterministic" else "语义推断"
            # 用户语言三段：位置＋证据＋影响一句话，然后最小修改动作；严重度留给 JSON。
            statement = "%s：%s，%s。" % (location, finding["evidence"].rstrip("。"),
                                         finding["impact"].rstrip("。"))
            title = check["title"]
            tail = "；本次未改动。" if unchanged else "。"
            lines.append("- %s（%s；%s）：%s怎么改：%s%s" %
                         (title, check["id"], kind, statement,
                          finding["recommendation"].rstrip("。"), tail))
        lines.append("")
    for status, heading in (("not_applicable", "不适用"), ("not_assessed", "未评估")):
        items = [c for c in checks if c["status"] == status]
        lines.append(heading + ("：" if items else "：无"))
        for c in items:
            lines.append("- %s（%s）：%s" % (c["title"], c["id"], c["reason"]))
            for item in c["unassessed"]:
                lines.append("  %s；所需证据：%s；%s" %
                             (item["reason"], item["needed_evidence"],
                              "会影响整体结论" if item["material"] else "不影响整体结论"))
        lines.append("")
    limitations = list(report["limitations"])
    if report["profile"] == "codex":
        limitations.append("%s 项含 C01–C02 两项补充检查，由目标内的 agents/openai.yaml 触发，与本机运行宿主无关。" % len(checks))
    lines.append("限制：" if limitations else "限制：无")
    lines.extend("- " + x for x in limitations)
    lines.extend(["", CLAIM_LINE,
                  "待你决定：" if report["decisions"] else "待你决定：无"])
    titles = {c["id"]: c["title"] for c in checks}
    for item in report["decisions"]:
        lines.append("- %s（%s）：%s；%s；%s；%s。" % (
            titles[item["id"]], item["id"], item["question"].rstrip("。"),
            item["if_a"].rstrip("。"), item["if_b"].rstrip("。"), item["default"].rstrip("。")))
    lines.extend(["接下来怎么做：" + report["next_action"], "", SEPARATOR, ""])
    lines.append("读取范围：" + report["read_scope"])
    passed = [c for c in checks if c["status"] == "pass"]
    lines.append("通过 %s 项：%s" % (len(passed), " · ".join("%s（%s）" % (c["title"], c["id"]) for c in passed)))
    if verbosity == "full" and passed:
        groups = {}
        for c in passed:
            groups.setdefault(c["reason"].rstrip("。"), []).append("%s（%s）" % (c["title"], c["id"]))
        lines.extend(["", "通过项依据："] +
                     ["- %s：%s" % (reason, " · ".join(names)) for reason, names in groups.items()])
    observations = [(c, o) for c in checks for o in c["observations"]]
    if observations:
        lines.extend(["", "脚本观察处置："])
        grouped = {}
        for check, item in observations:
            grouped.setdefault(check["id"], []).append(item)
        for cid, items in grouped.items():
            if len(items) == 1:
                original = items[0]["original"]
                # 根目录属性没有可读路径，不输出「.」占位。
                where = "" if original["path"] in ("", ".") else "，%s" % original["path"]
                lines.append("- %s%s：%s；原始观察：%s" %
                             (cid, where, items[0]["disposition"], original["evidence"]))
                continue
            dispositions = []
            for item in items:
                if item["disposition"] not in dispositions:
                    dispositions.append(item["disposition"])
            paths = []
            for item in items:
                if item["original"]["path"] not in paths:
                    paths.append(item["original"]["path"])
            # 同类观察合并成一行；逐条明细留在 JSON，Markdown 从 34 行降到 1 行。
            lines.append("- %s：%s 条观察合并披露，处置：%s；代表路径：%s；逐条见 JSON。" % (
                cid, len(items),
                "；".join(dispositions[:3]) + ("等 %s 类" % len(dispositions) if len(dispositions) > 3 else ""),
                "、".join(paths[:3])))
    if report["changes"]:
        lines.extend(["", "变更证据："] + ["- " + x for x in report["changes"]])
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--verbosity", choices=("concise", "full"), default="full")
    parser.add_argument("--facts", help="complete validator JSON; reconcile observations and check citations")
    args = parser.parse_args(argv)
    try:
        report = normalize(json.loads(Path(args.report).read_text(encoding="utf-8")))
        if args.facts:
            validate_evidence(report, json.loads(Path(args.facts).read_text(encoding="utf-8")))
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.format == "json"
              else render_markdown(report, args.verbosity), end="\n")
    except (ValueError, OSError, TypeError) as exc:
        print(json.dumps({"completed": False, "error": {"code": "report.invalid", "message": str(exc)}}, ensure_ascii=False))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
