---
name: arit-smell-detection
description: Use arit tool to detect code smells in clojure projects.
compatibility: Requires python3
allowed-tools: Bash(python:*) Read
---

## Prerequisites

You need to have the arit binary in $ARIT_DIR/arit and have sourced the .env file in the project's root.

## Skill Instructions

You are going to run arit through scripts/scan.py passing the project_path as an argument.

Input:

```sh
python3 .agents/skills/arit-smell-detection/scripts/scan.py $ARIT_DIR/arit /full/path/to/project
```

Output:

```json
[
    {
        "rule_id": "hidden-side-effects",
        "message": "Function '-main' performs side effects (I/O operations) without explicit indication. Consider adding '!' suffix or using 'doseq' for side-effect operations to make the impurity explicit.",
        "filepath": "/path/to/your/project/file.clj",
        "location": {
            "start_line": 13,
            "start_col": 1,
            "end_line": 13,
            "end_col": 2
        },
        "severity": "WARNING"
    }
]
```