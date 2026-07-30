#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys

KONDO_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "kondo.sh",
)

WARNING_TO_RULE_ID = {
    "blocking operation inside go block": "blocking-inside-go",
    "Prefer cond-> to build a map with successive conditional assocs.": "conditional-build-up",
}

# Pattern: /path/to/file.clj:LINE:COL: (warning|error|info): Message text
LINE_PATTERN = re.compile(
    r"^(?P<filepath>.+?):(?P<line>\d+):(?P<col>\d+):\s+(?P<severity>warning|error|info):\s+(?P<message>.+)$"
)

def parse_kondo_output(raw_output: str) -> list[dict]:
    """Parse kondo stdout lines into a list of structured findings."""
    results = []

    for line in raw_output.splitlines():
        match = LINE_PATTERN.match(line.strip())
        if not match:
            continue

        message = match.group("message").strip()
        rule_id = WARNING_TO_RULE_ID.get(message)

        if rule_id is None:
            continue

        start_line = int(match.group("line"))
        start_col = int(match.group("col"))

        results.append({
            "rule_id": rule_id,
            "message": message,
            "filepath": match.group("filepath"),
            "location": {
                "start_line": start_line,
                "start_col": start_col,
                "end_line": start_line,
                "end_col": start_col,
            },
            "severity": match.group("severity").upper(),
        })

    return results

def run_kondo(project_path: str) -> dict:
    """Run kondo.sh on the given project path.

    Returns a dict with keys: success, output, errors.
    """
    if not os.path.exists(KONDO_SCRIPT):
        return {"success": False, "output": "", "errors": f"kondo.sh not found at {KONDO_SCRIPT}"}

    try:
        result = subprocess.run(
            ["bash", KONDO_SCRIPT, "--lint", project_path],
            capture_output=True,
            text=True,
            timeout=120,
        )
        # clj-kondo writes findings to stdout
        raw = result.stdout.strip()
        findings = parse_kondo_output(raw)

        if not findings:
            return {
                "success": True,
                "output": "No code smells found matching the configured rules.",
                "errors": result.stderr.strip(),
            }

        return {
            "success": True,
            "output": json.dumps(findings, indent=2),
            "errors": result.stderr.strip(),
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "errors": "kondo.sh timed out after 120 seconds"}
    except Exception as e:
        return {"success": False, "output": "", "errors": str(e)}

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <project_path>", file=sys.stderr)
        sys.exit(1)

    project_path = sys.argv[1]
    result = run_kondo(project_path)

    if result["errors"]:
        print(result["errors"], file=sys.stderr)

    if result["output"]:
        try:
            parsed = json.loads(result["output"])
            print(json.dumps(parsed, indent=2))
        except json.JSONDecodeError:
            print(result["output"])

    sys.exit(0 if result["success"] else 1)

if __name__ == "__main__":
    main()
