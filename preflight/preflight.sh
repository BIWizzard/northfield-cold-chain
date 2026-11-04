#!/bin/bash
# Preflight check for the Northfield cold-chain training (macOS).
# Run from the repo root:  bash preflight/preflight.sh
# Compatible with bash 3.2. Never prints secrets.

failed=0
port=8765
script_dir="$(cd "$(dirname "$0")" && pwd)"

pass() { if [ -n "$2" ]; then echo "PASS  $1: $2"; else echo "PASS  $1"; fi; }
info() { if [ -n "$2" ]; then echo "INFO  $1: $2"; else echo "INFO  $1"; fi; }
fail() {
  failed=$((failed + 1))
  if [ -n "$2" ]; then echo "FAIL  $1: $2"; else echo "FAIL  $1"; fi
  echo "      Fix: $3"
}

# Extract first x.y[.z] from text, padded to x.y.z
extract_version() {
  local v
  v=$(echo "$1" | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
  [ -z "$v" ] && return 1
  case "$v" in *.*.*) ;; *) v="$v.0" ;; esac
  echo "$v"
}

# version_ge A B: true when A >= B
version_ge() {
  local a1 a2 a3 b1 b2 b3
  IFS=. read -r a1 a2 a3 <<EOF
$1
EOF
  IFS=. read -r b1 b2 b3 <<EOF
$2
EOF
  [ "$a1" -gt "$b1" ] && return 0; [ "$a1" -lt "$b1" ] && return 1
  [ "$a2" -gt "$b2" ] && return 0; [ "$a2" -lt "$b2" ] && return 1
  [ "${a3:-0}" -ge "${b3:-0}" ]
}

# Minimum Claude Code version: defined once in preflight/min-claude-version.txt
min_version=""
if [ -f "$script_dir/min-claude-version.txt" ]; then
  min_version=$(extract_version "$(head -1 "$script_dir/min-claude-version.txt")")
fi

# 1. Starter repo
if [ -f data/sop/thresholds.json ]; then
  pass "Starter repo" "running from the repo root"
else
  fail "Starter repo" "data/sop/thresholds.json not found" "cd into the cloned northfield-cold-chain repo, then run this script again."
fi

# 2. Git
git_out=$(git --version 2>/dev/null)
if [ -n "$git_out" ]; then
  pass "Git" "$git_out"
else
  fail "Git" "git --version did not run" "Run: xcode-select --install"
fi

# 3. Python. The labs, Lab 8's allow rule and the Module 3 hooks all call
# "python", so only the "python" command counts. A stock macOS install from
# python.org or Homebrew usually provides python3 but no python.
py_fix="Install Python 3.10+ from https://www.python.org/downloads/ (or: brew install python)."
if command -v python >/dev/null 2>&1; then
  py_out=$(python --version 2>&1)
  py_ver=$(extract_version "$py_out")
  if [ -z "$py_ver" ]; then
    fail "Python" "python --version gave no version" "$py_fix"
  elif version_ge "$py_ver" "3.10.0"; then
    pass "Python" "$py_out"
  else
    fail "Python" "$py_out is older than 3.10" "$py_fix"
  fi
elif command -v python3 >/dev/null 2>&1; then
  nl=$'\n      '
  py3_fix="The labs, hooks and permission rules all call python, not python3. Add a real python command (no admin rights needed):${nl}- Homebrew: add \"\$(brew --prefix python)/libexec/bin\" to the PATH in ~/.zshrc${nl}- python.org: mkdir -p ~/.local/bin && ln -s \"\$(command -v python3)\" ~/.local/bin/python${nl}  then add ~/.local/bin to the PATH in ~/.zshrc${nl}Then open a new terminal and run this script again.${nl}Do not use a shell alias (alias python=python3): hooks and Claude's own shell do not load aliases."
  fail "Python" "found python3 but no python command" "$py3_fix"
else
  fail "Python" "python not found" "$py_fix"
fi

# 4. Claude Code
have_claude=0
if command -v claude >/dev/null 2>&1; then
  have_claude=1
  c_out=$(claude --version 2>&1)
  c_ver=$(extract_version "$c_out")
  if [ -z "$c_ver" ]; then
    fail "Claude Code" "claude --version gave no version" "Update Claude Code: claude update"
  elif [ -z "$min_version" ]; then
    fail "Claude Code" "minimum version file missing or unreadable (preflight/min-claude-version.txt)" "Restore preflight/min-claude-version.txt from the repo."
  elif version_ge "$c_ver" "$min_version"; then
    pass "Claude Code" "$c_out (minimum $min_version)"
  else
    fail "Claude Code" "$c_out is below the minimum $min_version" "Update Claude Code: claude update"
  fi
else
  fail "Claude Code" "claude not found on the path" "Install or update Claude Code: https://code.claude.com/docs/en/setup"
fi

