---
name: verify-coverage
description: Verify whether ARIT smell detections are actually reached by a test file, using per-test-namespace Cloverage attribution.
---

## Input

test_check_path - path to check-lein-test's test_check.csv. There's no separately-curated "verified working repos" file to maintain - test_check.csv already records, per repo, whether its test suite genuinely passes (verified_ok), and the collect phase filters to those rows and normalizes them itself (its `repo` column is "owner/name", not the "owner__name" clone-directory form the rest of this pipeline uses; its `project_clj_path` is absolute, not relative). Only repos with verified_ok=True are worth running Cloverage on - coverage is meaningless for a repo whose tests don't even pass. If a plain TSV (no header, columns repo<TAB>project_clj_relative_path) is ever the only thing available instead, the collect phase also accepts that directly via `--verified-tsv` - but test_check.csv is the default, expected source.

current_state_test_path - path to current_state_test.csv, as produced by the arit-batch-detection skill.
repos_path - the path to the directory where all the projects are clonned.
out_dir - the directory where coverage_results.csv, per-namespace logs/lcov data, and the final output will be saved.

## Output

coverage_results - out_dir/coverage_results.csv, one row per repo: how many test namespaces it has, how many attributed cleanly, timing, and its attribution.json path when successful. This is the collect phase's own resume bookkeeping (at the repo level - a kill mid-repo loses that repo's in-progress namespace runs, no finer-grained resumability within one repo) - don't delete it between runs or a resume redoes every repo from scratch. Per-namespace raw lcov.info files live under out_dir/by_ns/<repo>/<namespace>__<index>/ - the index suffix matters and isn't cosmetic: the same namespace symbol can be declared in two different files (seen for real in metosin__sieppari, which has a .clj and .cljs test file both named sieppari.core-async-test, testing the same .cljc source) - without a per-run suffix, the second run's lcov.info would silently overwrite the first's on disk, breaking step 3.4's audit trail even though the actual attribution.json result is unaffected (each run is parsed into memory immediately, before the next one could overwrite it on disk).
current_state_with_coverage - out_dir/current_state_with_coverage.csv: current_state_test.csv's non-test rows (is_test=True rows are excluded entirely, not scored), each with coverage_status, covered, test_files, load_time_only, and some_coverage added. some_coverage is a plain True/False summary - True only when coverage_status is "covered" (at least one test's isolated run reached the span), False for everything else (uncovered, unmeasured_file, and unmeasured_repo all collapse to False) - a deliberate simplification for a single boolean column, not a claim those three are equivalent; coverage_status still carries the real distinction. Always a new file - the join phase never edits current_state_test.csv or any other input in place.
report - summary of collect results (per-repo namespace ok/fail/timeout breakdown) and join results (covered/uncovered/unmeasured breakdown, two coverage-rate numbers).

## Instructions

1. Run the collect phase: for every verified_ok repo in test_check_path, find its test namespaces (parsed from :test-paths in project.clj, then every `(ns ...)` form under those paths) and run lein-cloverage once per namespace in isolation (`lein update-in :plugins conj '[lein-cloverage ...]' -- cloverage --lcov --test-ns-regex ^<namespace>$`) - project.clj itself is never touched. A hit in one namespace's isolated run means that namespace's own test file actually reaches that line - this is what makes the output name *which* test file(s) reach each detection, not just whether the suite as a whole touches it.

```sh
~/.venvs/check-lein-test/bin/python3 ${CLAUDE_SKILL_DIR}/scripts/verify_coverage.py collect \
  --test-check-csv test_check.csv --repos-root repos_path --out-dir out_dir --timeout 300
```

Use `--verified-tsv some_tsv_path` instead of `--test-check-csv` if a plain TSV is ever the only thing available instead of test_check.csv.

1.1. This reruns cloverage once per test namespace, not once per repo - a repo with N test namespaces costs N cloverage runs. Real observed per-namespace times during this skill's own development ranged ~10-30s typically, with occasional outliers past 200s (e.g. a benchmark namespace). Launch it as a background process rather than waiting on it synchronously, especially across many repos.

1.2. Resumable at the repo level via out_dir/coverage_results.csv - a killed or restarted run skips any repo already recorded there, but a repo interrupted mid-way through its own namespace list restarts that repo's namespaces from scratch on resume (no per-namespace checkpoint). Use `--limit N` for a small smoke test before committing to a full run. `--timeout` (seconds, default 300) is a PER-NAMESPACE budget, not per-repo - raise it if namespaces are timing out that would plausibly finish given more time.

2. Once collect finishes, retry the cases that look transient:

