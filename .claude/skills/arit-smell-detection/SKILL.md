---
name: arit-smell-detection
description: Use arit tool to detect code smells in clojure projects. Requires python3 and the arit binary configured via $ARIT_DIR.
allowed-tools: Bash(python3 *) Read
---

## Prerequisites

You need to have the arit binary in $ARIT_DIR/arit and have sourced the .env file in the project's root.

## Skill Instructions

You are going to run arit through scripts/scan.py passing the project_path as an argument.

Input:

```sh
source .env && python3 ${CLAUDE_SKILL_DIR}/scripts/scan.py $ARIT_DIR/arit /full/path/to/project
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
