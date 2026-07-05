#!/usr/bin/env python3
"""Fail if committed debug log JSON contains local/private patterns."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEBUG_LOG_DIR = ROOT / "debug_logs"
PATTERNS = [
    ("windows_user_backslash", re.compile(r"C:\\Users", re.IGNORECASE)),
    ("windows_user_slash", re.compile(r"C:/Users", re.IGNORECASE)),
    ("mac_user_path", re.compile(r"/Users/")),
    ("linux_home_path", re.compile(r"/home/")),
    ("onedrive", re.compile(r"OneDrive", re.IGNORECASE)),
    ("desktop", re.compile(r"\bDesktop\b", re.IGNORECASE)),
    ("documents", re.compile(r"\bDocuments\b", re.IGNORECASE)),
    ("downloads", re.compile(r"\bDownloads\b", re.IGNORECASE)),
    ("email", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
    ("unc_backslash", re.compile(r"\\\\[^\\\s]+\\[^\s\"'<>|]+")),
    ("unc_slash", re.compile(r"(?<!:)//(?!localhost(?:/|$))[^/\s]+/[^\s\"'<>|]+")),
]


def main():
    files = sorted(DEBUG_LOG_DIR.glob("*.json"))
    failures = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for label, pattern in PATTERNS:
            if pattern.search(text):
                failures.append((path.relative_to(ROOT).as_posix(), label))
    if failures:
        for rel_path, label in failures:
            print("privacy scan failed: {0}: {1}".format(rel_path, label), file=sys.stderr)
        return 1
    print("privacy scan passed: {0} debug log JSON file(s) checked".format(len(files)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
