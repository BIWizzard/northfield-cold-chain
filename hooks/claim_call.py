"""Find a call to the claim tool in a hook event, for claim_guard.py.

This is plumbing: you don't need to read or edit this file for Lab 7.
It works out whether a Bash or PowerShell command runs carrier_claim_api.py,
blocks the roundabout ways of running it, and finds the payload file.
"""

import json
from pathlib import Path
import re
import shlex
import sys


CLAIM_TOOL = "carrier_claim_api.py"
CLAIM_NAME = "carrier_claim_api"
# Anything that lets one command line run more than one command.
CHAIN_MARKERS = (";", "&", "|", "`", "$(", "<(", ">(", "\n", "\r")
INTERPRETER = re.compile(r"(python[0-9.]*|pythonw|py)(\.exe)?")
# Interpreter flags that can't run other code (unlike -c or -m).
SAFE_FLAG = re.compile(r"-[uBEIsSO3]+|-3\.[0-9]+")
# Commands that only read files, so naming the claim tool with them is fine.
VIEWERS = {
    "cat", "head", "tail", "less", "more", "grep", "rg", "wc", "ls", "type", "gc",
    "get-content", "select-string", "sls", "dir", "get-childitem", "git",
}
# A path to the tool: no quoting, substitution, or shell syntax in it.
CLEAN_PATH = re.compile(r"[^;&|`()<>'\"$!#=\n\r]+")
# A file name or path a viewer may be given: no spaces, no shell syntax.
PLAIN_PATH = re.compile(r"[\w./:\\-]+")
# --payload, or any short form of it argparse accepts, anywhere in the text.
PAYLOAD_TEXT = re.compile(r"(?<![\w-])--p(a(y(l(o(a(d)?)?)?)?)?)?(?![\w-])")


class Blocked(Exception):
    """Raised with the reason Claude should see."""


def read_event():
    """Read the hook event from stdin as UTF-8 JSON."""
    return json.loads(sys.stdin.buffer.read().decode("utf-8"))


def basename(token):
    """The lowercased file name at the end of a path, either slash."""
    return token.replace("\\", "/").rsplit("/", 1)[-1].lower()


def flattened(text):
    """Lowercased copies of text with quotes, $, backticks, and carets removed:
    one with backslashes turned into slashes, one with backslashes dropped."""
    text = text.lower()
    for mark in "'\"$`^":
        text = text.replace(mark, "")
    return text.replace("\\", "/"), text.replace("\\", "")


def names_tool(text):
    """True if text names the claim tool, however it's quoted or escaped."""
    return any(CLAIM_NAME in copy for copy in flattened(text))


def is_payload_option(token):
    """True for --payload, --payload=..., and the short forms argparse accepts."""
    option = token.split("=", 1)[0]
    return len(option) >= 3 and "--payload".startswith(option)


def runs_tool(tokens, index):
    """True if the command is a direct call: an interpreter (and harmless flags),
    or nothing, then a plain path to the tool."""
    token = tokens[index]
    if basename(token) != CLAIM_TOOL or not CLEAN_PATH.fullmatch(token):
        return False
    before = tokens[:index]
    if before:
        return bool(INTERPRETER.fullmatch(basename(before[0]))) and all(
            SAFE_FLAG.fullmatch(flag) for flag in before[1:]
        )
    return any(is_payload_option(after) for after in tokens[index + 1:])


def claim_arguments(event):
    """Return the arguments after the claim tool, or None if the command doesn't run it."""
    tool_input = event.get("tool_input")
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not isinstance(command, str):
        return None
    looks_like_claim = names_tool(command) or any(
        PAYLOAD_TEXT.search(copy) for copy in flattened(command)
    )
    chained = any(marker in command for marker in CHAIN_MARKERS)
    text = command.replace("\\", "/") if event.get("tool_name") == "PowerShell" else command
    try:
        tokens = shlex.split(text, posix=True)
    except ValueError:
        if looks_like_claim:
            raise Blocked("Write the claim command with balanced quotes.")
        return None

    # The usual case: one plain call to the tool, which the checks then examine.
    named = [index for index, token in enumerate(tokens) if names_tool(token)]
    if len(named) == 1 and runs_tool(tokens, named[0]):
        if chained:
            raise Blocked("Run the claim tool on its own, not chained with other commands.")
        return tokens[named[0] + 1:]

    # Anything else that names the tool or passes a payload is only allowed
    # when it just reads files.
    if not looks_like_claim:
        return None
    viewing = (
        tokens
        and tokens[0].lower() in VIEWERS
        and not chained
        and all(PLAIN_PATH.fullmatch(tokens[index]) for index in named)
    )
    if viewing:
        return None
    raise Blocked("Run the claim tool directly: python tools/carrier_claim_api.py --payload <file>, on its own.")


def payload_value(arguments):
    """Return the one --payload value, or None if there isn't a usable one."""
    values = []
    for index, token in enumerate(arguments):
        if not is_payload_option(token):
            continue
        if "=" in token:
            values.append(token.split("=", 1)[1])
        else:
            values.append(arguments[index + 1] if index + 1 < len(arguments) else "")
    if len(values) > 1:
        raise Blocked("Give exactly one --payload option.")
    if not values or not values[0] or values[0].startswith("-"):
        return None
    return values[0]


def find_claim_call(event, project):
    """Look for a claim call in a hook event.

    Returns None when the event doesn't run the claim tool, ("block", reason)
    when it must be stopped before any checks, or ("check", payload_file) with
    the full path of the payload to check. The claim tool opens the payload from
    the folder the command runs in, so the path resolves from the event's cwd.
    """
    try:
        if not isinstance(event, dict):
            raise Blocked("Provide a JSON object as the hook event.")
        if event.get("tool_name") not in ("Bash", "PowerShell"):
            return None
        arguments = claim_arguments(event)
        if arguments is None:
            return None
        value = payload_value(arguments)
        if value is None:
            raise Blocked("Supply --payload <path> with a claim JSON file.")
    except Blocked as reason:
        return ("block", str(reason))
    cwd = event.get("cwd")
    working = Path(cwd) if isinstance(cwd, str) and cwd else project
    return ("check", working / Path(value.replace("\\", "/")))
