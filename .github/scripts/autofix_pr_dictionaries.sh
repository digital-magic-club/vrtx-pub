#!/usr/bin/env bash
# Fixes the simple issues in the dictionaries changed by the pull request and
# commits the result on top of the PR branch:
#   - removes duplicated lines and sorts alphabetically (fix_dictionaries.py)
#   - adds the _wip suffix to dictionaries missing letter/position words,
#     unless they are listed in .github/validated_dictionaries.txt
#
# Usage: autofix_pr_dictionaries.sh <backend dictionaries scripts directory> <PR working tree>
#
# Expects to run inside a main checkout where the PR head was fetched as `pr`.
# PR files are only edited as data, never executed.
set -euo pipefail

scripts_dir="$1"
pr_tree="$2"
validated_list="$PWD/.github/validated_dictionaries.txt"
staged_dir="$RUNNER_TEMP/autofix_staged"

git worktree add --detach "$pr_tree" pr

.github/scripts/stage_pr_dictionaries.sh pr "$staged_dir"
python "$scripts_dir/fix_dictionaries.py" "$staged_dir"

find "$staged_dir" -name '*.txt' -print0 |
  while IFS= read -r -d '' staged_file; do
    file="${staged_file#"$staged_dir/"}"
    cp "$staged_file" "$pr_tree/$file"

    if [[ "$file" == *_wip.txt ]] || grep -qxF "$file" "$validated_list"; then
      continue
    fi

    # The scripts write temporary files in the current directory
    count_dir=$(mktemp -d)
    cp "$staged_file" "$count_dir/"
    missing=$(cd "$count_dir" && python "$scripts_dir/check_incomplete_positions.py" "$count_dir" |
      grep "Final total sum of incomplete positions" | awk '{print $NF}')
    rm -rf "$count_dir"

    if [[ "${missing:-0}" -gt 0 ]]; then
      echo "🚧 $file is missing $missing words: renaming it to _wip"
      git -C "$pr_tree" mv "$file" "${file%.txt}_wip.txt"
    fi
  done

git -C "$pr_tree" add -A dictionaries
if git -C "$pr_tree" diff --cached --quiet; then
  echo "✅ Nothing to fix!"
  exit 0
fi

git -C "$pr_tree" -c user.name="github-actions[bot]" -c user.email="github-actions[bot]@users.noreply.github.com" \
  commit -q -m "Fix dictionaries automatically" -m "Sort alphabetically, remove duplicated lines and add the _wip suffix to incomplete dictionaries."
git -C "$pr_tree" show --stat --format='🛠️ %s' HEAD
