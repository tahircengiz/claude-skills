#!/usr/bin/env python3
"""Collects raw project status data as JSON (read-only).

Usage: python3 collect.py [project-root]   (default: current directory)
Prints to stdout: git, the status file (STATUS.md / ROADMAP.md / TODO.md), delix STATE.json, open and merged PRs.
A missing source becomes null; the script writes no files.
"""
import datetime as dt
import json
import os
import subprocess
import sys

STATUS_CANDIDATES = ["STATUS.md", "docs/STATUS.md", "ROADMAP.md", "TODO.md", "docs/ROADMAP.md"]
TEXT_LIMIT = 24000


def run(args, cwd, timeout=15):
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def git(cwd, *args):
    return run(["git", *args], cwd)


def git_info(root):
    if git(root, "rev-parse", "--is-inside-work-tree") != "true":
        return None
    default = git(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    info = {
        "branch": git(root, "branch", "--show-current"),
        "default_branch": default.split("/", 1)[-1] if default else None,
        "remote": git(root, "remote", "get-url", "origin"),
        "dirty_files": len((git(root, "status", "--porcelain") or "").splitlines()),
        "recent_commits": [],
        "daily_commits": {},
        "worktrees": [],
    }
    log = git(root, "log", "-30", "--date=short", "--pretty=format:%h\x1f%ad\x1f%an\x1f%s")
    for line in (log or "").splitlines():
        h, date, author, subject = (line.split("\x1f") + ["", "", "", ""])[:4]
        info["recent_commits"].append({"hash": h, "date": date, "author": author, "subject": subject})

    today = dt.date.today()
    days = [(today - dt.timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
    counts = dict.fromkeys(days, 0)
    dates = git(root, "log", "--all", "--since=14 days ago", "--date=short", "--pretty=format:%ad")
    for d in (dates or "").splitlines():
        if d in counts:
            counts[d] += 1
    info["daily_commits"] = counts

    wt = git(root, "worktree", "list", "--porcelain") or ""
    entry = {}
    for line in wt.splitlines() + [""]:
        if not line:
            if entry:
                info["worktrees"].append(entry)
            entry = {}
        elif line.startswith("worktree "):
            entry["path"] = line[9:]
        elif line.startswith("branch "):
            entry["branch"] = line[7:].replace("refs/heads/", "")
    return info


def status_file(root):
    for candidate in STATUS_CANDIDATES:
        path = os.path.join(root, candidate)
        if os.path.isfile(path):
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
            return {
                "path": candidate,
                "modified": dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M"),
                "truncated": len(text) > TEXT_LIMIT,
                "text": text[:TEXT_LIMIT],
            }
    return None


def delix_state(root):
    path = os.path.join(root, "docs", "delix", "STATE.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        return {"error": str(e)}


def pr_info(root, remote):
    if not remote or "github.com" not in remote:
        return None
    fields = "number,title,headRefName,isDraft,updatedAt,url"
    open_prs = run(["gh", "pr", "list", "--state", "open", "--limit", "30", "--json", fields], root)
    since = (dt.date.today() - dt.timedelta(days=30)).isoformat()
    merged = run(["gh", "pr", "list", "--state", "merged", "--limit", "30",
                  "--search", "merged:>=" + since, "--json", "number,title,mergedAt,url"], root)
    if open_prs is None and merged is None:
        return {"error": "gh failed (not installed, not signed in, or no network)"}
    return {"open": json.loads(open_prs or "[]"), "merged_last_30_days": json.loads(merged or "[]")}


def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.getcwd())
    top = git(root, "rev-parse", "--show-toplevel")
    if top:
        root = top
    g = git_info(root)
    data = {
        "root": root,
        "name": os.path.basename(root),
        "collected": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "git": g,
        "status_file": status_file(root),
        "delix": delix_state(root),
        "pr": pr_info(root, g["remote"] if g else None),
    }
    json.dump(data, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
