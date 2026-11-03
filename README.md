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

## What's here

| Path | What it holds |
|---|---|
| `data/raw/loggers/` | Temperature readings, one CSV per shipment, grouped by week. Never modified. |
| `data/reference/` | Shipments, carriers, and lanes |
| `data/sop/thresholds.json` | Temperature limits for each product category. The only place limits are defined. |
| `tests/` | Tests for the excursion check you build in Lab 3 |
| `CLAUDE.md` | Project instructions for Claude. You complete it in Lab 2. |

More arrives as the week goes on. The academy site tells you what to open for each lab.

## Branches

- `main` is where you start. Commit your work as you go; it stays on your laptop.
- `m1-solution` to `m4-solution` hold a finished version of each module, for comparison or to catch up. Switch with `git switch m1-solution`, and back with `git switch main`.
