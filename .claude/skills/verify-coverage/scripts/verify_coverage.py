#!/usr/bin/env python3
"""
Verify whether each ARIT detection (current_state_test.csv, arit-batch-
detection's output) is actually covered by the real test suite - and, more
specifically than a plain yes/no, WHICH test file(s) reach it - using
Cloverage runtime line-coverage data isolated per test namespace, not a
single aggregate whole-suite run.

Built from run_test_attribution.py / run_attribution_batch.py /
write_coverage_json.py's mechanism (previously left out of this script in
favor of a cheaper aggregate `lein cloverage` run per repo - see git history
for that version). Switched to this one because "is there any test file
that reaches this code" is a more useful question than "was this line
merely executed by the suite as a whole" for what this data feeds into
(refactor-safety judgments), and per this project's own decision, the cost
of running Cloverage once per test namespace instead of once per repo is
not a concern here.

Mechanism: for each repo, find its test namespaces (parse :test-paths out
of project.clj, then find every (ns ...) form under those paths), and run
`lein update-in :plugins conj '[lein-cloverage ...]' -- cloverage --lcov
--test-ns-regex <ns>` once per namespace, in isolation - project.clj itself
is never touched. A hit in that isolated run's lcov.info means that
specific test namespace's own test run exercised that line, not the suite
as a whole. This directly answers "which test file(s) reach this code",
not just "was it reached by something".

Critical correctness detail, easy to get wrong by porting
run_test_attribution.py unchanged: its ORIGINAL attribution.json only ever
recorded lines that were positively HIT (hits > 0) by some namespace's run -
a line with zero DA: entries across every single namespace run and a line
that was genuinely instrumented-but-never-hit in every run would both
simply be ABSENT from that structure, indistinguishable from each other.
Porting that unchanged would have silently reintroduced the exact bug this
script's previous (aggregate-lcov) version had to find and fix: treating
"never checked" the same as "checked and found untested". Fixed here by
recording the union of every (file, line) key seen in ANY namespace's lcov
- even with hits=0, even with an empty resulting test-file list - so a key
being present at all still means "instrumented in at least one namespace's
isolated run", independent of whether any namespace actually hit it.

Two phases, run as subcommands (same split as check-lein-test's
run_lein_tests.py - slow/resumable data collection vs. fast/deterministic
analysis):

  collect - for each already-verified-working repo (check-lein-test's
    verified_ok rows, via --test-check-csv or a plain --verified-tsv), run
    the per-namespace attribution described above and write
    <project_dir>/target/coverage-report/attribution.json. Slow (reruns the
    real test suite once per test namespace), resumable at the REPO level
    via out_dir/coverage_results.csv - a kill mid-repo loses that repo's
    in-progress namespace runs (no finer-grained resumability within a
    single repo, matching run_attribution_batch.py's original design).

  join - for every non-test occurrence in current_state_test.csv, look up
    its file+line-span in the matching repo's attribution.json and decide
    covered/uncovered and, when covered, exactly which test file(s) did it.
    Fast, deterministic, safe to re-run freely.

    Coverage rule: an occurrence is "covered" if ANY line in
    [start_line, end_line] has at least one test file attributed to it.
    Same any-line-in-span rule the aggregate version used, applied to
    per-namespace data instead of a single lcov.info.

    is_test=True occurrences are excluded entirely before scoring - coverage
    is meaningless for test code itself. Every remaining row gets a
    coverage_status, never silently dropped or miscounted:
      covered         - at least one namespace's isolated run hit this span,
                         and test_files names which one(s)
      uncovered       - the span was instrumented (a DA: entry existed) in
                         at least one namespace's run, but never actually
                         hit by any of them
      unmeasured_file - no namespace's isolated run ever produced a DA:
                         entry for any line in this span - either the file
                         never got loaded during any of those runs, or it
                         falls in an instrumentation gap Cloverage never
                         separately tracks (e.g. a bare literal inside a
                         map/vector), or the occurrence has no line span at
                         all. Never treated as uncovered - see the
                         correctness note above.
      unmeasured_repo - this repo has no usable attribution.json at all
                         (collect never ran for it, found zero test
                         namespaces, every namespace it found failed/timed
                         out, or attribution.json is missing on disk even
                         though coverage_results.csv says "ok" - target/ is
                         untracked build output and gets wiped by a
                         `git clean -fdx` repo refresh, a real risk seen
                         more than once during this project)

    Known limitation inherent to the per-namespace mechanism, not this
    script: isolating each test namespace one at a time can only load
    whatever that ONE namespace's own tests happen to require. A namespace
    that only gets loaded through some interaction BETWEEN multiple test
    namespaces running together (rare, but possible with global/shared
    state) could show unmeasured_file here even though a full aggregate
    whole-suite run would have seen it - the union of N isolated runs is
    not provably identical to one combined run. Not observed as an actual
    problem in this project's pilots, but worth knowing the mechanism has
    this edge, not just the previous aggregate one.

load_time_only: unchanged from the aggregate version - a second,
independent flag alongside coverage_status, answering a different question
than "did the line run" - "does this line only run because the namespace
loaded, or does reaching it require something to actually CALL a
function?" See find_function_like_spans's own docstring for the mechanism
and how it was validated.

Output: current_state_with_coverage.csv - current_state_test.csv's columns,
with is_test=True rows excluded and coverage_status/covered/test_files/
load_time_only/some_coverage added to the rest (covered and load_time_only
are NA where not applicable; test_files is an empty string, not NA, for a
genuinely uncovered/instrumented-but-never-hit row, to distinguish it from
"not scored at all"). some_coverage is a plain True/False summary -
True only for coverage_status=="covered", False for every other status
including unmeasured_file/unmeasured_repo. That's a deliberate
simplification for a single boolean column, not a claim that "confirmed
untested" and "couldn't measure" are the same thing - that distinction is
still there in coverage_status for anyone who needs it; some_coverage never
replaces it, only summarizes it. Always written to a NEW file (--out) -
the join phase never edits current_state_test.csv or any other input in
place. The join phase reads its own output back after writing and checks
it against the in-memory data before declaring success.

Needs pandas throughout (collect's per-repo/per-namespace mechanism itself
is stdlib-only, but --test-check-csv normalization uses it) - use the
dedicated venv if pandas isn't on the system python3:
~/.venvs/check-lein-test/bin/python3 verify_coverage.py ...
"""
import argparse
import csv
import json
import os
import re
import subprocess
import time
from pathlib import Path

