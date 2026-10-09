#!/usr/bin/env python3
"""Validate and render an agent-assessed SCK report, without reading its target.

This is a report consumer, not an automatic semantic reviewer. Invalid input
returns an operational error, never a quality verdict.
"""
import argparse
import copy
import json
from pathlib import Path


SCHEMA = "skill-creator-king.report.v1"
BASE_IDS = ["SCK-S%02d" % n for n in range(1, 11)] + ["SCK-L%02d" % n for n in range(1, 14)]
CODEX_IDS = ["SCK-C%02d" % n for n in range(1, 5)]
STATUSES = ("pass", "gap", "advisory", "not_applicable", "not_assessed")
# JSON keeps the full boundary claim; user-facing lines use the short template form.
CLAIM = "运行行为：未评估，超出 SCK 范围。静态检查不证明安全、宿主验收、发布就绪或人工批准。"
CLAIM_LINE = "运行行为：未评估，超出 SCK 范围"
LABELS = {"pass": "通过", "gap": "必修", "advisory": "建议", "not_applicable": "不适用", "not_assessed": "未评估"}


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
    for field in ("limitations", "changes"):
        array(report.get(field), field)
        for i, value in enumerate(report[field]):
            string(value, "%s[%s]" % (field, i))
    verdict = ("无法完成检查" if has_unknown else "静态不合规" if has_gap else
               "静态合规但有建议" if has_advisory else "静态合规")
    report["verdict"] = verdict
    report["coverage"] = {s: sum(c["status"] == s for c in checks) for s in STATUSES}
    report["claim_boundary"] = CLAIM
    report["checks"] = sorted(checks, key=lambda c: expected_ids.index(c["id"]))
    return report


def render_markdown(report, verbosity="full"):
    report = normalize(report)
    checks = report["checks"]
    counts = " · ".join("%s %s" % (n, LABELS[s])
                        for s, n in report["coverage"].items() if n)
    lines = ["**静态合规报告**", "", "结论：**%s**——%s 项全分类（%s）" % (report["verdict"], len(checks), counts),
             "", "检查对象：" + report["target"],
             "读取范围：" + report["read_scope"], ""]
    for disposition, label in (("gap", "必修项（不修=静态不合规）"), ("advisory", "建议项（不影响合格判定）")):
        items = [(c, f) for c in checks for f in c["findings"] if f["disposition"] == disposition]
        lines.append(label + ("：" if items else "：无"))
        for check, finding in items:
            location = finding["file"] + (" 第 %s 行" % finding["line"] if finding["line"] else "")
            kind = "脚本事实" if finding["check_type"] == "deterministic" else "语义推断"
            # 用户语言三段：位置＋证据＋影响一句话，然后最小修改动作；严重度留给 JSON。
            statement = "%s：%s，%s。" % (location, finding["evidence"].rstrip("。"),
                                         finding["impact"].rstrip("。"))
            title = ("**%s**" if disposition == "gap" else "%s") % check["title"]
            lines.append("- %s（%s；%s）：%s怎么改：%s。" %
                         (title, check["id"], kind, statement,
                          finding["recommendation"].rstrip("。")))
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
    passed = [c for c in checks if c["status"] == "pass"]
    lines.append("通过 %s 项：%s" % (len(passed), " · ".join("%s（%s）" % (c["title"], c["id"]) for c in passed)))
    observations = [(c, o) for c in checks for o in c["observations"]]
    if observations:
        lines.extend(["", "脚本观察处置："])
        for c, item in observations:
            original = item["original"]
            lines.append("- %s，%s：%s；原始观察：%s" %
                         (c["id"], original["path"], item["disposition"], original["evidence"]))
    if verbosity == "full" and passed:
        groups = {}
        for c in passed:
            groups.setdefault(c["reason"].rstrip("。"), []).append("%s（%s）" % (c["title"], c["id"]))
        lines.extend(["", "通过项依据："] +
                     ["- %s：%s" % (reason, " · ".join(names)) for reason, names in groups.items()])
    lines.extend(["", "限制："] + (["- " + x for x in report["limitations"]] or ["无"]))
    if report["changes"]:
        lines.extend(["", "变更证据："] + ["- " + x for x in report["changes"]])
    lines.extend(["", CLAIM_LINE, "下一步行动：" + report["next_action"]])
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--verbosity", choices=("concise", "full"), default="full")
    args = parser.parse_args(argv)
    try:
        report = normalize(json.loads(Path(args.report).read_text(encoding="utf-8")))
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.format == "json"
              else render_markdown(report, args.verbosity), end="\n")
    except (ValueError, OSError, TypeError) as exc:
        print(json.dumps({"completed": False, "error": {"code": "report.invalid", "message": str(exc)}}, ensure_ascii=False))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