# 5. Sign-in
if [ "$have_claude" = 1 ]; then
  auth_text=$(claude auth status --json 2>/dev/null)
  if echo "$auth_text" | grep -Eq '"loggedIn"[[:space:]]*:[[:space:]]*true'; then
    pass "Sign-in" "loggedIn: true"
  else
    fail "Sign-in" "not signed in" "Sign in with the method your organization provides (run: claude auth login, or follow your onboarding instructions)."
  fi
  val=$(echo "$auth_text" | sed -n 's/.*"authMethod"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
  [ -n "$val" ] && info "Auth method" "$val"
  val=$(echo "$auth_text" | sed -n 's/.*"apiProvider"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
  [ -n "$val" ] && info "API provider" "$val"
else
  fail "Sign-in" "cannot check, Claude Code is not installed" "Install Claude Code first, then sign in."
fi
if [ -n "$ANTHROPIC_API_KEY" ]; then info "ANTHROPIC_API_KEY" "set"; else info "ANTHROPIC_API_KEY" "not set"; fi

# 6. Round trip (90 second limit; macOS has no timeout command)
if [ "$have_claude" = 1 ]; then
  rt_file=$(mktemp "${TMPDIR:-/tmp}/preflight.XXXXXX")
  claude -p "Reply with the single word: ready" >"$rt_file" 2>&1 </dev/null &
  rt_pid=$!
  waited=0
  while kill -0 "$rt_pid" 2>/dev/null && [ "$waited" -lt 90 ]; do
    sleep 1
    waited=$((waited + 1))
  done
  rt_fix="If the message says the API key is invalid, unset or correct ANTHROPIC_API_KEY. On a certificate error, set NODE_EXTRA_CA_CERTS to your organization CA bundle. Behind a proxy, set HTTPS_PROXY."
  if kill -0 "$rt_pid" 2>/dev/null; then
    kill "$rt_pid" 2>/dev/null
    fail "Round trip" "timed out after 90 seconds (likely a proxy or network problem)" "Behind a proxy, set HTTPS_PROXY. On a certificate error, set NODE_EXTRA_CA_CERTS to your organization CA bundle."
  else
    wait "$rt_pid"
    rt_code=$?
    if [ "$rt_code" -eq 0 ] && [ -s "$rt_file" ]; then
      pass "Round trip" "claude -p returned a response"
    else
      if grep -Eiq 'api key' "$rt_file"; then
        fail "Round trip" "API key rejected" "Unset or correct ANTHROPIC_API_KEY (unset ANTHROPIC_API_KEY), then sign in with the method your organization provides."
      elif grep -Eiq 'certificate|self.signed|unable to verify|CERT_|SSL' "$rt_file"; then
        fail "Round trip" "certificate error" "Set NODE_EXTRA_CA_CERTS to your organization CA bundle."
      elif grep -Eiq 'proxy|ECONNREFUSED|ENOTFOUND|ETIMEDOUT|ECONNRESET|network|fetch failed|unable to connect' "$rt_file"; then
        fail "Round trip" "proxy or network error" "Behind a proxy, set HTTPS_PROXY."
      else
        fail "Round trip" "claude -p did not return a response" "$rt_fix"
        # Unknown error: show claude's own last line (ASCII only, key-like strings redacted, truncated)
        last=$(grep -v '^[[:space:]]*$' "$rt_file" | tail -1 | LC_ALL=C tr -c '\040-\176' ' ' | sed -E 's/sk-[A-Za-z0-9_-]{8,}/[redacted]/g' | cut -c1-200 | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')
        [ -n "$last" ] && echo "      Claude said: $last"
      fi
    fi
  fi
  rm -f "$rt_file"
else
  fail "Round trip" "cannot check, Claude Code is not installed" "Install Claude Code first."
fi

# 7. Interface (INFO)
vsc=0
if command -v code >/dev/null 2>&1 && code --list-extensions 2>/dev/null | grep -q 'anthropic\.claude-code'; then
  vsc=1
fi
if [ "$vsc" = 0 ] && ls -d "$HOME"/.vscode/extensions/anthropic.claude-code-* >/dev/null 2>&1; then
  vsc=1
fi
if [ "$vsc" = 1 ]; then info "Interface" "VS Code extension installed"; else info "Interface" "VS Code extension not found"; fi

# 8. App port (INFO): a successful connect means something is listening
if (exec 3<>/dev/tcp/127.0.0.1/$port) 2>/dev/null; then
  info "App port" "$port is in use on 127.0.0.1; start the app with --port"
else
  info "App port" "$port is free on 127.0.0.1"
fi

# 9. Browser checks (INFO)
if command -v npx >/dev/null 2>&1; then
  info "Browser checks" "npx found (Playwright MCP available)"
else
  info "Browser checks" "npx not found; the bug hunt falls back to the browser console"
fi

echo ""
if [ "$failed" -gt 0 ]; then
  echo "$failed check(s) failed."
  exit 1
fi
echo "All checks passed."
exit 0
