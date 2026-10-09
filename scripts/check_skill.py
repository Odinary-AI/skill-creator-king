#!/usr/bin/env python3
"""Run SCK's own validator with an existing Python/PyYAML environment.

No target code, dependency installation, service, or network is invoked.
"""
import json
import os
from pathlib import Path
import subprocess
import sys


def supports_yaml(executable):
    try:
        result = subprocess.run(
            [str(executable), "-I", "-c", "import sys,yaml; sys.exit(0 if sys.version_info >= (3,9) and yaml.__version__.split('.')[0] == '6' else 1)"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
            cwd=str(Path(__file__).resolve().parent),
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def select_python():
    configured = os.environ.get("SCK_PYTHON")
    if configured:
        return configured if supports_yaml(configured) else None
    candidates = [sys.executable, Path.home() / ".workbuddy/binaries/python/envs/default/bin/python"]
    for candidate in candidates:
        if supports_yaml(candidate):
            return str(candidate)
    return None


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    validator = Path(__file__).resolve().with_name("validate_skill.py")
    runtime = select_python()
    if runtime is None and os.environ.get("SCK_PYTHON"):
        print(json.dumps({"completed": False, "error": {
            "code": "runtime.unavailable",
            "message": "SCK_PYTHON must identify an existing Python 3.9+ environment with PyYAML 6.x. No dependency was installed."
        }}))
        return 2
    # With no ready environment preserve the validator's independent filesystem
    # results and explicit YAML not_assessed items; never guess parsed values.
    # The validator inherits this caller's working directory so relative target
    # paths resolve where the user invoked the entry, not beside the script.
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([runtime or sys.executable, "-I", str(validator), *args],
                          env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main())
