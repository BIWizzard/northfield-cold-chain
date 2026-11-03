# Preflight check for the Northfield cold-chain training (Windows).
# Run from the repo root:
#   powershell -ExecutionPolicy Bypass -File preflight\preflight.ps1
# Compatible with Windows PowerShell 5.1. Never prints secrets.

$ErrorActionPreference = 'Continue'
$script:failed = 0
$port = 8765

function Pass($name, $detail) { Write-Host ("PASS  {0}{1}" -f $name, $(if ($detail) { ": $detail" } else { '' })) }
function Info($name, $detail) { Write-Host ("INFO  {0}{1}" -f $name, $(if ($detail) { ": $detail" } else { '' })) }
function Fail($name, $detail, $fix) {
    $script:failed++
    Write-Host ("FAIL  {0}{1}" -f $name, $(if ($detail) { ": $detail" } else { '' }))
    Write-Host ("      Fix: {0}" -f $fix)
}
function Find-Cmd($name) {
    $c = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($c) { return $c.Source }
    return $null
}
function Get-VersionFrom($text) {
    if ($text -match '(\d+)\.(\d+)(?:\.(\d+))?') {
        $patch = if ($Matches[3]) { $Matches[3] } else { '0' }
        return [version]("{0}.{1}.{2}" -f $Matches[1], $Matches[2], $patch)
    }
    return $null
}

# Minimum Claude Code version: defined once in preflight\min-claude-version.txt
$minFile = Join-Path $PSScriptRoot 'min-claude-version.txt'
$minVersion = $null
if (Test-Path $minFile) {
    $minVersion = Get-VersionFrom ((Get-Content $minFile -TotalCount 1) | Out-String)
}

# 1. Starter repo
if (Test-Path -LiteralPath 'data\sop\thresholds.json') {
    Pass 'Starter repo' 'running from the repo root'
} else {
    Fail 'Starter repo' 'data\sop\thresholds.json not found' 'cd into the cloned northfield-cold-chain repo, then run this script again.'
}

# 2. Git
$gitPath = Find-Cmd 'git'
$gitOut = $null
if ($gitPath) { $gitOut = (& git --version | Out-String).Trim() }
if (-not $gitOut) {
    Fail 'Git' 'git --version did not run' 'Install Git for Windows from https://git-scm.com/download/win'
} else {
    $bash = $null
    $dir = Split-Path -Parent $gitPath
    for ($i = 0; $i -lt 3 -and $dir -and -not $bash; $i++) {
        $cand = Join-Path $dir 'bin\bash.exe'
        if (Test-Path $cand) { $bash = $cand }
        $dir = Split-Path -Parent $dir
    }
    if ($bash) { Pass 'Git' "$gitOut, bash.exe found" }
    else { Fail 'Git' "$gitOut, but bash.exe not found in the Git install" 'Install Git for Windows from https://git-scm.com/download/win (it includes Git Bash).' }
}

# 3. Python
$pyPath = Find-Cmd 'python'
$pyFix = 'Install Python 3.10+ from https://www.python.org/downloads/ and turn off the App Execution Aliases for python.exe and python3.exe (Settings > Apps > Advanced app settings > App execution aliases).'
if (-not $pyPath) {
    Fail 'Python' 'python not found on the path' $pyFix
} elseif ($pyPath -like '*\WindowsApps\*') {
    Fail 'Python' 'python resolves to the Microsoft Store alias' $pyFix
} else {
    $pyOut = (& python --version | Out-String).Trim()
    $pyVer = Get-VersionFrom $pyOut
    if (-not $pyVer) { Fail 'Python' 'python --version gave no version' $pyFix }
    elseif ($pyVer -lt [version]'3.10.0') { Fail 'Python' "$pyOut is older than 3.10" $pyFix }
    else { Pass 'Python' $pyOut }
}

# 4. Claude Code
$claudePath = Find-Cmd 'claude'
$claudeOK = $false
if (-not $claudePath) {
    Fail 'Claude Code' 'claude not found on the path' 'Install or update Claude Code: https://code.claude.com/docs/en/setup'
} else {
    $cOut = (& claude --version | Out-String).Trim()
    $cVer = Get-VersionFrom $cOut
    if (-not $cVer) {
        Fail 'Claude Code' 'claude --version gave no version' 'Update Claude Code: claude update'
    } elseif (-not $minVersion) {
        Fail 'Claude Code' 'minimum version file missing or unreadable (preflight\min-claude-version.txt)' 'Restore preflight\min-claude-version.txt from the repo.'
    } elseif ($cVer -lt $minVersion) {
        Fail 'Claude Code' "$cOut is below the minimum $minVersion" 'Update Claude Code: claude update'
    } else {
        Pass 'Claude Code' "$cOut (minimum $minVersion)"
        $claudeOK = $true
    }
}

