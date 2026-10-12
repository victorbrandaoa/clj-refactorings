#!/usr/bin/env bash
# Deterministically list every project dir under $1 (default: current dir)
# that uses Leiningen as its build tool: a project.clj containing
# (defproject ...) exists at the repo root OR in a nested submodule/module
# (depth <= 4, skipping .git/target/node_modules/resources/test-resources).
#
# Multi-module repos (e.g. a repo with mulog-core/project.clj and
# mulog-kafka/project.clj) emit one line per module, keyed as
# "<repo>/<module-dir>" so each hit stays uniquely addressable; a
# project.clj at the repo root is keyed as plain "<repo>".
set -uo pipefail

root="${1:-.}"
cd "$root"

for d in */; do
  name="${d%/}"
  hits=$(find "$d" -maxdepth 4 \
    -type d \( -name .git -o -name target -o -name node_modules -o -name resources -o -name test-resources \) -prune -o \
    -type f -name project.clj -print 2>/dev/null \
    | xargs -r grep -l '(defproject' 2>/dev/null)
  if [ -n "$hits" ]; then
    while IFS= read -r hit; do
      mod_rel="${hit#"$d"}"
      mod_dir="${mod_rel%/project.clj}"
      if [ "$mod_dir" = "project.clj" ]; then
        key="$name"
      else
        key="$name/$mod_dir"
      fi
      printf '%s\t%s\n' "$key" "$hit"
    done <<< "$hits"
  fi
done
