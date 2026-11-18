"""Graders for the eval harness.

`run_judge` is the one place a rubric is sent to `claude -p`. The harness's `judge`
grader and Lab 12's evals/judge.py both call it, so a rubric behaves the same way in
both. The rest of the graders are added alongside it.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TIMEOUT = 300
SETTINGS = ".claude/settings.json"
ANSWERS = {"yes": True, "no": False}


class JudgeError(RuntimeError):
    """The judge call failed, or its reply could not be read.

    A grader should count this as a failed grader, never as a pass.
    """


def parse_checks(text):
    """Read the judge's verdict from its reply. Returns {check: True or False}.

    The reply may have notes around the JSON, and the notes may contain braces of their
    own, so this reads the last JSON object that has a "checks" key. An empty verdict, or
    any answer that is not yes or no, is an error: it must not read as a pass.
    """
    decoder = json.JSONDecoder()
    checks = None
    for start, char in enumerate(text):
        if char != "{":
            continue
        try:
            data, _ = decoder.raw_decode(text, start)
        except ValueError:
            continue
        if isinstance(data, dict) and isinstance(data.get("checks"), dict):
            checks = data["checks"]
    if not checks:
        raise JudgeError("the judge's reply has no checks")
    verdict = {}
    for name, value in checks.items():
        answer = str(value).strip().lower()
        if answer not in ANSWERS:
            raise JudgeError(f"the judge's answer for {name!r} is {value!r}, not yes or no")
        verdict[name] = ANSWERS[answer]
    return verdict


def claude_command():
    """`claude`, unless EVALS_CLAUDE names another command (the tests point it at a stub)."""
    return os.environ.get("EVALS_CLAUDE") or shutil.which("claude") or "claude"


def run_judge(rubric_path, text, model=None, timeout=DEFAULT_TIMEOUT):
    """Send the rubric and `text` to `claude -p` and return each check as True or False.

    The call is made the way every case is run: `-p`, `--output-format json`,
    `--settings .claude/settings.json`, and `--model` when one is given. Raises
    JudgeError if the call times out, claude cannot run, or the reply is unreadable.
    """
    rubric = Path(rubric_path).read_text(encoding="utf-8")
    args = [claude_command(), "-p", f"{rubric}\n\n{text}\n", "--output-format", "json", "--settings", SETTINGS]
    if model:
        args += ["--model", model]
    try:
        run = subprocess.run(
            args, capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=ROOT, timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise JudgeError(f"the judge call timed out after {timeout} seconds") from error
    except OSError as error:
        raise JudgeError(f"could not run claude: {error}") from error
    try:
        output = json.loads(run.stdout)
    except ValueError as error:
        detail = (run.stderr or run.stdout or "").strip()[:200]
        raise JudgeError(f"claude printed no JSON result (exit {run.returncode}): {detail}") from error
    if not isinstance(output, dict):
        raise JudgeError("claude's JSON result is not an object")
    if output.get("is_error"):
        raise JudgeError(f"claude reported an error: {str(output.get('result', ''))[:200]}")
    return parse_checks(str(output.get("result", "")))
