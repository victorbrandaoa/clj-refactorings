---
name: test-coverage
description: Analyze static var-level test reachability in a Clojure project using the bundled clj-kondo script. Use when identifying production vars or smell locations that are likely untested, including matching scan JSON findings to their containing vars.
---

## Instructions

Input:
- Path to the project that will be analyzed;
- The result of ARIT's execution over the project with the smells found;
- The command that successfully run the entire test suite;

Output:
- A markdown file with a report of the test coverage;

Restrictions:
- The steps 4 and 6 of the pipeline below should successfully run only once per execution;
- Do not touch any existing test, only create new ones when necessary;
- Follow the steps as described, no need for extra work. You must be straight forward;
- Do not start several test processes in parallel, at most 3, if necessary;

Important Note:
- When monitoring running processes, do not let them stuck. Do not use small timeouts when running test suites, do not try to predict how long the process will take to finish, just keep monitoring withou stuck.

1. Run the kondo-test-coverage.clj script this skill directory so Clojure CLI loads `deps.edn`:

```sh
clojure -M ${CLAUDE_SKILL_DIR}/scripts/test-coverage.clj --format summary /full/path/to/project
```

Note: Pass non-standard project layouts explicitly with repeated `--source-root` and `--test-root` options. Save the JSON report with `--output <file>` when it will be consumed by another tool. If necessary, run more than once within a single project with different arguments.

Note: this usage is not considered as a linter fix/check usage, since we use kondo to crate a dependency graph.

2. Use the smells detected by ARIT to verify if there are tests that exercise the code that has the smell.
  2.1. The detection shows the exact place where the smell occurs, use this information to associate a scan entry with coverage, by matching its absolute `filepath` and location line range to a report var with the same `file` and with `line <= start_line <= end-line`.;

3. Use the following heuristic to both, double check the matches from the previous step and try to find coverage for smells that did not match:
  3.1. Search for usages of the namespaces, functions and variables across the codebase to find tests that exercise the code.

4. For the code smells that have no tests found, please generate tests that exercise the code with the smell according to the pattern used on the codebase tests.
  4.1. If it is not the first time this step is reached on the loop, just go to the next step. This should run only once per execution;
  4.2. If it is the first time this step is reached, do not proceed to the next step until you generate all the necessary tests;
  
5. Use the command that runs the entire test suite to verify if the generated tests work.
  5.1. If they work, just proceed to the next step;
  5.2. If they do not work, iterate over them trying to fix until it runs;
  
6. Once you generated the new tests and they successfully run, go back to step 1;
  6.1. If it is not the first time this step is reached on the loop, just go to the next step. This should run only once per execution;

7. Generate a report of the test coverage of the smells as output following the template below:

Note: the template below presents placeholders for you to replace with relevant information;

```md
## For each smell found
  - [Smell-Type] - [Smell-Location]
    * Existing Tests: [Test-Count] - [List-Of-Test-Locations]
    * Generated Tests: [Test-Count] - [List-Of-Test-Locations]
```

8. Write to a file within the project directory called `test-report.md`.