2.1. From out_dir/coverage_results.csv, select rows where `status` is `"no_usable_namespaces"` (every namespace found failed or timed out) - skim the per-namespace logs under out_dir/logs/<repo>/ for a real, reproducible incompatibility (Cloverage's per-namespace instrumentation is a narrower, less-exercised code path than a plain aggregate run, worth checking before assuming it's unfixable) versus something transient. Don't retry `"no_test_namespaces_found"` rows - that's a real structural fact (no test namespaces exist under this repo's :test-paths), not noise.

2.2. Remove exactly those rows from coverage_results.csv (leave every other row untouched - the script's resume logic treats any repo still present as done and skips it, redoing every namespace for a removed repo).

2.3. Re-run the same command from step 1. With those rows gone, the script reprocesses only the retried repos and appends fresh rows, leaving everything else as-is.

2.4. Repeat 2.1-2.3 at most once more. If a repo still fails on the second attempt, stop retrying it and report it as a real failure.

3. Run the join phase: score every non-test occurrence in current_state_test.csv against the collected per-namespace attribution data.

```sh
~/.venvs/check-lein-test/bin/python3 ${CLAUDE_SKILL_DIR}/scripts/verify_coverage.py join \
  --current-state-test current_state_test_path --coverage-results out_dir/coverage_results.csv \
  --repos-root repos_path --out out_dir/current_state_with_coverage.csv
```

3.1. Coverage rule: an occurrence is `covered` if any line in its span was hit by at least one test namespace's isolated run - `test_files` names exactly which one(s) (semicolon-joined absolute paths). Every row gets a `coverage_status` - `covered`, `uncovered` (the span was instrumented - a real DA: entry existed - in at least one namespace's run, but never hit by any of them), `unmeasured_file` (no namespace's isolated run ever produced a DA: entry for any line in this span at all - never counted as uncovered, since that would silently bias the count with cases that were never actually checked), or `unmeasured_repo` (this repo has no usable attribution.json - collect never ran for it, found zero test namespaces, every namespace failed/timed out, or attribution.json is missing on disk even though coverage_results.csv says "ok", which happens if `target/` got wiped by a `git clean -fdx` repo refresh since the collect run).

3.2. Known limitation inherent to this per-namespace mechanism (not a bug to fix, just a real edge to know about): isolating each test namespace one at a time can only load whatever that ONE namespace's own tests happen to require. Code that only gets loaded through an interaction BETWEEN multiple test namespaces running together (rare, but possible with shared/global state) could show `unmeasured_file` here even though a full aggregate whole-suite run would have seen it - the union of N isolated runs isn't provably identical to one combined run.

3.3. `load_time_only` answers a different question than coverage_status: does this line only execute because its namespace loaded (a top-level def/defprotocol/ns/defmulti/... form - runs unconditionally the instant anything requires that namespace, test-related or not), or does reaching it require something to actually CALL a function (defn/fn/defmethod/defmacro/deftype/defrecord/extend-protocol/extend-type body, or a #(...) literal)? A `covered` occurrence with `load_time_only=True` is a much weaker signal than one with `load_time_only=False` - even knowing *which* test file's run hit it, "covered" there can mean nothing more than "that test file's own dependency chain happens to load this namespace", not that anything in it was actually exercised as logic. The join phase's printed summary reports both a raw coverage rate and one excluding load_time_only rows - treat the second one as the trustworthy number.

3.4. Before trusting the output, spot-check a random sample of scored rows directly against the raw per-namespace lcov.info files (out_dir/by_ns/<repo>/<namespace>/lcov.info) rather than just trusting the script ran without error - for a `covered` row, confirm the namespace(s) listed in `test_files` are the only ones with a real positive DA: entry for that line, and every other namespace shows a real `DA:<line>,0` (not just missing); for `unmeasured_file`, confirm no namespace has any DA: entry for that line at all. This exact kind of check caught two real bugs during this skill's earlier (aggregate-coverage) development, and re-validated cleanly against a live 5-repo run when the mechanism was switched to per-namespace attribution - a missing DA: entry silently defaulting to "0 hits" instead of "no evidence" is the single easiest mistake to reintroduce when touching this code, since it's exactly what run_test_attribution.py's own original design did before being adapted here.

4. Report a summary: total verified_ok repos in test_check_path, how many collect succeeded/had no usable namespaces/found no test namespaces at all (and whether a step-2 retry fixed any), total occurrences scored (covered + uncovered) vs unmeasured (split unmeasured_file vs unmeasured_repo), the coverage rate both raw and excluding load_time_only rows, what fraction of scored occurrences were load_time_only, and - unique to this attribution-based version - which test file(s) most often show up covering detections, if that's useful context (e.g. a handful of test files accounting for most of the covered occurrences might mean the rest of the suite is thin). Name that this is a *sample* of the verified_ok repos unless every one of them was included, since coverage rates swing widely at small sample sizes (observed 11.8%-93.3% across five-repo pilots during this skill's earlier aggregate-coverage development).
