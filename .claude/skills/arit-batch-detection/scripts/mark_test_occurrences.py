#!/usr/bin/env python3
"""
Read current_state.json (ARIT smell-detection output) and, for every
occurrence, deterministically decide whether it sits in a test file - based
on the occurrence's filepath and, as a secondary check, ARIT's own
source_role field. Writes current_state_test.csv (via pandas): the same
records, each with an added "is_test" boolean and a "group" column giving
the smell category for that occurrence's rule_id, looked up from
references/smells_type.csv (columns: group, rule_id) alongside this script.
The nested "location" dict is flattened into location_start_line/
location_start_col/location_end_line/location_end_col columns; the list
fields "missing_evidence" and "tags" are joined with "; " - CSV has no
native nested-value representation, and this keeps every value
human-readable and diffable instead of Python repr noise (e.g.
"{'start_line': 5, ...}") landing in a cell. After writing, the script
reads the CSV back with pandas and checks it against the in-memory data -
same row count, same is_test and group values in the same order - so a run
either prints "consistency check passed" or fails loudly; it doesn't
silently trust round-tripping through a CSV.

A rule_id with no matching row in smells_type.csv gets group="Unknown"
rather than a crash or a silent NaN - the script prints a warning naming
every such rule_id so a gap in smells_type.csv is visible, not swallowed.
Checked directly against the current dataset: all 31 distinct rule_ids
present in current_state.json have a mapping in smells_type.csv (which
itself covers 34 rule_ids total, 3 unseen in this run), so "Unknown"
hasn't actually fired yet, but the fallback exists because the reference
csv is maintained separately from ARIT and can drift out of sync with new
rule_ids ARIT starts emitting.

Why filepath, not source_role alone: source_role classifies the ROLE OF THE
SPECIFIC CODE CONSTRUCT ARIT flagged (production / test / fixture / dev /
generated / build), not "which file is this in". The two disagree often - a
real check against this exact dataset found 175 occurrences inside an actual
test/ directory that ARIT still tagged source_role=production (e.g. a plain
helper function defined in a _test.clj file), and 1468 source_role=fixture
occurrences sitting in files like test-resources/clojure/core.clj that never
match a bare "test/" directory at all. Neither number means what "is this
file a test file" is asking. So the file's own path is the primary,
consistent-per-file signal; source_role is used only as a narrow safety net
for the rare case (checked directly: all such cases found were under an
integration-test/ style directory a path check already covers) where ARIT
calls something test code but the path heuristics below don't recognize it.

Path heuristics (all case-insensitive, matched against POSIX path segments):

1. Directory segment is an exact, standard Leiningen/Clojure test root:
   test, tests. Deliberately excludes spec/specs (see rule 3) - unlike
   "test", a bare "spec" directory is not reliably about testing in
   Clojure: clojure.spec/cljs.spec's own canonical layout is a directory
   literally named spec/specs (clojure/spec/alpha.clj, cljs/spec/alpha.cljs,
   .../fhir/spec/resource.clj for a domain-spec library, etc.). A check of
   every file in this dataset sitting under a spec/specs directory found 21
   of 64 were exactly this - production spec-implementation files with
   plain names (alpha.clj, impl.clj, protocols.clj, resource.clj) - so
   treating spec/specs as an unconditional directory match the way test/
   tests is produced real false positives (e.g. nasser__magic's
   stdlib/clojure/spec/alpha.clj, a vendored copy of clojure.spec.alpha).

2. Directory segment is test-related by common convention even though it
   isn't an exact match - integration-test, system-int-test, test-resources,
   testcases, e2e-tests, and similar. Matched as the word "test"/"tests"
   appearing at a segment boundary (start, end, or next to - or _), so it
   catches "test-resources" and "testcases" but not an unrelated word that
   merely contains "test" as a substring, like "latest" or "protest".

3. Filename (without extension) follows the standard *_test / *-test /
   *_spec / *-spec naming convention for an actual test or RSpec/speclj-
   style spec namespace - but only when no ancestor directory is a known
   non-test tooling location (script, scripts, bin, tools). Without that
   exclusion, files like script/test_server.clj (a dev/build script,
   confirmed via its own source_role=build in this dataset) would be
   misclassified. A bare "test.clj"/"spec.clj" filename never matches this
   rule on its own - real examples in this dataset: src/noir/util/test.clj
   is a production utility file that happens to be named exactly
   "test.clj" (source_role=production), and clojure/alpha/spec/test.clj
   (clojure.spec.alpha2's own instrumentation code) is similarly bare;
   requiring a separator plus more content avoids both false positives.
   The _spec/-spec suffix is trustworthy precisely because it's the
   complement to rule 1's gap: of the 64 spec/specs-directory files
   checked, all 43 that really were tests (speclj's own test suite,
   swarmiji, more-speech, ...) were named exactly this way
   (event_spec.clj, client_core_spec.clj, bech32_spec.clj, ...); none of
   the 21 production spec-implementation files were.

   Only the *_test / *-test / *_spec / *-spec SUFFIX form is matched - a
   test_* / test- PREFIX is deliberately not, even though it's a valid
   convention in other ecosystems (Python's test_foo.py). A random sample
   of this exact dataset found a real false positive from the prefix form:
   clojure-contrib's src/main/clojure/clojure/contrib/test_is.clj is
   clojure.contrib.test-is, a production library that *implements* a
   testing framework (source_role=production, sitting in a plain
   src/main/clojure/ tree with no test-ish directory) - "test" there names
   the library itself, not a thing under test. Every genuine prefix-style
   hit found in this dataset (test_utils.clj, test_clojure/*.clj,
   test-native/...) was already caught independently by the directory
   rules above, so the prefix branch contributed no true positives here,
   only that one false positive - not worth the risk.

The repo-clone-root segment (the "owner__repo" directory each repo is
checked out into, immediately under .../refactorings/) is excluded from
every directory check above - it names the *repository*, not a location
within it, so it's not evidence about where inside that repo a file sits.
Without this exclusion, a repo whose own name happens to contain "test"
sweeps every file it has into is_test=True regardless of actual location:
checked all 512 repo roots in this dataset, and found exactly two real
cases - jakemcc__test-refresh (the lein-test-refresh plugin's own repo)
and pjstadig__humane-test-output (the humane-test-output library's own
repo) - both wholly production code (e.g.
pjstadig__humane-test-output/src/pjstadig/humane_test_output.clj) that
was being marked is_test=True purely from the clone-root name.

Known, deliberately-unfixed gap: a directory segment naming a test-RUNNER
tool (e.g. polyfy__polylith's components/clojure-test-test-runner and
components/test-runner-orchestrator, both wholly production Polylith
components whose job is running/orchestrating tests) still matches the
fuzzy directory rule and gets marked is_test=True, same failure mode as
the test_is.clj and clojure.spec cases above but not resolved in the
script - any occurrences that fall in this bucket are corrected by hand
in the output instead, since a clean rule-level fix risks catching real
cases too (e.g. cljs-test-runner-out, a real generated-test-output
directory that also contains "test-runner" in its name).

Deterministic: pure regex/string matching over fixed input data, no
timestamps, randomness, or network calls - the same current_state.json
always produces the same current_state_test.json.
"""
import argparse
import json
import re
from pathlib import Path, PurePosixPath

