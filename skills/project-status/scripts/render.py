#!/usr/bin/env python3
"""Turns status data JSON (schema: SKILL.md) into Artifact-ready HTML.

Usage: python3 render.py <data.json> <output.html>
Shared by the project-status and side-sessions skills.
"""
import html
import json
import os
import sys

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "page.html")
STATUSES = {"done", "partial", "blocked", "waiting", "attention", "open"}


def validate(v):
    errors = []
    if v.get("kind") not in ("project", "side-sessions"):
        errors.append("kind must be 'project' or 'side-sessions'")
    if not v.get("title"):
        errors.append("title is empty")
    if v.get("status") and v["status"] not in STATUSES:
        errors.append("invalid status: %s" % v["status"])
    for s in v.get("sections", []):
        if s.get("type") and s["type"] not in STATUSES:
            errors.append("invalid section type: %s" % s["type"])
        for i in s.get("items", []):
            if i.get("status") and i["status"] not in STATUSES:
                errors.append("invalid item status: %s (%s)" % (i["status"], i.get("title")))
    p = v.get("progress")
    if p is not None and not isinstance(p.get("percent"), (int, float)):
        errors.append("progress.percent must be a number")
    return errors


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: render.py <data.json> <output.html>")
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
    errors = validate(data)
    if errors:
        sys.exit("data error:\n- " + "\n- ".join(errors))
    suffix = "Side Sessions" if data["kind"] == "side-sessions" else "Status"
    title = "%s %s" % (data["title"], suffix)
    with open(TEMPLATE, encoding="utf-8") as f:
        template = f.read()
    embedded = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out = template.replace("__TITLE__", html.escape(title), 1).replace("/*__DATA__*/", embedded, 1)
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(out)
    print("%s (%d bytes) · title: %s" % (sys.argv[2], len(out.encode()), title))


if __name__ == "__main__":
    main()
