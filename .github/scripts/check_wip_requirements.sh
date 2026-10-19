#!/usr/bin/env bash
# Checks that every dictionary changed by the pull request without the _wip
# suffix has enough words for each letter/position, unless it's listed in
# .github/validated_dictionaries.txt.
#
# Usage: check_wip_requirements.sh <backend dictionaries scripts directory>
#
# Expects to run inside a main checkout where the PR head was fetched as `pr`.
# PR files are only read through git, never executed.
set -euo pipefail

scripts_dir="$1"
staged_dir="$RUNNER_TEMP/wip_staged"
validated_list="$RUNNER_TEMP/validated_dictionaries.txt"
failures=0

# The PR's list, so an admin can validate a dictionary in the same PR
# (only admins may edit it, see check-validated-dictionaries)
git show pr:.github/validated_dictionaries.txt > "$validated_list" 2>/dev/null || : > "$validated_list"

.github/scripts/stage_pr_dictionaries.sh pr "$staged_dir"

while IFS= read -r -d '' staged_file; do
  file="${staged_file#"$staged_dir/"}"

  if [[ "$file" == *_wip.txt ]]; then
    echo "🚧 $file is a work in progress."
    continue
  fi
  if grep -qxF "$file" "$validated_list"; then
    echo "✅ $file is validated."
    continue
  fi

  # The scripts write temporary files in the current directory
  count_dir=$(mktemp -d)
  cp "$staged_file" "$count_dir/"
  missing=$(cd "$count_dir" && python "$scripts_dir/check_incomplete_positions.py" "$count_dir" |
    grep "Final total sum of incomplete positions" | awk '{print $NF}')
  rm -rf "$count_dir"

  if [[ "${missing:-0}" -gt 0 ]]; then
    echo "❌ $file is missing $missing words: rename it to ${file%.txt}_wip.txt, or ask an admin to add it to .github/validated_dictionaries.txt."
    failures=$((failures + 1))
  else
    echo "✅ $file respects all letter/position requirements."
  fi
done < <(find "$staged_dir" -name '*.txt' -print0)

if [[ "$failures" -gt 0 ]]; then
  exit 1
fi