import pandas as pd

DEFAULT_INPUT_PATH = "/home/victor/Documents/tmp/current_state.json"
DEFAULT_OUTPUT_PATH = "/home/victor/Documents/tmp/current_state_test.csv"
DEFAULT_SMELLS_TYPE_PATH = str(Path(__file__).resolve().parent.parent / "references" / "smells_type.csv")

UNKNOWN_GROUP = "Unknown"

# list-valued JSON fields have no native CSV representation - join with this
# instead of letting pandas fall back to Python repr ("['a', 'b']") in a cell
LIST_FIELDS = ("missing_evidence", "tags")
LIST_FIELD_SEP = "; "

TEST_DIR_EXACT = {"test", "tests"}

# "test"/"tests" at a segment-boundary: start, end, or beside - or _.
# Matches: test-resources, integration-test, system-int-test, testcases,
# test_projects, e2e-tests. Does not match: latest, protest, contest.
TEST_DIR_FUZZY_RE = re.compile(
    r"(^|[-_])tests?(cases?|data|fixtures?|resources?|suites?|projects?)?([-_]|$)",
    re.IGNORECASE,
)

# filename stem: foo_test, foo-test, foo_spec, foo-spec only - requires a
# separator plus real content, so bare "test"/"spec" never matches on its
# own. Deliberately excludes the test_foo/test-foo prefix form: it
# false-positives on production libraries named test_<noun> (e.g.
# clojure.contrib.test-is), and every genuine prefix hit in this dataset
# was already caught by a directory rule.
TEST_FILENAME_RE = re.compile(r"^.+[-_](test|spec)$", re.IGNORECASE)

