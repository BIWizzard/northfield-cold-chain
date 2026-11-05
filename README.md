# Northfield Cold Chain

Starter repo for Claude Code Academy, Week 1. You'll work as part of the Cold-Chain Exception Desk at Northfield Provisions, a fictional food distributor: temperature loggers ride along on every refrigerated shipment, and the desk decides what happens when a load runs warm.

Everything here is synthetic. No real companies, carriers, or shipments.

## Get started

1. **Clone this repo** somewhere local, such as `C:\dev\` or `~/projects/`. Not inside OneDrive, Dropbox, or iCloud Drive. No GitHub account needed:

   ```
   git clone https://github.com/BIWizzard/northfield-cold-chain.git
   cd northfield-cold-chain
   ```

2. **Run the preflight** from the repo root:
   - Windows: `powershell -ExecutionPolicy Bypass -File preflight\preflight.ps1`
   - macOS: `bash preflight/preflight.sh`

   Fix anything marked `FAIL` and run it again until every check passes.
3. **Pick an interface:** VS Code with the Claude Code extension, the `claude` CLI in a terminal, or the Code tab in Claude Desktop. Every lab works the same in all three.

## Run the Northfield app

Lab 1 has you click through the shipments in a small local web app before you ask Claude about them. From the repo root:

```
python app/serve.py
```

Then open http://127.0.0.1:8765 in your browser. If something else is using port 8765, pick another: `python app/serve.py --port 8766`. Press Ctrl+C in the terminal to stop it.

## What's here

| Path | What it holds |
|---|---|
| `data/raw/loggers/` | Temperature readings, one CSV per shipment, grouped by week. Never modified. |
| `data/reference/` | Shipments, carriers, and lanes |
| `data/sop/thresholds.json` | Temperature limits for each product category. The only place limits are defined. |
| `data/sop/cold-chain-sop.md` | The desk's SOP in prose. You use it in Module 2. |
| `app/` | The Northfield app: a local web view of the shipments and logger readings. Run it with `python app/serve.py`. |
| `templates/SKILL.md` | A starting template for the skills you write in Module 2. |
| `templates/AGENT.md` | A starting template for the subagent you write in Module 4. |
| `tools/carrier_claim_api.py` | A mock carrier claim API. It files nothing real and doesn't check evidence. |
| `claims/` | Claim payloads, one per shipment. The mock records what it filed in `claims/submitted.jsonl`. |
| `hooks/` | Two hook stubs you complete in Lab 7, and a harness that tests them without a Claude session. |
| `tests/` | Tests for the excursion check you build in Lab 3, plus tests for the mock claim tool, the hook harness, the app, and the settings and subagent files. |
| `CLAUDE.md` | Project instructions for Claude. You complete it in Lab 2. |
| `.claude/settings.json` | Project settings: permission rules and hooks. It starts empty, and you fill it in during Modules 3 and 4. |
| `.claude/settings.md` | A guide to `settings.json`, with the hook wiring you paste in during Lab 7 and notes on writing permission rules for Lab 8. |
| `.claude/agents/` | Where project subagents live. It starts empty, and you add one in Lab 9. |

More arrives as the week goes on. The academy site tells you what to open for each lab.

## Branches

- `main` is where you start. Commit your work as you go; it stays on your laptop.
- `m1-solution` to `m4-solution` hold a finished version of each module, for comparison or to catch up. Switch with `git checkout m1-solution`, and back with `git checkout main`.