import pandas as pd

CLOVERAGE_VERSION = "1.2.4"

ATTRIBUTION_RESULTS_FIELDS = [
    "repo", "project_clj", "n_namespaces", "n_ok", "n_fail",
    "seconds", "status", "attribution_path",
]

# list-valued fields have no native CSV representation - join with this
# instead of letting pandas fall back to Python repr ("['a', 'b']")
LIST_FIELD_SEP = "; "

NS_RE = re.compile(r"\(ns\s+([A-Za-z0-9.\-_!?*+<>=]+)")
SF_RE = re.compile(r"^SF:(.+)$")
DA_RE = re.compile(r"^DA:(\d+),(\d+)$")


# --------------------------------------------------------------- collect


def get_test_paths(project_clj):
    """Parse :test-paths out of project.clj, falling back to the
    conventional "test" directory if it's absent."""
    text = project_clj.read_text(errors="replace") if project_clj.is_file() else ""
    text = re.sub(r'#_\s*"[^"]*"', "", text)
    text = re.sub(r"#_\s*[A-Za-z0-9._\-/]+", "", text)
    m = re.search(r":test-paths\s*\[([^\]]*)\]", text)
    if m:
        found = re.findall(r'"([^"]+)"', m.group(1))
        if found:
            return found
    return ["test"]


def find_test_namespaces(project_dir, test_paths):
    """Return [(namespace_symbol, absolute_test_filepath), ...] for every
    (ns ...) form found under project_dir/<test_path>/**/*.{clj,cljc,cljs}."""
    out = []
    for tp in test_paths:
        base = project_dir / tp
        if not base.is_dir():
            continue
        for ext in ("*.clj", "*.cljc", "*.cljs"):
            for f in base.rglob(ext):
                try:
                    text = f.read_text(errors="replace")
                except OSError:
                    continue
                m = NS_RE.search(text)
                if m:
                    out.append((m.group(1), str(f.resolve())))
    return out


def sanitize(ns):
    return re.sub(r"[^A-Za-z0-9_.\-]", "_", ns)


