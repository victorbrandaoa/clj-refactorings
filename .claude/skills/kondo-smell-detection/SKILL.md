---
name: kondo-smell-detection
description: Use kondo tool to detect code smells in clojure projects. Requires python3 and clj-kondo configured via $KONDO_DIR.
allowed-tools: Bash(python3 *) Read
---

## Prerequisites

You need to have the clj-kondo cloned and KONDO_DIR filled in your .env, and have sourced the .env file in the project's root.

## Skill Instructions

You are going to run kondo through scripts/scan.py passing the project_path as an argument.

Input:

```sh
python3 ${CLAUDE_SKILL_DIR}/scripts/scan.py /full/path/to/project
```

Output:

```json
[
    {
        "rule_id": "blocking-inside-go",
        "message": "blocking operation inside go block",
        "filepath": "/path/to/your/project/file.clj",
        "location": {
            "start_line": 97,
            "start_col": 43,
            "end_line": 97,
            "end_col": 43
        },
        "severity": "WARNING"
    }
]
```
