---
name: smell-refactor-pipeline
description: End-to-end pipeline that detects Clojure code smells, ensures test check, applies refactorings, verifies, re-scans, and reports results.
---

## Skill Instructions

You are going to run the full smell-detection-and-refactor pipeline against a target Clojure project by orchestrating the existing skills and agents below, in order.

Input:
- `project_path` (required): absolute path to the target Clojure project;
- `smells` (optional, default: all smells reported by the detector): a list of `rule_id`s to restrict the pipeline to;

Output:
- Markdown report of the refactoring pipeline as described;

Restrictions:
- You must follow the steps here strictly, do not do anything that is not strictly specified here;
- You must not ask anything, you have enough context to decide what to do by yourself;
- Follow the exact template of report on this skill;

### Steps

1. **Baseline scan** Invoke the skill `/arit-smell-detection` with `project_path` and `smells` (if passed) as arguments. Save the result as `<project_path>/scan-before.json`;
  1.1. If there is no smell, just stop here and report that;

2. **Test check** Ask @clj-tester to find out how to run the tests and confirm they are working using the skill `/test-discovery`;

3. **Refactor Loop** Run the skill `/refactor-loop` over `project_path`, with `<project_path>/scan-before.json` as `code_smells`, the test command from previous step and `smells` (if passed) as arguments;

4. **Report.** Produce output following the exact format below and save it to a file called `<project_path>/refactoring-report.md`:

```md
Project: [project-name]

Smells:

<!-- For each smell found do: -->
[smell-name]: [number-of-occurrences-before] -> [number-of-occurrences-after]
<!-- If any smell was considered as false positive: -->
  - False Positives: [number-of-false-positives]
    - [explanation-of-why-they-are-false-positives]

Command(s) To Run the Whole Test Suite:

```bash
[command-to-run-tests]
...
```
```