def run_cloverage_for_ns(project_dir, ns, out_dir, timeout_s, log_path):
    escaped = re.escape(ns)
    cmd = [
        "timeout", "-k", "10", str(timeout_s),
        "lein", "update-in", ":plugins", "conj",
        f'[lein-cloverage "{CLOVERAGE_VERSION}"]', "--",
        "cloverage", "--lcov", "-o", str(out_dir),
        "--test-ns-regex", f"^{escaped}$",
    ]
    start = time.time()
    with open(log_path, "w") as log:
        try:
            proc = subprocess.run(
                cmd, cwd=project_dir, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT,
            )
            exit_code = proc.returncode
        except Exception as e:
            log.write(f"\n[runner error] {e}\n")
            exit_code = -1
    return exit_code, time.time() - start


def parse_lcov(lcov_path, project_dir):
    """Return {absolute_filepath: {line: hitcount}}."""
    coverage = {}
    current_file = None
    with open(lcov_path, errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            m = SF_RE.match(line)
            if m:
                current_file = str((project_dir / m.group(1)).resolve())
                coverage[current_file] = {}
                continue
            m = DA_RE.match(line)
            if m and current_file:
                coverage[current_file][int(m.group(1))] = int(m.group(2))
            if line == "end_of_record":
                current_file = None
    return coverage


def collect_repo_attribution(name, project_clj_rel_path, repos_root, timeout_s, work_dir):
    """Run cloverage once per test namespace for one repo, and build the
    union attribution dict across all namespace runs - see module docstring
    for why a key's mere PRESENCE (even with an empty test-file set) has to
    be preserved as "instrumented", distinct from a key's absence.

    Returns (ns_status: {namespace: "ok"|"fail"|"timeout"},
             attribution: {abs_source_file: {line: set(test_files)}})."""
    project_clj = repos_root / project_clj_rel_path
    project_dir = project_clj.parent
    test_paths = get_test_paths(project_clj)
    namespaces = find_test_namespaces(project_dir, test_paths)

    attribution = {}
    ns_status = {}
    logs_dir = work_dir / "logs" / name
    logs_dir.mkdir(parents=True, exist_ok=True)

    for i, (ns, test_file) in enumerate(namespaces, 1):
        # index suffix, not just sanitize(ns): the same namespace symbol can
        # be declared in two different files (e.g. a .clj/.cljs pair testing
        # the same cljc source) - without the suffix, the second run's
        # lcov.info silently overwrites the first's on disk (the in-memory
        # attribution accumulation below is unaffected, since each run is
        # parsed immediately after it finishes and before any later run
        # could overwrite it, but the persisted directory would stop being a
        # trustworthy per-run audit trail). Confirmed happening for real in
        # metosin__sieppari (sieppari.core-async-test, sieppari.core-execute-test
        # each exist as both test/clj/... and test/cljs/... with identical ns).
        ns_out_dir = work_dir / "by_ns" / name / f"{sanitize(ns)}__{i}"
        log_path = logs_dir / f"{sanitize(ns)}__{i}.log"
        print(f"    [{i}/{len(namespaces)}] {ns} ...", flush=True)
        exit_code, elapsed = run_cloverage_for_ns(project_dir, ns, ns_out_dir, timeout_s, log_path)
        lcov = ns_out_dir / "lcov.info"
        if not lcov.is_file() or lcov.stat().st_size == 0:
            ns_status[ns] = "timeout" if exit_code in (124, 137) else "fail"
            print(f"        -> {ns_status[ns]} ({elapsed:.1f}s)")
            continue
        ns_status[ns] = "ok"
        print(f"        -> ok ({elapsed:.1f}s)")
        file_cov = parse_lcov(lcov, project_dir)
        for src_file, lines in file_cov.items():
            for line, hits in lines.items():
                bucket = attribution.setdefault(src_file, {}).setdefault(line, set())
                if hits > 0:
                    bucket.add(test_file)

    return ns_status, attribution


def write_attribution_json(out_path, ns_status, attribution):
    serializable = {
        f: {str(ln): sorted(tests) for ln, tests in lines.items()}
        for f, lines in attribution.items()
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"namespaces": ns_status, "attribution": serializable}, f)


