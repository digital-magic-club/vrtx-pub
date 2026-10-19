"""Builds the automatic PR comment: checks results and, for every dictionary
changed by the pull request, the missing letter/position couples before
(on main) and after merging.

Usage: python pr_report.py <backend dictionaries scripts directory>
  NEEDS: the workflow `needs` context as JSON, for the checks results

Expects to run inside a main checkout where the PR head was fetched as `pr`.
PR files are only read through git, never executed. Prints Markdown.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

MARKER = "<!-- vrtx-pr-report -->"
VALIDATE_MARKER = "<!-- validate:{path} -->"
SAFE_PATH = re.compile(r"dictionaries/[^/\s<>`]+/[^/\s<>`]+\.txt")

CHECKS = {
    "autofix": "Fix simple dictionary issues",
    "check-validated-dictionaries": "Validated dictionaries list is edited by an admin",
    "check-wip-requirements": "Dictionaries without _wip respect the requirements",
    "check-incomplete-positions": "Incomplete positions don't increase",
    "check-alphabetic-sorting": "Alphabetic sorting",
    "check-duplications": "No duplicated lines",
}

RESULT_ICONS = {"success": "✅", "failure": "❌", "skipped": "⏭️", "cancelled": "🚫"}

def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True).stdout

def file_at(revision, path):
    """Returns the file content at a revision, or None if it doesn't exist there."""
    result = subprocess.run(["git", "show", f"{revision}:{path}"], capture_output=True)
    return result.stdout if result.returncode == 0 else None

def changed_dictionaries():
    """Lists (path on main or None, path in the PR) for the dictionaries changed by the PR."""
    merge_base = git("merge-base", "HEAD", "pr").decode().strip()
    fields = git("diff", "--name-status", "-z", "-M", merge_base, "pr", "--", "dictionaries/*.txt").decode().split("\0")
    changes = []
    i = 0
    while i < len(fields) - 1:
        status = fields[i]
        if status.startswith("R"):
            changes.append((fields[i + 1], fields[i + 2]))
            i += 3
        else:
            if status != "D":
                changes.append((fields[i + 1], fields[i + 1]))
            i += 2
    # Files the PR added don't exist on main
    return [(old if file_at("HEAD", old) is not None else None, new) for old, new in changes]

def scan(scripts_dir, file_name, content):
    """Returns (missing letter/position couples, missing words) using the backend scripts."""
    with tempfile.TemporaryDirectory() as work_dir:
        txt_path = os.path.join(work_dir, file_name)
        with open(txt_path, "wb") as file:
            file.write(content)
        # The scripts write the JSON file in the current directory
        subprocess.run([sys.executable, os.path.join(scripts_dir, "parse_txt_into_json.py"), txt_path],
                       cwd=work_dir, check=True, capture_output=True)
        json_path = os.path.join(work_dir, os.path.splitext(file_name)[0] + ".json")
        output = subprocess.run([sys.executable, os.path.join(scripts_dir, "scan.py"), json_path],
                                cwd=work_dir, check=True, capture_output=True, text=True).stdout

    incomplete_section = output.split("Incomplete positions", 1)[1] if "Incomplete positions" in output else ""
    missing_couples = re.findall(r"\*\*Letter:\*\* `(.+?)`, \*\*Position:\*\* `(\d+)`", incomplete_section)
    missing_words = int(re.search(r"Total missing words: `(\d+)`", output).group(1))
    return missing_couples, missing_words

def dictionary_status(path, validated):
    """Where the dictionary stands: work in progress, or in production (validated or not)."""
    if path is None:
        return "—"
    if path.endswith("_wip.txt"):
        return "🚧 WIP"
    if path in validated:
        return "🚀 Production (validated)"
    return "🚀 Production (⚠️ not validated)"

def evolution(before, after):
    if before is None:
        return f"— → **{after}**"
    icon = "🟢" if after < before else "🔴" if after > before else "⚪️"
    return f"{before} → **{after}** {icon}"