NON_TEST_TOOLING_DIRS = {"script", "scripts", "bin", "tools"}

ARIT_TEST_ROLES = {"test"}

# the directory each repo is cloned into, one level above every repo root
REPOS_ROOT_DIR = "refactorings"


def is_test_occurrence(filepath, source_role):
    parts = PurePosixPath(filepath).parts
    dirs = parts[:-1]

    # exclude the repo-clone-root segment (names the repo, not a location
    # within it) - see module docstring for the jakemcc__test-refresh /
    # pjstadig__humane-test-output cases this was found from.
    repo_root_idx = parts.index(REPOS_ROOT_DIR) + 1 if REPOS_ROOT_DIR in parts else -1
    dirs = [d for i, d in enumerate(dirs) if i != repo_root_idx]
    dirs_lower = {d.lower() for d in dirs}

    for d in dirs:
        dl = d.lower()
        if dl in TEST_DIR_EXACT or TEST_DIR_FUZZY_RE.search(dl):
            return True

    if not (dirs_lower & NON_TEST_TOOLING_DIRS):
        stem = PurePosixPath(filepath).stem
        if TEST_FILENAME_RE.match(stem):
            return True

    if source_role in ARIT_TEST_ROLES:
        return True

    return False


def build_dataframe(occurrences, smells_type_path):
    df = pd.json_normalize(occurrences, sep="_")
    for col in LIST_FIELDS:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda v: LIST_FIELD_SEP.join(v) if isinstance(v, list) else v
            )

    smells_type = pd.read_csv(smells_type_path)
    df = df.merge(smells_type[["rule_id", "group"]], on="rule_id", how="left")

    unmapped = sorted(df.loc[df["group"].isna(), "rule_id"].unique())
    if unmapped:
        print(
            f"WARNING: {len(unmapped)} rule_id(s) have no group in {smells_type_path}, "
            f"defaulting to {UNKNOWN_GROUP!r}: {', '.join(unmapped)}"
        )
    df["group"] = df["group"].fillna(UNKNOWN_GROUP)

    return df


def check_csv_consistency(csv_path, df):
    """Read csv_path back and confirm it matches df row-for-row on is_test
    and group - fails loudly (AssertionError) rather than silently trusting
    the CSV round-trip."""
    check_df = pd.read_csv(csv_path)
    assert len(check_df) == len(df), (
        f"row count mismatch after CSV round-trip: {len(check_df)} != {len(df)}"
    )
    assert check_df["is_test"].tolist() == df["is_test"].tolist(), (
        "is_test values changed after CSV round-trip"
    )
    assert check_df["group"].tolist() == df["group"].tolist(), (
        "group values changed after CSV round-trip"
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Mark every ARIT occurrence with whether it sits in a test file, "
        "and tag it with its smell group."
    )
    parser.add_argument("--input", default=DEFAULT_INPUT_PATH, help="path to current_state.json")
    parser.add_argument(
        "--output", default=DEFAULT_OUTPUT_PATH, help="path to write current_state_test.csv"
    )
    parser.add_argument(
        "--smells-type",
        default=DEFAULT_SMELLS_TYPE_PATH,
        help="path to smells_type.csv (columns: group, rule_id)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    with open(args.input) as f:
        occurrences = json.load(f)

    for occ in occurrences:
        occ["is_test"] = is_test_occurrence(occ.get("filepath", ""), occ.get("source_role"))

    df = build_dataframe(occurrences, args.smells_type)
    df.to_csv(args.output, index=False)

    total = len(df)
    test_count = int(df["is_test"].sum())
    print(f"total occurrences: {total}")
    print(f"is_test=True:  {test_count} ({test_count / total * 100:.1f}%)")
    print(f"is_test=False: {total - test_count} ({(total - test_count) / total * 100:.1f}%)")
    print(f"written: {args.output}")

    check_csv_consistency(args.output, df)
    print(f"consistency check passed: {total} rows round-trip through the CSV unchanged")


if __name__ == "__main__":
    main()