# 5. Sign-in
if ($claudePath) {
    $authText = (& claude auth status --json | Out-String)
    $auth = $null
    try { $auth = $authText | ConvertFrom-Json } catch { }
    if ($auth -and $auth.loggedIn -eq $true) {
        Pass 'Sign-in' 'loggedIn: true'
    } else {
        Fail 'Sign-in' 'not signed in' 'Sign in with the method your organization provides (run: claude auth login, or follow your onboarding instructions).'
    }
    if ($auth) {
        Info 'Auth method' ([string]$auth.authMethod)
        Info 'API provider' ([string]$auth.apiProvider)
    }
} else {
    Fail 'Sign-in' 'cannot check, Claude Code is not installed' 'Install Claude Code first, then sign in.'
}
if ($env:ANTHROPIC_API_KEY) { Info 'ANTHROPIC_API_KEY' 'set' } else { Info 'ANTHROPIC_API_KEY' 'not set' }

# 6. Round trip
$rtFix = 'If the message says the API key is invalid, unset or correct ANTHROPIC_API_KEY. On a certificate error, set NODE_EXTRA_CA_CERTS to your organization CA bundle. Behind a proxy, set HTTPS_PROXY.'
if ($claudePath) {
    $job = Start-Job -ScriptBlock {
        $o = & claude -p 'Reply with the single word: ready' 2>&1 | Out-String
        [pscustomobject]@{ Out = $o; Code = $LASTEXITCODE }
    }
    if (Wait-Job $job -Timeout 90) {
        $res = Receive-Job $job
        if ($res.Code -eq 0 -and $res.Out.Trim()) {
            Pass 'Round trip' 'claude -p returned a response'
        } else {
            if ($res.Out -match '(?i)api key') {
                Fail 'Round trip' 'API key rejected' 'Unset or correct ANTHROPIC_API_KEY (Remove-Item Env:ANTHROPIC_API_KEY), then sign in with the method your organization provides.'
            } elseif ($res.Out -match '(?i)certificate|self.signed|unable to verify|CERT_|SSL') {
                Fail 'Round trip' 'certificate error' 'Set NODE_EXTRA_CA_CERTS to your organization CA bundle.'
            } elseif ($res.Out -match '(?i)proxy|ECONNREFUSED|ENOTFOUND|ETIMEDOUT|ECONNRESET|network|fetch failed|unable to connect') {
                Fail 'Round trip' 'proxy or network error' 'Behind a proxy, set HTTPS_PROXY.'
            } else {
                Fail 'Round trip' 'claude -p did not return a response' $rtFix
                # Unknown error: show claude's own last line (ASCII only, key-like strings redacted, truncated)
                $last = ($res.Out -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -Last 1)
                if ($last) {
                    $last = $last -replace '[^\x20-\x7E]', ' ' -replace 'sk-[A-Za-z0-9_\-]{8,}', '[redacted]'
                    if ($last.Length -gt 200) { $last = $last.Substring(0, 200) }
                    Write-Host ("      Claude said: {0}" -f $last.Trim())
                }
            }
        }
    } else {
        Stop-Job $job
        Fail 'Round trip' 'timed out after 90 seconds (likely a proxy or network problem)' 'Behind a proxy, set HTTPS_PROXY. On a certificate error, set NODE_EXTRA_CA_CERTS to your organization CA bundle.'
    }
    Remove-Job $job -Force
} else {
    Fail 'Round trip' 'cannot check, Claude Code is not installed' 'Install Claude Code first.'
}

# 7. Interface (INFO)
$vsc = $false
$codePath = Find-Cmd 'code'
if ($codePath) {
    $exts = (& code --list-extensions | Out-String)
    if ($exts -match 'anthropic\.claude-code') { $vsc = $true }
}
if (-not $vsc) {
    $extDir = Join-Path $env:USERPROFILE '.vscode\extensions'
    if ((Test-Path $extDir) -and (Get-ChildItem $extDir -Directory -Filter 'anthropic.claude-code-*' -ErrorAction SilentlyContinue)) { $vsc = $true }
}
if ($vsc) { Info 'Interface' 'VS Code extension installed' } else { Info 'Interface' 'VS Code extension not found' }

# 8. App port (INFO)
$listener = $null
try {
    $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Parse('127.0.0.1'), $port)
    $listener.Start()
    $listener.Stop()
    Info 'App port' "$port is free on 127.0.0.1"
} catch {
    Info 'App port' "$port is in use on 127.0.0.1; start the app with --port"
}

# 9. Browser checks (INFO)
if (Find-Cmd 'npx') { Info 'Browser checks' 'npx found (Playwright MCP available)' }
else { Info 'Browser checks' 'npx not found; the bug hunt falls back to the browser console' }

if ($script:failed -gt 0) {
    Write-Host ''
    Write-Host ("{0} check(s) failed." -f $script:failed)
    exit 1
}
Write-Host ''
Write-Host 'All checks passed.'
exit 0