def load_verified_entries(args, repos_root):
    """Return [(repo, project_clj_relative_path), ...] from either
    --verified-tsv (repo<TAB>relative_path, no header - e.g.
    lein_test_runs/verified_141.tsv) or --test-check-csv (check-lein-test's
    own test_check.csv output, filtered to verified_ok rows).

    test_check.csv needs normalizing before use here, not just filtering:
    its `repo` column is "owner/name" (a bare "/"), not the "owner__name"
    clone-directory form the rest of this pipeline uses (verified_141.tsv,
    the refactorings/ checkout dirs) - a literal "/" in `repo` would make
    collect's per-repo log path unwritable (logs/owner/name.log, no such
    subdirectory), failing the whole repo rather than just producing a
    wrong name. Its `project_clj_path` is also absolute rather than
    relative to repos_root. Both are fixed here rather than documented as a
    separate manual step, since there was never a reason for this
    normalization to live outside the script - it's pure data massaging,
    the same kind the join phase already does for current_state_test.csv."""
    if args.test_check_csv:
        df = pd.read_csv(args.test_check_csv)
        verified = df[df["verified_ok"]]
        repos = verified["repo"].str.replace("/", "__", regex=False)
        rel_paths = verified["project_clj_path"].apply(
            lambda p: str(Path(p).relative_to(repos_root))
        )
        return list(zip(repos, rel_paths))

    with open(args.verified_tsv) as f:
        return [tuple(line.rstrip("\n").split("\t", 1)) for line in f if line.strip()]


def collect_coverage(args):
    repos_root = Path(args.repos_root)
    out_dir = Path(args.out_dir)
    results_path = out_dir / "coverage_results.csv"

    entries = load_verified_entries(args, repos_root)
    if args.limit:
        entries = entries[: args.limit]

    # keyed by (repo, project_clj), not repo alone - a multi-module repo
    # can have several independent rows sharing one repo name, and using
    # repo name alone as the dedup key means retrying ONE failing module
    # (by removing just its row) silently no-ops the moment ANY sibling
    # module of that same repo is still present in the results file, since
    # the repo name alone already reads as "done". Found for real: retrying
    # aphyr__tesser/core after removing only its row was silently skipped
    # because aphyr__tesser/math (a different module, already ok) was still
    # in coverage_results.csv.
    already_done = set()
    write_header = not results_path.exists()
    if not write_header:
        with open(results_path) as f:
            for row in csv.DictReader(f):
                already_done.add((row["repo"], row["project_clj"]))

    with open(results_path, "a", newline="") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=ATTRIBUTION_RESULTS_FIELDS)
        if write_header:
            writer.writeheader()

        for i, (name, rel_path) in enumerate(entries, 1):
            if (name, rel_path) in already_done:
                print(f"[{i}/{len(entries)}] {name}: already done, skipping")
                continue

            print(f"[{i}/{len(entries)}] {name}: per-namespace attribution ...", flush=True)
            start = time.time()
            ns_status, attribution = collect_repo_attribution(
                name, rel_path, repos_root, args.timeout, out_dir
            )
            elapsed = time.time() - start

            n_ns = len(ns_status)
            n_ok = sum(1 for s in ns_status.values() if s == "ok")
            n_fail = n_ns - n_ok

            project_dir = (repos_root / rel_path).parent
            attribution_path = project_dir / "target" / "coverage-report" / "attribution.json"

            if n_ns == 0:
                status = "no_test_namespaces_found"
                attribution_path_str = ""
            elif n_ok == 0:
                status = "no_usable_namespaces"
                attribution_path_str = ""
            else:
                write_attribution_json(attribution_path, ns_status, attribution)
                status = "ok"
                attribution_path_str = str(attribution_path)

            writer.writerow({
                "repo": name,
                "project_clj": rel_path,
                "n_namespaces": n_ns,
                "n_ok": n_ok,
                "n_fail": n_fail,
                "seconds": round(elapsed, 1),
                "status": status,
                "attribution_path": attribution_path_str,
            })
            out_f.flush()
            print(f"    -> {status} ({n_ok}/{n_ns} namespaces ok, {elapsed:.1f}s)")

    print(f"\nDone. Results: {results_path}")


# ------------------------------------------------------------------ join

