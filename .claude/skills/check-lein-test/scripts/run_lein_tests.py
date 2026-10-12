#!/usr/bin/env python3
"""
Verify `lein install` + `lein test` for a set of Leiningen project.clj files,
deterministically and non-interactively, and record structured outcomes.

Input: lein_config.csv (as produced by the identify-leiningen skill), with
       columns: repo, project_clj_path (absolute path to a project.clj).
       A repo with N modules (N project.clj files) appears as N rows -
       every one of them is verified independently.

Two phases, to handle two problems at once:

Phase 1 - install (grouped by repo, round-based):
  A multi-module repo's modules can depend on each other (e.g. mulog-kafka
  needs mulog-core installed locally first). `lein install` resolves deps
  AND publishes the module's own artifact to the local repo, so running it
  round-by-round within a repo - retrying only what failed - lets a sibling
  module become resolvable after its dependency's first round succeeds.
  Each repo's own rounds run strictly in sequence (never parallel with each
  other), but different repos are fully independent, so repos are processed
  concurrently across a small thread pool (--install-workers) to bound how
  much concurrent traffic hits the shared ~/.m2 local repo.

  Each module's install result is persisted to <out-dir>/install_state.csv
  the moment it's known (whichever round produced it) - not held in memory
  until Phase 2 starts. Without this, a process killed mid-Phase-1 (e.g. by
  the host running low on memory) would lose every completed install and
  redo them all from scratch on resume; with it, resume only re-installs
  whatever hadn't finished yet.

Phase 2 - test (flat across all modules, higher concurrency):
  Once a module's install has succeeded (in whichever round), `lein test`
  mostly reads already-resolved jars and runs in an isolated project dir -
  the main shared resource is CPU/memory, not a correctness-sensitive shared
  cache - so this phase uses a larger thread pool (--test-workers).

Classification per module:
  - install_status: ok | fail | timeout | error (of whichever round produced
    the final recorded result; error means the runner itself hit an
    unexpected exception, e.g. permissions or disk issues - not a test outcome)
  - install_round: which round (1, 2, ...) that result came from
  - test_status: skipped (install never succeeded) | ran | timeout | crash
    (nonzero exit, no test summary line) | error (same meaning as above)
  - ran_to_completion: True if lein printed a "Ran N tests containing M
    assertions" summary, i.e. the test task itself executed regardless of
    pass/fail
  - all_tests_passed: True iff lein test exit code == 0
  - verified_ok: ran_to_completion and nonzero_tests and all_tests_passed

Each project.clj is identified by a module_key: its directory path relative
to --repos-root (e.g. "BrunoBonacci__mulog/mulog-kafka" for a submodule, or
just "200ok-ch__org-parser" when project.clj sits at the repo root). This
key is unique per project.clj even for multi-module repos, and is used both
as the resume identifier and as the logs/<module_key>/ directory name.

Full stdout+stderr of each command is saved under <out-dir>/logs/<module_key>/
(install_round1.log, install_round2.log if a retry happened, test.log).
Results are appended to <out-dir>/test_check.csv incrementally via pandas
(safe to Ctrl-C and resume manually - rows already in test_check.csv are
skipped entirely, in both phases).

Non-interactive by construction: stdin is /dev/null so any prompt-waiting plugin fails fast
instead of hanging past the timeout wrapper's grace, and `timeout -k` force-kills stragglers.
"""
import argparse
import os
import re
import subprocess
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

TEST_SUMMARY_RE = re.compile(r"Ran (\d+) tests? containing (\d+) assertions?", re.IGNORECASE)
# Non-clojure.test runners (midje, rdt, kaocha, ...) print their own summary
# format and won't match here even when every test passed. Rather than
# growing an ever-incomplete list of per-runner regexes, that judgment call
# is left to the check-lein-test skill, which reads the actual log.

CSV_FIELDS = [
    "module_key", "repo", "project_clj_path",
    "install_exit", "install_status", "install_round", "install_seconds",
    "test_exit", "test_status", "test_seconds",
    "ran_to_completion", "tests_run", "assertions_run",
    "nonzero_tests", "all_tests_passed", "verified_ok",
    "manually_classified",
    "install_log", "test_log",
]
# manually_classified starts False for every row the script writes. The
# check-lein-test skill's log-verification step flips it to True (and
# corrects the surrounding fields) when a human/agent overrides what this
# script concluded - see SKILL.md step 2.2. The script itself never sets
# this to True; it has no basis to judge its own output.

