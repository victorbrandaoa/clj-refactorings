---
name: arit-batch-detection
description: Use ARIT tool to detect code smells in a batch of clojure projects. Requires arit binary configured via $ARIT_DIR.
---

## Input

repos_path - the path to the directory where all the projects from lein_config are clonned.
output_dir - the directory where the output will be saved.

## Output

current_state - a json file with all the detections from ARIT.
current_state_test - a csv file with all the detections marked as test file or not, and tagged with each detection's smell group (from references/smells_type.csv).

## Instructions

1. Verify if the env var $ARIT_DIR is set and ask the user to set if not.

2. Run the following command to execute ARIT over the projects:

```sh
$ARIT_DIR --include-contextual --format json-snippet repos_path > output_dir/current_state.json
```

3. Run the following command to mark each detection with whether it sits in a test file, based on a deterministic set of filepath heuristics (test/tests directories, test-related directory conventions like test-resources/integration-test, *_test/*_spec filename suffixes, with source_role as a narrow supplementary signal), tag it with its smell group, and save the result as a csv (via pandas - use the dedicated venv at `~/.venvs/check-lein-test` if pandas isn't on the system python3):

```sh
~/.venvs/check-lein-test/bin/python3 ${CLAUDE_SKILL_DIR}/scripts/mark_test_occurrences.py --input output_dir/current_state.json --output output_dir/current_state_test.csv
```

The script writes the nested `location` field as four flat columns (location_start_line/location_start_col/location_end_line/location_end_col) and joins the list fields `missing_evidence`/`tags` with "; ", since CSV has no native nested-value representation. It adds a `group` column by looking up each occurrence's `rule_id` in `${CLAUDE_SKILL_DIR}/references/smells_type.csv` (columns: group, rule_id) - a rule_id with no match there gets `group="Unknown"` and a printed warning instead of a crash or a silent gap, since that reference file is maintained separately from ARIT and can drift out of sync with new rule_ids. It also reads the csv back after writing and checks it against the in-memory data (row count, and `is_test`/`group` values in the same order) - it prints "consistency check passed" on success and fails loudly (an assertion error) rather than silently trusting the round-trip.

3.1. If you find any false positive classification of a detection as being within a test file, feel free to change the classification.

3.2. The script prints a summary (total occurrences, how many were marked is_test=True/False, false positives along with justification) - report this alongside the ARIT detection summary.