# forms whose BODY only executes when actually invoked (called with real
# arguments), as opposed to running once, unconditionally, the moment the
# namespace loads. Anonymous #(...) literals are function-like too, detected
# separately below since they have no head symbol of their own.
FUNCTION_LIKE_HEADS = {
    "defn", "defn-", "fn", "defmethod", "defmacro", "definline",
    "deftype", "defrecord", "extend-protocol", "extend-type",
}

_HEAD_TOKEN_RE = re.compile(r"[\s,]*([^\s()\[\]{}\"';,]*)")


def find_function_like_spans(source_text):
    """Scan Clojure/ClojureScript source and return every parenthesized
    form's (start_line, end_line) whose head symbol is in
    FUNCTION_LIKE_HEADS, or that is an anonymous #(...) literal - i.e. every
    span whose contents only execute when that form is invoked, not merely
    when the namespace loads.

    Deliberately not a full Clojure reader - just enough tokenizing to keep
    paren/bracket/brace depth correct: skips line comments, string literals
    (with \\" escapes), and character literals (\\X - only the one char
    right after the backslash is consumed; a multi-char named literal like
    \\newline leaves its trailing letters as an ignorable bare token, which
    never affects paren balance since named literals never contain parens).
    Known gap: doesn't special-case #_ discarded forms or reader-conditional
    branches - harmless for depth balance (the real parens inside them still
    balance correctly), at most a rare spurious extra span that doesn't
    change any actual classification. Validated against the 24 real
    "covered" occurrences from the earlier aggregate-coverage pilots -
    matched a manual, line-by-line read of each one's actual enclosing form
    for all 24.
    """
    spans = []
    stack = []  # [start_line, is_function_like]
    i, n = 0, len(source_text)
    line = 1
    prev_significant = ""

    while i < n:
        c = source_text[i]

        if c == "\n":
            line += 1
            i += 1
            continue
        if c == " " or c == "\t" or c == "\r":
            i += 1
            continue
        if c == ";":
            while i < n and source_text[i] != "\n":
                i += 1
            continue
        if c == '"':
            i += 1
            while i < n and source_text[i] != '"':
                if source_text[i] == "\\":
                    i += 1
                if i < n and source_text[i] == "\n":
                    line += 1
                i += 1
            i += 1
            prev_significant = '"'
            continue
        if c == "\\" and i + 1 < n:
            i += 2
            prev_significant = "\\"
            continue
        if c == "(":
            # peek-only lookahead for the head symbol - does not consume
            # input or advance `i`/`line`; the whitespace and head-symbol
            # characters themselves still get walked (and `line` bumped for
            # any newline among them) by the normal loop on later iterations
            m = _HEAD_TOKEN_RE.match(source_text, i + 1)
            head = m.group(1) if m else ""
            is_fn_like = prev_significant == "#" or head in FUNCTION_LIKE_HEADS
            stack.append([line, is_fn_like])
            i += 1
            prev_significant = c
            continue
        if c == ")":
            if stack:
                start_line, is_fn_like = stack.pop()
                if is_fn_like:
                    spans.append((start_line, line))
            i += 1
            prev_significant = c
            continue

        prev_significant = c
        i += 1

    return spans


def is_load_time_only(line, function_like_spans):
    """True if `line` falls outside every function-like span - i.e. it only
    executes once, when the namespace loads, not when something calls it."""
    return not any(start <= line <= end for start, end in function_like_spans)


def repo_dir_of(filepath, repos_root):
    try:
        rel = Path(filepath).relative_to(repos_root)
    except ValueError:
        return None
    return rel.parts[0]


def build_attribution_index(coverage_results_csv, repos_root):
    """repo -> {absolute_source_file: {line(int): [test_file, ...]}}, for
    repos with at least one successfully-attributed namespace AND whose
    attribution.json still exists on disk (target/ is untracked build
    output and can be wiped independently of coverage_results.csv's
    bookkeeping)."""
    cov_rows = pd.read_csv(coverage_results_csv)
    usable = cov_rows[cov_rows["status"] == "ok"]

    index = {}
    missing_on_disk = []
    for _, row in usable.iterrows():
        attribution_path = Path(str(row["attribution_path"]))
        if not attribution_path.is_file():
            missing_on_disk.append(row["repo"])
            continue
        raw = json.load(open(attribution_path))
        index[row["repo"]] = {
            f: {int(ln): tests for ln, tests in lines.items()}
            for f, lines in raw.get("attribution", {}).items()
        }

    if missing_on_disk:
        print(
            f"WARNING: {len(missing_on_disk)} repo(s) marked ok in {coverage_results_csv} "
            f"but their attribution.json is missing on disk now (target/ wiped by a repo "
            f"refresh?) - treated as unmeasured_repo: {', '.join(missing_on_disk)}"
        )
    return index


