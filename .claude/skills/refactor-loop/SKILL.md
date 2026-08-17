---
name: refactor-loop
description: Skill that manages the agents and skills used within the refactor loop.
---

## Skill Instructions

You are going to run a refactor loop over a given Clojure project in order to solve code smells found there.

Input:
- `project_path` (required): absolute path to the target Clojure project;
- `code_smells` (required): json file that show the smells found and their location;
- `test_cmd` (required): command that executes the entire test suite of the project;

Output:
- `output.csv`: a csv file with the following columns:
  * `iter`: the iteration of the loop;
  * `diff`: the production code diff at that iteration;
  * `tests`: wether or not the test suite works at that iteration;
  * `agreement`: wether or not the agents agreed about the refactor;
  * `smells_solved`: the smells solved count at that iteration;

Important Notes:
- You must follow the steps here strictly, do not do anything that is not strictly specified here;
- Take extra care when writing the iteration results to the csv;
- The loop must run at most three times, not more than that;
- You must not ask anything, you have enough context to decide what to do by yourself;

### Steps

1. **Pre Execution** Create the following things before starting the loop:
  1.1. Create an index `i` to be used in the loop, starts with 1. (It will be used as `{i}` inside the loop);
  1.2. Create a csv file `<project_path>/output.csv` with the columns: `iter`, `diff`, `tests`, `agreement` and `smells_solved`
  1.3. Create a json file in `<project_path>/smells-count.json` with the following format and fill with the initial smell counts before starting the loop (initial i is 0):
  ```json
  {
    "{i}": {
      "<smell-name>": <smell-count>,
      ...
    }
  }
  ```

2. **Gather Context** Read the smells reference within ${CLAUDE_SKILL_DIR}/references so you get context of the meaning of the smells;

3. **Start Loop** The loop begins at step 3;
  3.1. If `{i}` is greater than 3, you must stop. End the execution of this skill in this case;

4. **Plan and Apply the fix** Give @clj-developer the context from step 2 and ask to plan and apply the fix over the `project_path` for all the smells within the json `code_smells`;
  4.1. Use the skill `/git-helper` to get the diffs of all production files at this iter (production only, you must ignore test changes);

5. **Test** Ask @clj-tester to execute the test using the command `test_cmd` to verify they still finish successfully and save the execution log to `<project_path>/tmp/test_run_{i}.log`;

6. **Re-scan** Invoke the skill `/arit-smell-detection` with `project_path` and `smells` (if passed) as arguments. Save the result as `<project_path>/scan-after_{i}.json`;
  6.0. When counting the solved smells, remember to consider the possible shift on the smell position due to the changes applied;
  6.1. Count how many smells were solved on this iter by comparing `code_smells` with `<project_path>/scan-after_{i}.json`;
  6.2. Add a new entry in `<project_path>/smells-count.json` for this iteration;

7. **Review** Give @clj-reviewer the context from step 2 and ask to review the fix applied at step 4;
  7.0. Everytime you reach this step 7, before proceed or going back to step 3, write the iteration results in `<project_path>/output.csv`, then increment the index `i` by one;
  7.1. If the tests are broken, look at the failure log at `<project_path>/tmp/test_run_{i}.log` and suggest another refactor to @clj-developer and go back to step 3;
  7.2. If the tests work, but the fix have not solved the smell, suggest another refactor to @clj-developer and go back to step 3;
  7.3. If the tests work, but it disagrees with the fix, suggest another refactor to @clj-developer and go back to step 3;
  7.4. If the tests work and there is no disagreement with the fix applied at step 4, proceed;

8. **Report** Return a report of what was done;
  8.1. If any smell was flaged as false positive, explain why on the report;
