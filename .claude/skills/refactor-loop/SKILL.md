---
name: refactor-loop
description: Skill that manages the agents and skills used within the refactor loop.
---

## Skill Instructions

You are going to run a refactor loop over a given Clojure project in order to solve code smells found there.

Input:
- `smell_data` (required): a row with smell information;
- `initial_run` (required): path to the initial ARIT result;
- `round` (required): round of execution for the given smell;
- `lein_config` (required): path to the project.clj file to be used when running tests;
- `project_path` (required): path to the project clonned locally;
- `smell_index` (required): index fo the `smell_data` row on the input csv;
- `project_results_dir` (required): the results directory for a project;

Output:
- `<project_results_dir>/output.csv`: a csv file with the following columns:
  * `round`: the round of execution;
  * `iter`: the iteration of the loop;
  * `diff`: the code diff at that iteration (path to file);
  * `tests_pass`: wether or not the test suite works at that iteration;
  * `agreement`: wether or not the agents agreed about the refactor;
  * `removed_smell`: wether or not the smell was removed;
  * `rule_id`: the smell rule id;
  * `smell_filepath`: the fiel were the smell was first found;
  * `code_snippet`: the code snippet where the smell was first found;
  * `test_log`: filepath to the test log from a given round and iter;
  * `new_smells`: the count of possible new added smells;
  * `project_path`: path to the project clonned locally;
  * `smell_index`: index fo the `smell_data` row on the input csv;

Important Notes:
- You must follow the steps here strictly, do not do anything that is not strictly specified here;
- You should write the line to output.csv only in the end of an iter, after gather the information on the loop;
- Take extra care when writing the iteration results to the csv;
- The loop must run at most three times, not more than that;
- You must not ask anything, you have enough context to decide what to do by yourself;

### Steps

1. **Pre Execution** Create the following things before starting the loop:
  1.1. Create an index `i` to be used in the loop, starts with 1. (It will be used as `{i}` inside the loop to fill `iter`);
  1.2. Extract the fields `rule_id`, `code_snippet` and `filepath` (it will be used as `smell_filepath`) from `smell_data`;
  1.3. Create a csv file `<project_results_dir>/output.csv` with the columns: `round`, `iter`, `diff`, `tests_pass`, `agreement`, `removed_smell`, `rule_id`, `smell_filepath`, `code_snippet`, `test_log`, `new_smells`, `project_path` and `smell_index` if it does not exist already;

2. **Smells Context** Read the smells context on references directory.

3. **Start Loop** The loop begins at step 3;
  3.1. If `{i}` is greater than 3, you must stop. End the execution of this skill in this case;

4. **Plan and Apply the fix** Ask @clj-developer to plan and apply the fix for the smell given always using the smells context from step 2;
  4.1. Use the command to save the diff to `<project_results_dir>/{smell_index}_{round}_{i}_diff.txt` and fill `diff`:
    ```sh
    git diff; git ls-files --others --exclude-standard | while IFS= read -r f; do echo "diff --git a/$f b/$f (untracked)"; diff -u /dev/null "$f" || true; done
    ```

5. **Test** Ask @clj-tester to run lein test from the directory containing lein_config (the module's project.clj), without running lein install, and verify the suite still finishes successfully after the refactoring, saving the execution log to `<project_results_dir>/{smell_index}_{round}_{i}_test_run.log`;
  5.1. Use the success of this step to fill `tests_pass` and `test_log`.

6. **Re-scan** Run ARIT over `project_path` and save the result as `<project_results_dir>/{smell_index}_{round}_{i}_scan-after.json` with the following commands:

  ```sh
  source .env
  $ARIT_DIR/arit --include-contextual --format json-snippet <project_path> > <project_results_dir>/{smell_index}_{round}_{i}_scan-after.json
  ```

  Note: use the fields `ast_fingerprint`, `rule_id` and `filepath` from `smell_data` to help verify if it is gone.
  Note: feel free to use `code_snippet` to analyze, but do not use it for exact matches.
  Note: use the information on the notes to identify if the smell is gone or new ones were added.
  6.1. Verify if the given smell was solved to fill `removed_smell` based on `<project_results_dir>/{smell_index}_{round}_{i}_scan-after.json`, if the smell on `smell_data` does not appear anymore, then it is solved.
  6.2. Verify the smells on the project before by filtering `initial_run` based on `project_path`, then compare with the `<project_results_dir>/{smell_index}_{round}_{i}_scan-after.json`, then count any smells that were not on `initial_run` to fill `new_smells` field;

7. **Review** Ask @clj-reviewer to review the fix applied at step 4 always using the smells context from step 2 and passing `<project_results_dir>/{smell_index}_{round}_{i}_diff.txt` and `<project_results_dir>/{smell_index}_{round}_{i}_test_run.log`;
  7.0. Everytime you reach this step 7, before proceed or going back to step 3, write the iteration results in `<project_results_dir>/output.csv`;
  7.1. If the tests are broken, look at the failure log at `<project_results_dir>/{smell_index}_{round}_{i}_test_run.log` and suggest another refactor to @clj-developer, then increment the index `i` by one and go back to step 3;
  7.2. If the tests work, but the fix have not solved the smell, suggest another refactor to @clj-developer, then increment the index `i` by one and go back to step 3;
  7.3. If the tests work, but it disagrees with the fix, suggest another refactor to @clj-developer, then increment the index `i` by one and go back to step 3;
  7.4. If the tests work and there is no disagreement with the fix applied at step 4, finish the execution;
