"""The repo must not contain banned vocabulary or real vendor names (code, docs and data).

The list is base64-encoded so this file does not trip its own check.
"""
import base64
import re

from conftest import ROOT

ENCODED_SUBSTRINGS = [
    "cmVjb25jaWxpYXRpb24=", "Y2h1cm4=", "bG9nbw==", "cGFyZW50IGFjY291bnQ=", "ZW50ZXJwcmlzZQ==",
    "c2FsZXNmb3JjZQ==", "c2ZkYw==", "Y2hhcmdlYmVl", "cGxhbmhhdA==", "Y2VsaWdv", "c25vd2ZsYWtl",
    "aHVic3BvdA==", "Z2FpbnNpZ2h0", "enVvcmE=", "cmVjdXJseQ==", "bmV0c3VpdGU=", "c2hpZnRtb3Zl", "YXZyaW9z",
]
ENCODED_WHOLE_WORDS = ["Y2Fycg=="]
SEGMENT_SIZES = r"\bsegment[\s_-]?(s|m|l)\b"
SKIP_DIRS = {".git", ".venv", "target", "logs", "dbt_packages", "__pycache__", ".pytest_cache"}
TEXT_SUFFIXES = {".py", ".sql", ".yml", ".yaml", ".md", ".csv", ".txt", ".toml", ".cfg", ""}


def patterns():
    pats = [re.escape(base64.b64decode(e).decode()) for e in ENCODED_SUBSTRINGS]
    pats += [rf"\b{re.escape(base64.b64decode(e).decode())}\b" for e in ENCODED_WHOLE_WORDS]
    pats.append(SEGMENT_SIZES)
    return re.compile("|".join(pats), re.IGNORECASE)


def repo_files():
    for p in ROOT.rglob("*"):
        if p.is_file() and not SKIP_DIRS & set(p.relative_to(ROOT).parts) and p.suffix in TEXT_SUFFIXES:
            yield p


def test_no_banned_words():
    rx = patterns()
    hits = []
    scanned = 0
    for p in repo_files():
        scanned += 1
        for n, line in enumerate(p.read_text(errors="ignore").splitlines(), 1):
            m = rx.search(line)
            if m:
                hits.append(f"{p.relative_to(ROOT)}:{n}: {m.group(0)!r}")
    assert scanned > 20, "scanner found too few files"
    assert hits == [], "banned words found:\n" + "\n".join(hits[:50])