def celebration(going_live):
    """A party for the dictionaries going live in production once merged."""
    plural = len(going_live) > 1
    lines = [
        f"## 🎉🚀 {'NEW DICTIONARIES' if plural else 'A NEW DICTIONARY'} GOING LIVE! 🚀🎉",
        "",
        f"> 🥳 Clear the stage and drop the confetti 🎊 Once merged, "
        f"{'these dictionaries hit production and land' if plural else 'this dictionary hits production and lands'} "
        "right in the hands of VRTX performers! 🪄✨",
        "",
    ]
    for path, is_new in going_live:
        name = f"`{path.removeprefix('dictionaries/')}`"
        if is_new:
            lines.append(f"- 🔥 {name}: brand new and already production-ready 💪")
        else:
            lines.append(f"- 🔥 {name}: straight out of the WIP workshop 🛠️ and into the big leagues 🏆")
    author = os.environ.get("PR_AUTHOR")
    if author:
        lines += ["", f"Huge thanks @{author} 🙌 You absolutely crushed it! 💯"]
    return lines + [""]

def main(scripts_dir):
    needs = json.loads(os.environ.get("NEEDS", "{}"))
    # Main's list only: the PR's own copy isn't trusted
    main_list = file_at("HEAD", ".github/validated_dictionaries.txt") or b""
    validated = validated_on_main = set(main_list.decode().splitlines())

    lines = [
        MARKER,
        "🤖 **This is an automatic message** from the pull request validations. It is updated on every run.",
        "",
        "### Checks",
        "",
        "| Check | Result |",
        "| --- | --- |",
    ]
    for job, name in CHECKS.items():
        result = needs.get(job, {}).get("result", "skipped")
        lines.append(f"| {name} | {RESULT_ICONS.get(result, '❔')} {result} |")

    changes = changed_dictionaries()
    lines += ["", "### Dictionaries changed by this PR", ""]

    if not changes:
        lines.append("This PR doesn't change any dictionary.")
        return "\n".join(lines)

    lines += [
        "Missing letter/position couples (at least 2 words are needed for each) and missing words, on `main` → once merged:",
        "",
        "| Dictionary | On `main` → once merged | Missing couples | Missing words |",
        "| --- | --- | --- | --- |",
    ]
    details = []
    to_production = []
    staying_wip = []
    going_live = []
    to_validate = []
    for old_path, new_path in changes:
        after_couples, after_words = scan(scripts_dir, os.path.basename(new_path), file_at("pr", new_path))
        before_couples, before_words = (None, None)
        if old_path is not None:
            couples, before_words = scan(scripts_dir, os.path.basename(old_path), file_at("HEAD", old_path))
            before_couples = len(couples)

        name = f"`{new_path.removeprefix('dictionaries/')}`"
        if old_path is None:
            name += " (new)"
        elif old_path != new_path:
            name += f" (renamed from `{old_path.removeprefix('dictionaries/')}`)"

        if new_path.endswith("_wip.txt"):
            staying_wip.append(name)
        else:
            to_production.append(name)
            if old_path is None or old_path.endswith("_wip.txt"):
                going_live.append((new_path, old_path is None))

        production_path = new_path.removesuffix("_wip.txt") + ".txt" if new_path.endswith("_wip.txt") else new_path
        # File names come from the PR: no checkbox for ones that could fake another line or marker
        if production_path not in validated and SAFE_PATH.fullmatch(production_path):
            to_validate.append(production_path)

        status = f"{dictionary_status(old_path, validated_on_main)} → **{dictionary_status(new_path, validated)}**"
        lines.append(f"| {name} | {status} | "
                     f"{evolution(before_couples, len(after_couples))} | {evolution(before_words, after_words)} |")

        if after_couples:
            missing = ", ".join(f"`{letter}` at {position}" for letter, position in after_couples)
            details.append(f"- `{new_path.removeprefix('dictionaries/')}`: {missing}")

    summary = ["", "**Once merged:**", ""]
    if to_production:
        summary.append(f"- 🚀 Sent to production: {', '.join(to_production)}")
    if staying_wip:
        summary.append(f"- 🚧 Still a work in progress (not in production): {', '.join(staying_wip)}")
    lines += summary

    if details:
        lines += ["", "<details>", "<summary>Still missing once merged</summary>", "", *details, "", "</details>"]

    if to_validate:
        lines += ["", "### 🛡️ Admin validation", "",
                  "Repo admins can tick a dictionary to add it to `.github/validated_dictionaries.txt`: "
                  "it then goes to production once merged, whatever its missing couples.", ""]
        for path in to_validate:
            # The marker tells the validation workflow which dictionary the box is about
            lines.append(f"- [ ] Validate `{path.removeprefix('dictionaries/')}` {VALIDATE_MARKER.format(path=path)}")

    if going_live:
        # Right after the automatic message line, so it's the first thing people see
        lines[3:3] = celebration(going_live)

    return "\n".join(lines)

if __name__ == "__main__":
    print(main(sys.argv[1]))
