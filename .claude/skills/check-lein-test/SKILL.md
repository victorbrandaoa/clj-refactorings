---
name: check-lein-test
description: Use a deterministic script to verify lein install and lein test for every project.clj found by identify-leiningen.
---

## Input

lein_config_path - path to a lein_config.csv file (columns: repo, project_clj_path), as produced by the identify-leiningen skill.
repos_path - the path to the directory where all the projects from lein_config are clonned.
out_path - the path to the directory where test_check.csv and logs will be written.

## Output

results - a test_check.csv file saved within out_path with one row per project.clj, recording install/test status, timings, test counts, log paths, and a `manually_classified` column (defaults False; step 2.2 sets it True on any row where a human/agent judgment call overrode the script's own conclusion).
install_state - an install_state.csv file saved within out_path, one row per module per install attempt - this is the script's own resume bookkeeping for Phase 1, not something you need to read directly, but don't delete it between runs or a resume will redo every install from scratch.
report - summary of how many project.clj entries were verified ok, and a breakdown of failures/timeouts.

## Instructions

1. Run the script to verify lein install and lein test for every project.clj in lein_config_path. The script needs pandas - use the dedicated venv at `~/.venvs/check-lein-test` (create it with `python3 -m venv ~/.venvs/check-lein-test && ~/.venvs/check-lein-test/bin/pip install pandas` if it doesn't exist yet):

```sh
~/.venvs/check-lein-test/bin/python3 ${CLAUDE_SKILL_DIR}/scripts/run_lein_tests.py --lein-config lein_config_path --repos-root repos_path --out-dir out_path
```

The script runs in two phases:
- **Phase 1 (install):** `lein install` (not just `deps`) for every project.clj, grouped by repo. A repo's own modules run their install rounds in sequence - if a module fails because it needs a sibling module's artifact, that sibling installing first in the same round unblocks it in the next round (`--install-rounds`, default 2). Different repos can install concurrently via `--install-workers`, but it defaults to 1 (serial) - raise it only once you've confirmed the machine has headroom to spare (see 1.4).
- **Phase 2 (test):** `lein test` for every module whose install ultimately succeeded, run concurrently across all repos (`--test-workers`, default: CPU count). Modules whose install never succeeded get an immediate `test_status=skipped` row, no test attempted.

1.1. This can take a long time across a full lein_config.csv even with the phasing above. Launch it as a background process rather than waiting on it synchronously.

1.2. The script is resumable at the module level, in both phases: `test_check.csv` gates whether a module needs any work at all, and `out_path/install_state.csv` separately records each module's install result the moment it's known - so a kill mid-Phase-1 (this happens often on a live/shared machine running low on memory) loses at most the one module that was mid-install, not the whole batch of installs completed so far. Already-installed artifacts also stay in the shared local `~/.m2`/`~/.lein` cache between runs, so resuming doesn't lose the sibling-install benefit from a prior run either.

1.3. Use `--limit N` for a small smoke test before committing to a full run. `--install-timeout` and `--test-timeout` (seconds, defaults 300/900) can be tuned if too tight or too loose for the repos involved - the defaults were raised once already after real Clojure test suites (embedded-broker integration tests, generative/benchmark suites) routinely needed 10-20 minutes, well past the original 240s/300s. A `timeout` result is a "needs a bigger budget" signal at least as often as a "genuinely stuck" one - don't assume the latter without checking how far the log actually got.

1.4. On a live/shared machine (not a dedicated CI box), check available memory (`free -h`) before picking `--install-workers`/`--test-workers` - each worker is a concurrent JVM. `--install-workers` already defaults to 1 (serial) for exactly this reason; `--test-workers` still defaults to CPU count, which assumes a machine with real headroom to spare - on a loaded desktop, override it down to 1 too, and only raise either one if the run is surviving cleanly.

2. Once the run finishes, read `out_path/test_check.csv`. Logs live under `out_path/logs/<module_key>/`: `install_round1.log` (and `install_round2.log` etc. if a retry happened) and `test.log`.

2.1. The script can only reliably parse plain `clojure.test` output (`Ran N tests containing M assertions`). Any other test runner - midje, `com.brunobonacci/rdt`, kaocha, eftest, or anything else - prints its own summary format, which the script has no way to know about in advance, so it records `test_status=crash` even when every test actually passed. Don't trust `test_status`/`verified_ok` at face value for anything other than a clean `ran` + `all_tests_passed=True`: for every row where `test_status` is `"crash"`, `"timeout"`, or `"error"`, open its `test.log` yourself and read it to determine what really happened. Look for the runner's own pass/fail summary (e.g. midje's `All checks (N) succeeded`, rdt's `==== Test summary ==== ... Failed: 0`) or an actual stack trace / dependency error / `Tests failed` line, and note which of these rows are real failures vs. false negatives from an unrecognized output format.

2.2. Correct `test_check.csv` for what 2.1 found - don't just note it in the report and leave the row as-is; the CSV is the artifact people will actually query later, so it needs to reflect reality, not the script's parsing limits. Every row you touch here gets `manually_classified` set to `True` (it defaults to `False` from the script), so anyone reading the CSV later can tell which rows came from a script execution versus a human/agent judgment call. Two patterns:

  - **Confirmed real pass in an unrecognized format** (e.g. midje's `All checks (N) succeeded`, rdt's `Total tests: N ... Failed: 0`, a generative/property-test suite with an explicit pass/fail count per case but no final summary line): set `verified_ok = True`, `ran_to_completion = True`, and `tests_run` to the real count recovered from the log (search the whole log, not just the tail, for frameworks that don't print a clean end-of-run summary). `all_tests_passed` is already `True` from the exit code, so it doesn't need touching. Do NOT do this for a log that merely exits 0 with no evidence of anything actually running (e.g. a midje file reporting `"No facts were checked"`, or a log that's empty or cuts off mid-test) - that's not a pass, exit 0 alone isn't sufficient evidence.
  - **Genuinely unresolvable in this environment, not transient** (needs a live external service - a database, message broker, network resource - that isn't running here; a `test` alias that's actually a file-watcher or other long-running tool that was never going to exit; missing privileges the environment won't grant): if the row's `test_status` is `"timeout"`, relabel it to `"crash"` (the closest fit - it's not going to resolve to a pass, and `timeout` invites another pointless retry). Leave `verified_ok = False`. Still set `manually_classified = True`, since you made a determination about it even though nothing about its pass/fail status changed.

3. Retry the cases that look transient, then update the results:

3.1. From `test_check.csv`, select rows where `manually_classified != True` AND (`install_status != "ok"` OR `test_status` is `"timeout"`, `"crash"`, or `"error"`). These are the statuses most likely caused by network blips, timeouts, resource contention, or install ordering - not by the code itself - so they're worth a second attempt. Excluding `manually_classified` rows matters: step 2.2 already made a final determination on each of those (either a confirmed pass, or confirmed unresolvable-here), so retrying one is either pointless (it'll just reproduce the same unparseable-but-passing output) or will only reproduce the same unresolvable failure. Also do NOT retry a row where `test_status == "ran"` and `all_tests_passed == False`: that's a real, reproducible test failure, not noise.

3.2. Remove exactly those rows from `test_check.csv` (leave every other row untouched - the script's resume logic treats any `module_key` still present as done and will skip it).

3.3. Re-run the same command from step 1 (same `--lein-config`, `--repos-root`, `--out-dir`). With those rows gone, the script will reprocess only the retried modules and append fresh rows for them into `test_check.csv`, leaving everything else as-is.

3.4. Repeat 3.1-3.3 at most once more. If a module still fails on the second attempt, stop retrying it and report it as a real failure - don't loop indefinitely on something that isn't transient.

4. Report a summary: total project.clj entries processed, how many are `verified_ok`, how many failed at the install step vs the test step (and, for install failures, how many only succeeded on a retry round - `install_round` > 1 - which signals a real sibling-module dependency), how many timed out, how many needed a step-3 retry and whether the retry fixed them, and how many rows ended up `manually_classified` from step 2.2 - split into how many were promoted to a confirmed pass (naming which test runner/format was responsible when you can tell - midje, rdt, etc.) versus how many were confirmed genuinely unresolvable in this environment (and why - missing external service, non-standard test alias, missing privileges, ...).
