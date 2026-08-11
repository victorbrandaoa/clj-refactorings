---
name: smell-refactor-pipeline
description: End-to-end pipeline that detects Clojure code smells, ensures test coverage, applies refactorings, verifies, re-scans, and reports results.
---

## Skill Instructions

You are going to run the full smell-detection-and-refactor pipeline against a target Clojure project by orchestrating the existing skills and agents below, in order.

Input:
- `project_path` (required): absolute path to the target Clojure project;
- `smells` (optional, default: all smells reported by the detector): a list of `rule_id`s to restrict the pipeline to;

Output:
- Markdown report of the refactoring pipeline as described;

Restrictions:
- Do not use or do anything that is not explicitly described on this pipeline.

### Steps

1. **Baseline scan** Invoke the skill `/arit-smell-detection` with `project_path` and `smells` (if passed) as arguments. Save the result as `<project_path>/scan-before.json`;

2. **Evaluate False Positives** Ask @clj-reviewer to generate a report of false positive smells on the initial scan result `<project_path>/scan-before.json`. Then save the filtered result as `<project_path>/scan-before-filtered.json`;

3. **Test coverage check** Ask @clj-tester to find out how to run the tests and confirm they are working using the skill `/test-discovery`. Then, for each smell found on `<project_path>/scan-before-filtered.json`, ask @clj-tester to check the coverage and increase it if necessary using the skill `/test-coverage`;

4. **Refactor the smells** Read the smells reference within ${CLAUDE_SKILL_DIR}/references so you get context of the meaning of them, then for each smell on `<project_path>/scan-before-filtered.json`:
  4.1. Ask @clj-developer to plan and apply a refactor that solve the occurencies of the smell, you can pass the smell explanation as reference to plan the fix;
  4.2. Ask @clj-tester to execute the tests to make sure they still work after the refactor.
  4.3. Ask @clj-reviewer to review the refactored code, and suggest another refactor to @clj-developer if it disagrees. If there's disagreement, then go back to step 4.1 and repeat based on the review. You must run this loop at most 3 times.

5. **Re-scan** Invoke the skill `/arit-smell-detection` with `project_path` and `smells` (if passed) as arguments. Save the result as `<project_path>/scan-after.json`; 

6. **Report.** Produce output following the exact format below and save it to a file called `refactoring-report.md`:

```md
Project: [project-name]

Smells:

<!-- For each smell found do: -->
[smell-name]: [number-of-occurrences-before] -> [number-of-occurrences-after]
  - False Positives: [number-of-false-positives]
    - [explanation-of-why-they-are-false-positives]

Command(s) To Run the Whole Test Suite:

```bash
[command-to-run-tests]
...
```

Tests Coverage:

<!-- For each smell found do: -->
[smell-name]: [number-of-tests-before] -> [number-of-tests-after]
  <!-- For each test found/created do: -->
  - [absolute-path-of-test-file-exercising-the-smell-before-and-after]:[test-line-before-and-after]
```
