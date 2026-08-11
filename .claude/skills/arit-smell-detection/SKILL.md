---
name: arit-smell-detection
description: Use ARIT tool to detect code smells in clojure projects. Requires python3 and the arit binary configured via $ARIT_DIR.
---

## Instructions

Input:
- Path to the project that will be analyzed;
- Optional smells list to be considered;

Output:
- Json with the final scan result after filtering;

1. Go to ARIT directory using the command below:

```sh
source .env && cd $ARIT_DIR
```

2. Use the skill /git-helper to update the main/master branch of ARIT.

3. Run the following command to generate ARIT's binary executable:

```sh
rm arit && go build -o arit .
```

4. Run ARIT through scripts/scan.py passing the project_path as an argument.

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

5. Discard any occurrence whose `filepath` is a test file or benchmark file.

6. If `smells` was given, also drop any entries whose `rule_id` is not in that list.

7. If the filtered result is empty, stop here and report "no target smells found.".