def classify_occurrence(occ, attribution_index, repos_root):
    """occ must already be a non-test occurrence - the join phase filters
    is_test=True rows out entirely before calling this, since coverage is
    meaningless for test code itself. Returns (coverage_status, covered,
    test_files: list)."""
    repo_dir = repo_dir_of(occ["filepath"], repos_root)
    if repo_dir is None or repo_dir not in attribution_index:
        return "unmeasured_repo", pd.NA, []

    file_attr = attribution_index[repo_dir].get(str(Path(occ["filepath"]).resolve()))
    start = occ.get("location_start_line")
    if file_attr is None or pd.isna(start):
        return "unmeasured_file", pd.NA, []

    start = int(start)
    end_raw = occ.get("location_end_line")
    end = int(end_raw) if pd.notna(end_raw) else start

    # a line with no key at all in file_attr means NO namespace's isolated
    # run ever produced a DA: entry for it - no evidence whatsoever, not
    # evidence of zero hits. See module docstring for why this has to be
    # preserved explicitly rather than trusted to fall out of the data.
    lines_present = [ln for ln in range(start, end + 1) if ln in file_attr]
    if not lines_present:
        return "unmeasured_file", pd.NA, []

    test_files = set()
    for ln in lines_present:
        test_files.update(file_attr[ln])

    if test_files:
        return "covered", True, sorted(test_files)
    return "uncovered", False, []


def load_time_only_for(filepath, start_line, spans_cache):
    """load_time_only, cached per file so a source file with many
    occurrences only gets tokenized once."""
    if pd.isna(start_line):
        return pd.NA
    if filepath not in spans_cache:
        try:
            spans_cache[filepath] = find_function_like_spans(
                Path(filepath).read_text(errors="replace")
            )
        except OSError:
            spans_cache[filepath] = None
    spans = spans_cache[filepath]
    if spans is None:
        return pd.NA
    return is_load_time_only(int(start_line), spans)


def check_csv_consistency(csv_path, df):
    check_df = pd.read_csv(csv_path)
    assert len(check_df) == len(df), (
        f"row count mismatch after CSV round-trip: {len(check_df)} != {len(df)}"
    )
    assert check_df["coverage_status"].tolist() == df["coverage_status"].tolist(), (
        "coverage_status values changed after CSV round-trip"
    )
    assert check_df["load_time_only"].tolist() == df["load_time_only"].tolist(), (
        "load_time_only values changed after CSV round-trip"
    )
    assert check_df["some_coverage"].tolist() == df["some_coverage"].tolist(), (
        "some_coverage values changed after CSV round-trip"
    )


