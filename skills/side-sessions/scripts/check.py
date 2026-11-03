#!/usr/bin/env python3
"""Read-only check of whether a side session's worktree is at risk of losing work.

Usage: python3 check.py <worktree-path> [branch] [base-branch]
JSON output: dirty files, unpushed commits, merge state against the base, PR state and safe_to_archive.
"""
import json
import os
import subprocess
import sys


def run(args, cwd, timeout=15):
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: check.py <worktree-path> [branch] [base-branch]")
    path = os.path.abspath(sys.argv[1])
    result = {"path": path, "exists": os.path.isdir(path)}
    if not result["exists"] or run(["git", "rev-parse", "--is-inside-work-tree"], path) != "true":
        result["note"] = "no worktree or not a git repo; loss risk could not be checked"
        result["safe_to_archive"] = None
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return

    branch = sys.argv[2] if len(sys.argv) > 2 else run(["git", "branch", "--show-current"], path)
    base = sys.argv[3] if len(sys.argv) > 3 else None
    if not base:
        ref = run(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], path)
        base = ref or "main"
    elif "/" not in base and run(["git", "rev-parse", "--verify", "-q", "origin/" + base], path):
        base = "origin/" + base

    dirty = run(["git", "status", "--porcelain"], path) or ""
    upstream = run(["git", "rev-parse", "--abbrev-ref", "@{u}"], path)
    unpushed = run(["git", "rev-list", "--count", "@{u}..HEAD"], path) if upstream else None
    not_in_base = run(["git", "rev-list", "--count", base + "..HEAD"], path)

    pr = None
    if branch:
        raw = run(["gh", "pr", "view", branch, "--json", "number,state,isDraft,mergedAt,url,title"], path)
        pr = json.loads(raw) if raw else None

    result.update({
        "branch": branch,
        "base": base,
        "dirty_files": len(dirty.splitlines()),
        "dirty_sample": dirty.splitlines()[:5],
        "upstream": upstream,
        "unpushed_commits": int(unpushed) if unpushed else 0,
        "commits_not_in_base": int(not_in_base) if not_in_base else 0,
        "pr": pr,
    })

    reasons = []
    if result["dirty_files"]:
        reasons.append("%d uncommitted files" % result["dirty_files"])
    if result["unpushed_commits"]:
        reasons.append("%d unpushed commits" % result["unpushed_commits"])
    if not upstream and result["commits_not_in_base"] and not (pr and pr.get("state") == "MERGED"):
        reasons.append("%d commits on a branch with no remote" % result["commits_not_in_base"])
    if pr and pr.get("state") == "OPEN":
        reasons.append("PR #%s is open" % pr.get("number"))
    result["blocking_reasons"] = reasons
    result["safe_to_archive"] = not reasons
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
