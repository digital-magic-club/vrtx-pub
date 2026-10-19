#!/usr/bin/env bash
# Copies the dictionaries changed by the pull request into a directory, so the
# checks only look at what the PR touches instead of every dictionary.
#
# Usage: stage_pr_dictionaries.sh <base|pr> <output directory>
#   base: the files as they were where the PR branched off master
#   pr:   the files as they are in the PR
#
# Expects to run inside a master checkout where the PR head was fetched as `pr`.
# PR files are only read through git, never checked out or executed.
set -euo pipefail

side="$1"
output_dir="$2"

merge_base=$(git merge-base HEAD pr)
case "$side" in
  base) revision="$merge_base" ;;
  pr) revision=pr ;;
  *) echo "Unknown side: $side" >&2; exit 1 ;;
esac

mkdir -p "$output_dir"

git diff --name-only --diff-filter=d -z "$merge_base" pr -- 'dictionaries/*.txt' |
  while IFS= read -r -d '' file; do
    # Files added by the PR don't exist on the base side
    if git cat-file -e "$revision:$file" 2>/dev/null; then
      mkdir -p "$output_dir/$(dirname "$file")"
      git show "$revision:$file" > "$output_dir/$file"
      echo "Staged ($side): $file"
    fi
  done
