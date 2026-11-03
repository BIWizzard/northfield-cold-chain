# settings.json guide

`.claude/settings.json` holds this project's shared settings: what Claude can do without asking, and which hooks run. Keep this guide open in Labs 7 and 8.

Settings files are strict JSON. A `//` comment or a trailing comma is a syntax error, and Claude Code reports it at the next start. That's why the notes live here and the file itself stays bare.

Claude Code reloads the file when you save it, so there's no need to restart your session.

## What's in the file

| Key | What it does |
|---|---|
| `$schema` | Points your editor at the published schema, for autocomplete and inline checks. |
| `permissions.allow` | Rules for tool calls Claude can make without asking you. |
| `permissions.deny` | Rules for tool calls Claude can never make. |
| `permissions.ask` | Rules for tool calls that always need your approval, even when an allow rule also matches. |
| `hooks` | Commands Claude Code runs at fixed points, such as before or after a tool call. You wire two in Lab 7. |

When rules overlap, deny wins over ask, and ask wins over allow. Thursday covers this in more depth.

## Bash and PowerShell

On Windows, Claude Code can run a command through two tools: `Bash` (from Git for Windows) and `PowerShell`. Both are on by default, and Claude picks one per command. A hook matcher or permission rule that names only `Bash` never sees the commands that go through `PowerShell`, so the same command gets past it.

So every hook matcher and rule that targets a command covers both:

- Hook matchers: `Bash|PowerShell`
- Permission rules: one `Bash(...)` rule and one `PowerShell(...)` rule for each command

On a Mac, commands go through `Bash`. The `PowerShell` entries do nothing there, and they keep one file working on every laptop.

The hook scripts themselves run under Git Bash on Windows, which is why the preflight requires Git.

## Lab 7: wire the hooks

You complete two hooks in `hooks/`:

- **`claim_guard.py`** runs before every `Bash` or `PowerShell` call (PreToolUse). It lets through any command that doesn't run `carrier_claim_api.py`, so reading the file with a command like `cat` or `grep` is fine. Spotting a claim call is done for you in `hooks/claim_call.py`, which you don't need to open. That includes blocking one that's chained with other commands, gives more than one payload, or runs the tool in a roundabout way instead of `python tools/carrier_claim_api.py --payload <file>`. For a claim call, you make it block unless the payload holds up: the payload file exists and is valid JSON, its shipment ID matches exactly one row in `shipments.csv`, its logger file is the one on that row and exists, and its disposition is `hold` or `reject`. When it blocks, it says why in one line Claude can act on.
- **`audit_log.py`** runs after each tool call that completes (PostToolUse) or fails (PostToolUseFailure). It appends one line to `audit.jsonl` with the time, the event, the tool name, the tool use ID, and a short summary of what the tool was given. It never blocks and never fails the call.

A call the claim guard blocks never runs, so it never appears in `audit.jsonl`. The log records what happened; the guard decides what's allowed to happen.

Once both hooks pass the harness (next section), replace the contents of `.claude/settings.json` with this. If you've already added permission rules, keep them and replace only the `"hooks"` value.

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "permissions": {
    "allow": [],
    "deny": [],
    "ask": []
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|PowerShell",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PROJECT_DIR}/hooks/claim_guard.py\""
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PROJECT_DIR}/hooks/audit_log.py\""
          }
        ]
      }
    ],
    "PostToolUseFailure": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PROJECT_DIR}/hooks/audit_log.py\""
          }
        ]
      }
    ]
  }
}
```

A few things in there are easy to get wrong:

- **Each event takes a list.** `PreToolUse` holds a list of matcher groups, and each group holds its own list of `hooks`.
- **`matcher` is the tool name.** `Bash|PowerShell` matches either tool. `*` matches every tool, so the audit log also records file reads and writes.
- **The audit hook is wired twice**, once for calls that complete and once for calls that fail, so a command that errors still shows up in the log.
- **`${CLAUDE_PROJECT_DIR}`** is the folder you started Claude Code in. It keeps the path right whichever folder Claude is working in.
- **The `\"` quotes** are part of the command. They keep the path in one piece if your repo folder has a space in it.

To check the hooks loaded:

- **Terminal:** `/hooks` lists the hooks Claude Code loaded. All three should show up after you save.
- **VS Code or Desktop:** `/hooks` isn't available there. Ask Claude to run any command, such as `python --version`, and check that `audit.jsonl` gained a line.

## Test a hook before you try it live

The harness feeds saved tool events to a hook and checks what it does, with no Claude session:

```
python hooks/test_hook.py claim_guard
python hooks/test_hook.py audit_log
```

Each fixture prints `PASS` or `FAIL` with its name, and a `FAIL` shows what was expected, what happened, and anything the hook printed to stderr. The fixtures use a tiny made-up project with `TST-` shipment IDs, so they never touch the real data.

Before you complete a hook, expect most of its fixtures to fail. When every fixture passes, wire the hooks and try them live: ask Claude to file a claim without the evidence, and watch what happens. Then open `audit.jsonl` and find the calls that ran. The claim the guard blocked isn't there.

The harness runs each hook with whichever Python ran the harness. A live session runs the hook with `python`, as the hook command says. So if every fixture passes but a live claim gets through, check that `python --version` works in your terminal.

## Exit codes

A hook tells Claude Code what to do through its exit code.

| Exit code | What happens |
|---|---|
| `0` | No objection. The call goes on through the normal permission checks. Exit 0 doesn't approve anything. |
| `2` | Blocking. Before a tool call (PreToolUse), the call is stopped and the hook's stderr goes to Claude as the reason. After a tool call (PostToolUse or PostToolUseFailure), the tool has already run, so stderr is only shown to Claude. |
| Any other non-zero code | A non-blocking error. Claude Code shows a hook error notice, and **the call goes ahead**. |

Two consequences for Lab 7:

- A guard that crashes doesn't guard. An uncaught Python exception exits with code 1, so the call it should have stopped goes ahead. Block with exit code 2, on purpose.
- The block reason is what Claude reads. Write it so Claude can tell what's missing, not just that something is.

A PreToolUse block happens before permission rules are checked, so no allow rule can get a blocked call through.

## Lab 8: permission rules

Thursday's rules go in `permissions`. You'll write them in Lab 8.

A rule names a tool, with a pattern in parentheses. `*` stands for any text:

```
Bash(python tools/x.py *)
PowerShell(python tools/x.py *)
```

The space before `*` matters: `Bash(python tools/x.py *)` matches `python tools/x.py` with or without arguments after it, but not `python tools/x.py2`. Write each command rule twice, once for each tool.