def join_coverage(args):
    repos_root = Path(args.repos_root)
    full_df = pd.read_csv(args.current_state_test)

    # test occurrences are excluded entirely, not scored or kept - coverage
    # is meaningless for test code itself.
    n_test = int(full_df["is_test"].sum())
    df = full_df[~full_df["is_test"]].reset_index(drop=True)

    attribution_index = build_attribution_index(args.coverage_results, repos_root)

    statuses, covered, test_files_col, load_time_only = [], [], [], []
    spans_cache = {}
    for _, occ in df.iterrows():
        status, is_covered, test_files = classify_occurrence(occ, attribution_index, repos_root)
        statuses.append(status)
        covered.append(is_covered)
        test_files_col.append(LIST_FIELD_SEP.join(test_files))
        load_time_only.append(
            load_time_only_for(occ["filepath"], occ.get("location_start_line"), spans_cache)
        )

    df["coverage_status"] = statuses
    df["covered"] = covered
    df["test_files"] = test_files_col
    df["load_time_only"] = load_time_only
    # a plain, always-True/False summary of coverage_status - True only for
    # "covered" (at least one test namespace's isolated run reached this
    # span). False covers BOTH "uncovered" (real evidence, confirmed never
    # hit) AND "unmeasured_file"/"unmeasured_repo" (no evidence either way) -
    # collapsing those three into one False is a deliberate simplification
    # for a single yes/no column, not a claim they're equivalent. The
    # difference between "confirmed untested" and "couldn't measure" is
    # still there in coverage_status for anyone who needs it - this column
    # doesn't replace that data, just adds a simpler summary alongside it.
    df["some_coverage"] = df["coverage_status"] == "covered"
    df.to_csv(args.out, index=False)

    from collections import Counter
    counts = Counter(statuses)
    total = len(df)
    scored = counts["covered"] + counts["uncovered"]
    print(f"non-test occurrences: {total} (excluded {n_test} is_test occurrences)")
    for status in ("covered", "uncovered", "unmeasured_file", "unmeasured_repo"):
        print(f"  {status}: {counts[status]}")

    scored_mask = df["coverage_status"].isin(("covered", "uncovered"))
    lto_scored = df.loc[scored_mask, "load_time_only"]
    n_lto = int((lto_scored == True).sum())  # noqa: E712 (pandas bool column)
    if scored:
        print(
            f"\nof {scored} scored occurrences, {n_lto} ({n_lto/scored*100:.0f}%) are "
            f"load_time_only=True - 'covered' for these means the namespace loaded, "
            f"not that a test specifically exercises them (see module docstring)"
        )
    if scored:
        print(f"\ncoverage rate (covered / (covered + uncovered)): {counts['covered']/scored*100:.1f}%")
        called_mask = scored_mask & (df["load_time_only"] == False)  # noqa: E712
        called_scored = int(called_mask.sum())
        called_covered = int((called_mask & (df["covered"] == True)).sum())  # noqa: E712
        if called_scored:
            print(
                f"coverage rate excluding load_time_only rows (the more trustworthy "
                f"number - these actually had to be CALLED, not just loaded): "
                f"{called_covered}/{called_scored} = {called_covered/called_scored*100:.1f}%"
            )
    print(f"\nwritten: {args.out}")

    check_csv_consistency(args.out, df)
    print(f"consistency check passed: {total} rows round-trip through the CSV unchanged")


# ------------------------------------------------------------------- cli


def parse_args():
    ap = argparse.ArgumentParser(
        description="Verify whether ARIT detections are actually reached by some test file, "
        "using per-test-namespace Cloverage attribution."
    )
    sub = ap.add_subparsers(dest="phase", required=True)

    collect = sub.add_parser(
        "collect",
        help="Run lein cloverage once per test namespace for each verified-working repo "
        "(slow, resumable at the repo level).",
    )
    verified_source = collect.add_mutually_exclusive_group(required=True)
    verified_source.add_argument(
        "--verified-tsv",
        help="TSV: repo<TAB>project_clj_relative_path, no header (e.g. lein_test_runs/verified_141.tsv)",
    )
    verified_source.add_argument(
        "--test-check-csv",
        help="check-lein-test's test_check.csv directly - filtered to verified_ok rows and "
        "normalized (repo: owner/name -> owner__name; project_clj_path: absolute -> relative "
        "to --repos-root) internally, no separate derivation step needed",
    )
    collect.add_argument("--repos-root", default=os.path.expanduser("~/Documents/tmp/refactorings"))
    collect.add_argument("--out-dir", required=True)
    collect.add_argument(
        "--timeout", type=int, default=300,
        help="per-test-namespace timeout in seconds (not per-repo - a repo with many test "
        "namespaces runs cloverage that many times, each bounded by this)",
    )
    collect.add_argument("--limit", type=int, default=0)
    collect.set_defaults(func=collect_coverage)

    join = sub.add_parser(
        "join",
        help="Join current_state_test.csv against collected attribution data (fast, deterministic).",
    )
    join.add_argument("--current-state-test", required=True, help="path to current_state_test.csv")
    join.add_argument("--coverage-results", required=True, help="coverage_results.csv from the collect phase")
    join.add_argument("--repos-root", default=os.path.expanduser("~/Documents/tmp/refactorings"))
    join.add_argument("--out", required=True, help="path to write current_state_with_coverage.csv")
    join.set_defaults(func=join_coverage)

    return ap.parse_args()


def main():
    args = parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
