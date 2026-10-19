"""Rule-based risk floor. It can raise the model's label and never lower it.

A false alarm costs a moment of reading. A missed ``rm -rf`` costs data, so the
asymmetry is deliberate. This is a lexical check on the command string, not a
shell parser, and it never executes the command.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from bashagent.schema import RiskName, Suggestion

RANK: dict[RiskName, int] = {"safe": 0, "caution": 1, "destructive": 2}

_SUDO = re.compile(r"\b(sudo|doas|pkexec)\b")
_PIPE_SHELL = re.compile(
    r"\|\s*(?:sudo\s+)?(?:(?:ba)?sh|zsh|dash|ksh|fish|python3?|perl|ruby|node)\b"
)
_EVAL_REMOTE = re.compile(r"\beval\b[\s\S]{0,400}\b(?:curl|wget)\b")
_PROC_SUB_REMOTE = re.compile(r"<\(\s*(?:curl|wget)\b")
_SECRET_FILE = re.compile(r"(?:~/?\.ssh\b|\bid_rsa\b|\bid_ed25519\b|~/?\.aws/|~/?\.netrc\b)")
_EXFIL_SINK = re.compile(r"\|\s*(?:sudo\s+)?(?:curl|wget|nc|ncat)\b")
_FORK_BOMB = re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&")
_TRUNCATE = re.compile(r"(?<!>)>(?!>)(?!&)")
_MUTATING_WORD = re.compile(
    r"\b(?:rm|unlink|mv|cp|install|rsync|tee|ln|dd|mkfs|shred|wipefs|truncate|chmod|chown)\b"
)
_WILDCARD = re.compile(r"[*?]")
_DELETION = re.compile(r"\b(rm|unlink|shred)\b|\s-delete\b")
_SEGMENT = re.compile(r"&&|\|\||[|;]")
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_WRAPPERS = frozenset({"sudo", "doas", "pkexec", "command", "env"})

# Lexical patterns. The highest level wins; a later lower level does not
# pull the result down.
_PATTERNS: list[tuple[RiskName, re.Pattern[str], str]] = [
    ("destructive", re.compile(r"\brm\b"), "rm deletes files."),
    ("destructive", re.compile(r"\b(dd|mkfs|shred|wipefs)\b"), "Disk or wipe command."),
    ("destructive", re.compile(r"\btruncate\b"), "truncate shrinks or empties a file."),
    (
        "destructive",
        re.compile(r"\bfind\b[\s\S]*\s-delete\b"),
        "find -delete removes files.",
    ),
    (
        "destructive",
        re.compile(r"\bfind\b[\s\S]*-exec\s+rm\b"),
        "find -exec rm removes files.",
    ),
    (
        "destructive",
        re.compile(r"\bgit\s+push\b[^;&|]*--force(?:-with-lease)?\b"),
        "git push --force rewrites remote history.",
    ),
    (
        "destructive",
        re.compile(r"\bgit\s+push\b[^;&|]*(?:^|\s)-[A-Za-z]*f[A-Za-z]*\b"),
        "git push -f rewrites remote history.",
    ),
    (
        "destructive",
        re.compile(r"\bgit\s+checkout\b[^;&|]*--\s+\.(?:\s|$)"),
        "git checkout -- . discards local changes.",
    ),
    (
        "destructive",
        re.compile(r"\bgit\s+restore\b[^;&|]*\s\.(?:\s|$)"),
        "git restore . discards local changes.",
    ),
    (
        "destructive",
        re.compile(r"\bcrontab\b[^;&|]*(?:\s-r\b|\s--remove\b)"),
        "crontab -r removes every cron job.",
    ),
    (
        "destructive",
        re.compile(r"\bdocker\s+system\s+prune\b"),
        "docker system prune deletes unused data.",
    ),
    (
        "destructive",
        re.compile(r"\bdocker\s+rm\b[^;&|]*(?:--force\b|(?:^|\s)-[A-Za-z]*f[A-Za-z]*\b)"),
        "docker rm -f removes containers.",
    ),
    (
        "destructive",
        re.compile(r"\bpython3?\s+-c\b[\s\S]*\b(?:shutil\.rmtree|os\.remove)\b"),
        "python -c deletes files.",
    ),
    (
        "destructive",
        re.compile(r"\brsync\b[^;&|]*--delete\b"),
        "rsync --delete removes files at the destination.",
    ),
    (
        "destructive",
        re.compile(r"\bchmod\b[^;&|]*?(?:-R|--recursive)\b"),
        "Recursive chmod.",
    ),
    (
        "destructive",
        re.compile(r"\bchown\b[^;&|]*?(?:-R|--recursive)\b"),
        "Recursive chown.",
    ),
    (
        "destructive",
        re.compile(r"\bkill\b[^;&|]*?(?:-9\b|-KILL\b|-SIGKILL\b)"),
        "kill -9.",
    ),
    ("caution", re.compile(r"\bkill\b"), "Sends a signal to a process."),
    (
        "destructive",
        re.compile(r"\bgit\s+reset\b[^;&|]*--hard\b"),
        "git reset --hard discards changes.",
    ),
    (
        "destructive",
        re.compile(r"\bgit\s+clean\b[^;&|]*(?:-[\w]*f|--force)"),
        "git clean -f deletes untracked files.",
    ),
    (
        "caution",
        re.compile(r"\b(mkdir|rmdir|touch|cp|mv|install|ln|rsync|tee)\b"),
        "Writes or moves files locally.",
    ),
    ("caution", re.compile(r"\bchmod\b"), "Changes permissions."),
    ("caution", re.compile(r"\bchown\b"), "Changes ownership."),
    (
        "caution",
        re.compile(r"\btar\b[^;&|]*(?:--extract|\s-[^\s]*x)"),
        "Extracts an archive.",
    ),
    (
        "caution",
        re.compile(r"\bgit\s+(add|commit|mv|restore)\b"),
        "Changes the git index or work tree.",
    ),
    ("caution", re.compile(r"\bsed\b[^;&|]*\s-i\b"), "sed -i edits a file in place."),
    ("caution", re.compile(r">>"), "Appends to a file."),
    (
        "caution",
        re.compile(r"\bfind\b[\s\S]*-exec\b"),
        "find -exec runs a command on each match.",
    ),
]


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskName
    reason: str


def classify_command(command: str, *, home: Path | None = None) -> RiskAssessment:
    """Classify ``command`` from its text. ``home`` decides the path rule."""
    home_path = home if home is not None else Path.home()
    text = command.strip()
    level: RiskName = "safe"
    reasons: list[str] = []

    def consider(new_level: RiskName, reason: str) -> None:
        nonlocal level
        if RANK[new_level] > RANK[level]:
            level = new_level
            reasons.clear()
            reasons.append(reason)
        elif new_level == level and new_level != "safe" and reason not in reasons:
            reasons.append(reason)

    if _SUDO.search(text):
        consider("destructive", "Contains sudo or another privilege escalation.")
    if _PIPE_SHELL.search(text):
        consider("destructive", "Pipes into a shell or an interpreter.")
    if _EVAL_REMOTE.search(text) or _PROC_SUB_REMOTE.search(text):
        consider("destructive", "Runs code fetched from the network.")
    if _SECRET_FILE.search(text) and _EXFIL_SINK.search(text):
        consider("destructive", "Sends a secret file over the network.")
    if _FORK_BOMB.search(text):
        consider("destructive", "Fork bomb.")
    if _has_real_truncate(text):
        consider("destructive", "A single > truncates a file.")
    if _WILDCARD.search(text) and _DELETION.search(text):
        consider("destructive", "Combines a wildcard with deletion.")
    if _outside_home(text, home_path):
        if _mutates(text):
            consider("destructive", "Writes or deletes a path outside the home directory.")
        else:
            consider("caution", "Reads a path outside the home directory.")

    for pattern_level, pattern, reason in _PATTERNS:
        if pattern.search(text):
            consider(pattern_level, reason)

    if not reasons:
        reasons.append("Reads or lists only.")
    return RiskAssessment(level=level, reason=" ".join(reasons))


def apply_risk_net(suggestion: Suggestion, *, home: Path | None = None) -> Suggestion:
    """Return ``suggestion`` with the risk raised when the rules demand it.

    The model's own label is kept when it is already at least as high.
    """
    ruled = classify_command(suggestion.command, home=home)
    if RANK[ruled.level] <= RANK[suggestion.risk]:
        return suggestion
    reason = (
        f"{suggestion.risk_reason} Säkerhetsnätet höjde nivån från "
        f"{suggestion.risk} till {ruled.level}: {ruled.reason}"
    )
    return suggestion.model_copy(update={"risk": ruled.level, "risk_reason": reason})


def _has_real_truncate(text: str) -> bool:
    """True when a single ``>`` targets something other than ``/dev/null``.

    ``2>&1`` and ``>>`` are not truncating redirects. ``>/dev/null`` discards
    output and does not empty a user file.
    """
    for match in _TRUNCATE.finditer(text):
        rest = text[match.end() :].lstrip()
        if rest.startswith("/dev/null"):
            continue
        return True
    return False


def _mutates(text: str) -> bool:
    """True when the command writes, moves, or deletes, ignoring ``>/dev/null``."""
    return _MUTATING_WORD.search(text) is not None or _has_real_truncate(text)


def _outside_home(command: str, home: Path) -> bool:
    """True when an operand path is ``/`` or outside ``home``.

    The executable token is ignored. ``/usr/bin/find .`` names a binary, it
    does not operate on ``/usr``. ``shlex`` only splits the string.
    """
    home_text = str(home)
    prefix = home_text.rstrip("/") + "/"
    for path in _target_paths(command):
        if path != home_text and not path.startswith(prefix):
            return True
    return False


def _target_paths(command: str) -> list[str]:
    paths: list[str] = []
    for segment in _SEGMENT.split(command):
        try:
            tokens = shlex.split(segment, posix=True)
        except ValueError:
            continue
        for token in _operands(tokens):
            paths.extend(_paths_in_token(token))
    return paths


def _operands(tokens: list[str]) -> list[str]:
    index = 0
    while index < len(tokens) and (tokens[index] in _WRAPPERS or _ASSIGNMENT.match(tokens[index])):
        index += 1
    if index < len(tokens):
        index += 1
    return tokens[index:]


def _paths_in_token(token: str) -> list[str]:
    found: list[str] = []
    if token.startswith("/"):
        found.append(token)
    if token.startswith("="):
        token = token[1:]
    for part in token.split("="):
        if part.startswith("/") and part not in found:
            found.append(part)
    return found