INSTALL_STATE_FIELDS = [
    "module_key", "repo", "project_clj_path",
    "install_exit", "install_status", "install_round", "install_seconds", "install_log",
]

write_lock = threading.Lock()
install_state_lock = threading.Lock()


def run_cmd(cmd, cwd, timeout_s, log_path):
    start = time.time()
    with open(log_path, "w") as log:
        try:
            proc = subprocess.run(
                ["timeout", "-k", "10", str(timeout_s)] + cmd,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            exit_code = proc.returncode
        except Exception as e:
            log.write(f"\n[runner error] {e}\n")
            exit_code = -1
    elapsed = time.time() - start
    return exit_code, elapsed


def classify_install(exit_code):
    if exit_code == 124 or exit_code == 137:
        return "timeout"
    if exit_code == 0:
        return "ok"
    return "fail"


def classify_test(exit_code, log_path):
    if exit_code == 124 or exit_code == 137:
        return "timeout", False, 0, 0
    text = ""
    try:
        text = log_path.read_text(errors="replace")
    except OSError:
        pass
    m = TEST_SUMMARY_RE.search(text)
    ran = bool(m)
    tests_run = int(m.group(1)) if m else 0
    assertions_run = int(m.group(2)) if m else 0
    status = "ran" if ran else "crash"
    return status, ran, tests_run, assertions_run


def append_result(results_path, row):
    with write_lock:
        pd.DataFrame([row], columns=CSV_FIELDS).to_csv(
            results_path, mode="a", header=not results_path.exists(), index=False
        )


def append_install_state(state_path, row):
    with install_state_lock:
        pd.DataFrame([row], columns=INSTALL_STATE_FIELDS).to_csv(
            state_path, mode="a", header=not state_path.exists(), index=False
        )


def install_repo(repo, modules, install_timeout, install_rounds, logs_dir, state_path):
    """modules: list of (module_key, project_dir, project_clj_path). Returns
    {module_key: {install fields}}. Persists each module's result to state_path
    the moment it's known, so a kill mid-phase loses at most the module
    currently running, not the whole repo/batch."""
    results = {}
    pending = list(modules)
    for rnd in range(1, install_rounds + 1):
        if not pending:
            break
        next_pending = []
        for module_key, project_dir, project_clj_path in pending:
            log_dir = logs_dir / module_key
            log_path = log_dir / f"install_round{rnd}.log"
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
                exit_code, seconds = run_cmd(["lein", "install"], project_dir, install_timeout, log_path)
                status = classify_install(exit_code)
            except Exception as e:
                # Anything unexpected (permissions, disk full, ...) shouldn't take
                # down the whole repo's install or the batch - record it and move on.
                exit_code, seconds, status = -1, 0.0, "error"
                try:
                    log_path.write_text(f"[runner error] {e}\n")
                except OSError:
                    pass
            fields = {
                "install_exit": exit_code,
                "install_status": status,
                "install_round": rnd,
                "install_seconds": round(seconds, 1),
                "install_log": log_path,
            }
            results[module_key] = fields
            append_install_state(state_path, {
                "module_key": module_key,
                "repo": repo,
                "project_clj_path": str(project_clj_path),
                **{k: (str(v) if k == "install_log" else v) for k, v in fields.items()},
            })
            if status != "ok":
                next_pending.append((module_key, project_dir, project_clj_path))
        pending = next_pending
    return results


def run_test_phase(module_key, repo, project_clj_path, project_dir, test_timeout, logs_dir, out_dir):
    log_dir = logs_dir / module_key
    test_log = log_dir / "test.log"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        test_exit, test_s = run_cmd(["lein", "test"], project_dir, test_timeout, test_log)
        test_status, ran_to_completion, tests_run, assertions_run = classify_test(test_exit, test_log)
        all_tests_passed = (test_exit == 0)
        nonzero_tests = tests_run > 0
        verified_ok = ran_to_completion and nonzero_tests and all_tests_passed
    except Exception as e:
        # Same rationale as install_repo's try/except: one module's unexpected
        # error shouldn't take down the whole test phase.
        try:
            test_log.write_text(f"[runner error] {e}\n")
        except OSError:
            pass
        test_exit, test_s = -1, 0.0
        test_status = "error"
        ran_to_completion = False
        tests_run = 0
        assertions_run = 0
        nonzero_tests = False
        all_tests_passed = False
        verified_ok = False

    return {
        "test_exit": test_exit,
        "test_status": test_status,
        "test_seconds": round(test_s, 1),
        "ran_to_completion": ran_to_completion,
        "tests_run": tests_run,
        "assertions_run": assertions_run,
        "nonzero_tests": nonzero_tests,
        "all_tests_passed": all_tests_passed,
        "verified_ok": verified_ok,
        "test_log": str(test_log.relative_to(out_dir)),
    }


def skip_test_row():
    return {
        "test_exit": "",
        "test_status": "skipped",
        "test_seconds": 0.0,
        "ran_to_completion": False,
        "tests_run": 0,
        "assertions_run": 0,
        "nonzero_tests": False,
        "all_tests_passed": False,
        "verified_ok": False,
        "test_log": "",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos-root", default=os.path.expanduser("~/Documents/tmp/refactorings"))
    ap.add_argument("--lein-config", required=True, help="lein_config.csv: repo,project_clj_path")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--install-timeout", type=int, default=300,
                     help="raised from an earlier 240s default - too tight for a meaningful slice of real Clojure builds")
    ap.add_argument("--test-timeout", type=int, default=900,
                     help="raised from an earlier 300s default - embedded-broker and generative/benchmark suites routinely need 10-20 minutes")
    ap.add_argument("--install-rounds", type=int, default=2,
                     help="retry rounds for `lein install` within a repo, so a module can pick up a sibling module installed in an earlier round")
    ap.add_argument("--install-workers", type=int, default=1,
                     help="repos installed concurrently (each repo's own rounds stay sequential)")
    ap.add_argument("--test-workers", type=int, default=os.cpu_count() or 1,
                     help="modules tested concurrently, flat across all repos")
    ap.add_argument("--limit", type=int, default=0, help="0 = no limit")
    args = ap.parse_args()

    repos_root = Path(args.repos_root).resolve()
    out_dir = Path(args.out_dir)
    logs_dir = out_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "test_check.csv"
    install_state_path = out_dir / "install_state.csv"

    config = pd.read_csv(args.lein_config)
    config["project_clj_path"] = config["project_clj_path"].apply(lambda p: Path(p).resolve())
    config["module_key"] = config["project_clj_path"].apply(
        lambda p: str(p.parent.relative_to(repos_root))
    )
    if args.limit:
        config = config.head(args.limit)

    already_done = set()
    if results_path.exists():
        already_done = set(pd.read_csv(results_path)["module_key"])

    pending_rows = [r for r in config.itertuples(index=False) if r.module_key not in already_done]
    skipped_count = len(config) - len(pending_rows)
    print(f"total project.clj: {len(config)} | already done: {skipped_count} | to process: {len(pending_rows)}")

    module_info = {r.module_key: r for r in pending_rows}

    # Phase 1 results are persisted incrementally (see install_repo) so a kill
    # mid-phase doesn't lose completed installs - load whatever survived from
    # a prior attempt before deciding what still needs a fresh `lein install`.
    install_results = {}
    if install_state_path.exists():
        state_df = pd.read_csv(install_state_path).drop_duplicates(subset="module_key", keep="last")
        for r in state_df.itertuples(index=False):
            if r.module_key in module_info:
                install_results[r.module_key] = {
                    "install_exit": r.install_exit,
                    "install_status": r.install_status,
                    "install_round": r.install_round,
                    "install_seconds": r.install_seconds,
                    "install_log": r.install_log,
                }

    needs_install = [r for r in pending_rows if r.module_key not in install_results]
    print(f"install already known from a prior run: {len(pending_rows) - len(needs_install)} | needs install: {len(needs_install)}")

    by_repo = defaultdict(list)
    for r in needs_install:
        by_repo[r.repo].append((r.module_key, r.project_clj_path.parent, r.project_clj_path))

    # Phase 1: install, grouped by repo, repos run concurrently, rounds within a repo stay sequential.
    print(f"\n=== Phase 1: lein install ({len(by_repo)} repos, {args.install_workers} workers, up to {args.install_rounds} rounds) ===", flush=True)
    with ThreadPoolExecutor(max_workers=args.install_workers) as pool:
        futures = {
            pool.submit(install_repo, repo, modules, args.install_timeout, args.install_rounds, logs_dir, install_state_path): repo
            for repo, modules in by_repo.items()
        }
        done_repos = 0
        for future in as_completed(futures):
            repo = futures[future]
            try:
                repo_results = future.result()
            except Exception as e:
                # install_repo already catches per-module errors; this only fires
                # for something outside that (e.g. the pool itself misbehaving).
                # Don't let it kill the rest of the batch - mark every module of
                # this repo as errored so it still gets a row and is retry-eligible.
                print(f"[install ERROR] {repo}: {e}", flush=True)
                repo_results = {}
                for module_key, _, project_clj_path in by_repo[repo]:
                    err_log = logs_dir / module_key / "install_round1.log"
                    err_log.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        err_log.write_text(f"[executor error] {e}\n")
                    except OSError:
                        pass
                    fields = {
                        "install_exit": -1, "install_status": "error", "install_round": 1,
                        "install_seconds": 0.0, "install_log": err_log,
                    }
                    repo_results[module_key] = fields
                    append_install_state(install_state_path, {
                        "module_key": module_key, "repo": repo, "project_clj_path": str(project_clj_path),
                        **{k: (str(v) if k == "install_log" else v) for k, v in fields.items()},
                    })
            install_results.update(repo_results)
            done_repos += 1
            print(f"[install {done_repos}/{len(by_repo)}] {repo}: done", flush=True)

    # Phase 2: test - modules whose install ultimately succeeded run in parallel;
    # modules whose install never succeeded get an immediate skip row (no worker needed).
    ok_modules = [mk for mk, res in install_results.items() if res["install_status"] == "ok"]
    failed_modules = [mk for mk, res in install_results.items() if res["install_status"] != "ok"]
    print(f"\n=== Phase 2: lein test ({len(ok_modules)} to run, {len(failed_modules)} skipped, {args.test_workers} workers) ===", flush=True)

    def build_row(module_key, test_fields):
        entry = module_info[module_key]
        install_fields = install_results[module_key]
        row = {
            "module_key": module_key,
            "repo": entry.repo,
            "project_clj_path": str(entry.project_clj_path),
            "install_exit": install_fields["install_exit"],
            "install_status": install_fields["install_status"],
            "install_round": install_fields["install_round"],
            "install_seconds": install_fields["install_seconds"],
            "manually_classified": False,
            "install_log": str(Path(install_fields["install_log"]).relative_to(out_dir)),
        }
        row.update(test_fields)
        return row

    for module_key in failed_modules:
        row = build_row(module_key, skip_test_row())
        append_result(results_path, row)
        print(f"  {module_key}: install={install_results[module_key]['install_status']} -> test skipped")

    with ThreadPoolExecutor(max_workers=args.test_workers) as pool:
        futures = {}
        for module_key in ok_modules:
            entry = module_info[module_key]
            futures[pool.submit(
                run_test_phase, module_key, entry.repo, entry.project_clj_path,
                entry.project_clj_path.parent, args.test_timeout, logs_dir, out_dir,
            )] = module_key

        done_tests = 0
        for future in as_completed(futures):
            module_key = futures[future]
            try:
                test_fields = future.result()
            except Exception as e:
                # Same rationale as the install-phase guard above.
                print(f"[test ERROR] {module_key}: {e}", flush=True)
                test_fields = skip_test_row()
                test_fields["test_status"] = "error"
            row = build_row(module_key, test_fields)
            append_result(results_path, row)
            done_tests += 1
            print(f"[test {done_tests}/{len(ok_modules)}] {module_key}: "
                  f"test={test_fields['test_status']} tests_run={test_fields['tests_run']} "
                  f"passed={test_fields['all_tests_passed']} verified_ok={test_fields['verified_ok']}", flush=True)

    print(f"\nDone. Results: {results_path}")


if __name__ == "__main__":
    main()
