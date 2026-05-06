#!/usr/bin/env python3
"""Runs the arit static analyzer on a Clojure project and prints the results."""

import json
import os
import subprocess
import sys
import json

ALLOWED_RULES = [
    "production-doall",
    "blocking-inside-go",
    "conditional-build-up"
]

def filter_results(raw_json: str) -> str:
    """Parse JSON output and filter by allowed rule_ids."""
    try:
        results = json.loads(raw_json)
    except json.JSONDecodeError:
        return raw_json  # if not valid JSON, return as-is

    if not ALLOWED_RULES:
        return raw_json  # no filter configured, return everything

    filtered = [r for r in results if r.get("rule_id") in ALLOWED_RULES]

    if not filtered:
        return "No code smells found matching the configured rules."

    return json.dumps(filtered, indent=2)

def run_analyzer(analyzer_path: str, project_path: str) -> dict:
    """Run the arit analyzer on the given project path.

    Returns a dict with keys: success, output, errors.
    """
    if not os.path.exists(analyzer_path):
        return {"success": False, "output": "", "errors": f"Analyzer not found at {analyzer_path}"}

    try:
        result = subprocess.run(
            [str(analyzer_path), "--format", "json", project_path],
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout.strip()
        errors = result.stderr.strip()

        return {
            "success": result.returncode == 0,
            "output": filter_results(output),
            "errors": errors,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "errors": "Analyzer timed out after 120 seconds"}
    except Exception as e:
        return {"success": False, "output": "", "errors": str(e)}


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <arit_path> <project_path>", file=sys.stderr)
        sys.exit(1)

    analyzer_path = sys.argv[1]
    project_path = sys.argv[2]
    result = run_analyzer(analyzer_path, project_path)

    if result["errors"]:
        print(result["errors"], file=sys.stderr)

    if result["output"]:
        # Pretty-print if valid JSON, otherwise print raw
        try:
            parsed = json.loads(result["output"])
            print(json.dumps(parsed, indent=2))
        except json.JSONDecodeError:
            print(result["output"])

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
