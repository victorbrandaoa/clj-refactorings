---
name: smell-refactor-pipeline
description: End-to-end pipeline that applies refactorings, verifies tests work after the refactor, re-scans to see if the smell is gone.
---

## Skill Instructions

You are going to run the full smell-detection-and-refactor pipeline against a target Clojure project by orchestrating the existing skills and agents below, in order.

Input:
- `smells_csv` (required): absolute path to the csv with the smells to refactor;
- `test_check` (required): absolute path to the csv with lein config to be used when testing;
- `initial_run` (required): path to the initial ARIT result;
- `results_dir` (required): path to the directory where the results will be stored;
- `smell_index` (required): the index of the smell on `smells_csv`;

Output:
- The final <results_dir>/<project_name>/output.csv by project after the execution finish;

Restrictions:
- You must follow the steps here strictly, do not do anything that is not strictly specified here;
- You must not ask anything, you have enough context to decide what to do by yourself;
- All the rounds are independent and run regardless of success;

### Steps

1. **Load test data** Read `test_check` csv to have test information available;

2. **Load smell data** Read `smells_csv` and filter to keep smells with covered=True, is_test=False;

  2.1. **Project dir** Extract <project_path> from filepath field on the row, the project path goes until the first directory name after `refactorings` directory;

  2.2. Join with `test_check` and filter using verified_ok field to keep only smells that have working tests;

  2.3. Define `project_results_dir` as <results_dir>/<project_name>, where <project_name> is the last dir on <project_path> and create the directory if it does not exist yet;

  2.4. Show the final stats of how many smell were kept;

3. **Loop over the smells** For each row of the filtered `smells_csv`, in order:
  Note: Always keep a counter of how many smells were finished already and how many are left;
  Note: each row uses `project_results_dir` of its own project;

  3.1. **Test Execution Config** Read which project_clj_path to use according to the module_key from `test_check` csv, which is the project dir name from project_path;

  3.2. Use the verified_ok field from `test_check` csv to see if the tests pass, if not skip to the next smell (go to step 3).

4. **Start round counter** Start the round counter as 1;

5. **Clean up the diffs** Execute the following command to clean up the diffs before start:
    ```sh
    git reset --hard HEAD && git clean -fd
    ```

6. **Run Loop refactor over five times over each smell** Run while counter is less than 6;
  Note: If round reach 6, the process should stop and proceed to step 7;
  
  6.1. **Refactor Loop** Run the skill `/refactor-loop` over the row from `smells_csv` as `smell_data`, pass `project_clj_path` as `lein_config`, pass `round`, `initial_run`, `smell_index`, `project_results_dir` and `project_path`;

  6.2. **Clean up the diffs** Execute the following command to clean up the diffs:
    ```sh
    git reset --hard HEAD && git clean -fd
    ```

  6.3. Increment round by one and go back to step 6.1;

7. Go back to step 3 for the next smell;

