# settings.json guide

`.claude/settings.json` holds this project's shared settings: what Claude can do without asking, and which hooks run. Keep this guide open in Labs 7 and 8.

Settings files are strict JSON, so a `//` comment or trailing comma is a syntax error. That's why the notes live here and the file stays bare. Claude Code reloads the file on save, so you don't need to restart your session.

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

- **`claim_guard.py`** runs before every `Bash` or `PowerShell` call (PreToolUse). `hooks/claim_call.py` (already done, no need to open it) spots `carrier_claim_api.py` calls and blocks chained, multi-payload, or roundabout ones; any other command, like `cat` or `grep` on the file, passes. For a real claim call, you make it block unless the payload checks out (the four TODOs in the file). The block says why in one line Claude can act on.
- **`audit_log.py`** runs after each tool call that completes (PostToolUse) or fails (PostToolUseFailure). It appends one line to `audit.jsonl` with the time, the event, the tool name, the tool use ID, and a short summary of what the tool was given. It never blocks and never fails the call.

A call the claim guard blocks never runs, so it never appears in `audit.jsonl`. The log records what happened; the guard decides what's allowed to happen.

Once both hooks pass the harness (next section), merge this `"hooks"` value into your existing `.claude/settings.json`. Keep `$schema` and any permission rules you've added; replace only `"hooks"`.

```json
{
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

Thursday's rules go in `permissions`. You'll write them in Lab 8. The examples here use made-up scripts and paths; working out the real rules is the lab.

### Command rules

A rule names a tool, with a pattern in parentheses. `*` stands for any text:

```
Bash(python tools/x.py *)
PowerShell(python tools/x.py *)
```

The space before `*` matters: `Bash(python tools/x.py *)` matches `python tools/x.py` with or without arguments after it, but not `python tools/x.py2`. Write each command rule twice, once for each tool.

Give each script its own rule. A rule broad enough to cover two scripts, such as `Bash(python *)`, also covers every other Python command, including one Claude writes itself. Claude Code checks each part of a chained command separately, so a rule never approves another command chained to the one it matches.

### File rules

`Read(...)` and `Edit(...)` rules take a path instead of a command:

```
Read(/notes/private.txt)
Edit(/archive/**)
```

- **`**`** means everything under a folder, at any depth.
- **A leading `/`** means the project folder, the one you started Claude Code in. Without it, the path is relative to wherever Claude is working, which moves when it runs `cd`. A single `/` isn't the drive root; that's `//`.
- **`Edit(...)` covers Write too.** There's no `Write(...)` path rule: Claude Code accepts one, but it never matches anything.
- **`Read(...)` covers Grep and Glob too**, on the same path.
- **No `PowerShell` twin.** A file rule matches the path whichever tool or shell touches it.

### Order

Claude Code checks deny rules first, then ask, then allow, and the first match wins, however specific the other rule is. With `Bash(python tools/x.py *)` in deny, `Bash(python tools/x.py --dry-run)` in allow never gets a call through.

### Hooks and rules

Hooks run first. A call a PreToolUse hook blocks never reaches the rules, so no rule can let it through. A call the hook lets through goes on to the rules as usual. Exit 0 approves nothing, so a hook can't skip an ask prompt.

### Skills and rules

A skill's `allowed-tools` pre-approves its tools only for the turn that ran the skill. A deny or ask rule still wins: if an ask rule matches a command the skill lists, you're still asked.

### Settings layers

Claude Code reads settings from four layers:

| Layer | File | Who it's for |
|---|---|---|
| Managed | Set by your organization's IT | Everyone on the laptop |
| User | `~/.claude/settings.json` | You, in every project |
| Project | `.claude/settings.json` | Everyone who clones the repo. This is the shared one. |
| Local | `.claude/settings.local.json` | You, in this project only |

Lab 8's rules go in the project file, so they travel with the repo. A deny rule in any layer wins: no other layer can allow what one denies.

### Checking

- **Terminal:** `/permissions` lists the rules Claude Code loaded.
- **Desktop:** `/permissions` works differently in the Code tab. Read `.claude/settings.json` itself, or run `/permissions` from a terminal.
