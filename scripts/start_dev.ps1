# Pinta Dev-Launcher
#
# Startet Backend, Telegram-Bot und Frontend in drei eigenen pwsh-Fenstern,
# damit du jeden Prozess separat sehen, restarten und mit Ctrl+C killen
# kannst. Eigene Fenster (statt Background-Jobs) weil:
#   - Backend-Lifespan-Output (Azure-Bridge-Status, agent.profile_rendered)
#     willst du beim Start direkt sehen.
#   - Telegram-Polling logged jede inbound-Message — gehört nicht in den
#     Backend-Stream gemischt.
#   - Vite hat einen eigenen HMR-Reload-Output.
#
# Usage:
#   .\scripts\start_dev.ps1                       # default: alle drei
#   .\scripts\start_dev.ps1 -SkipBot              # ohne Telegram-Bot
#   .\scripts\start_dev.ps1 -SkipFrontend         # nur Backend + Bot
#   .\scripts\start_dev.ps1 -BackendPort 8001     # Backend auf 8001
#
# Stoppen: Ctrl+C in jedem Fenster, oder einmal `.\scripts\stop_dev.ps1`.

[CmdletBinding()]
param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5183,
    [switch]$SkipBackend,
    [switch]$SkipBot,
    [switch]$SkipFrontend
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$BackendDir = Join-Path $RepoRoot 'backend'
$FrontendDir = Join-Path $RepoRoot 'frontend'
$VenvPython = Join-Path $BackendDir '.venv\Scripts\python.exe'

function Test-PortFree {
    param([int]$Port)
    -not (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

function Start-DevWindow {
    param(
        [string]$Title,
        [string]$WorkingDirectory,
        [string]$Command
    )
    # Opens a NEW pwsh window. -NoExit keeps the window alive after the
    # command exits so you can read tracebacks. Window title makes it easy
    # to find with stop_dev.ps1.
    Start-Process pwsh -ArgumentList @(
        '-NoLogo',
        '-NoExit',
        '-Command',
        "`$Host.UI.RawUI.WindowTitle = 'Pinta: $Title'; Set-Location '$WorkingDirectory'; $Command"
    ) | Out-Null
    Write-Host "  ✓ $Title gestartet (Fenster: 'Pinta: $Title')" -ForegroundColor Green
}

# ── Pre-flight checks ────────────────────────────────────────────────────
if (-not (Test-Path $VenvPython)) {
    throw "Backend venv fehlt: $VenvPython`n  Erst: cd backend; python -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
}
if (-not (Test-Path (Join-Path $FrontendDir 'node_modules'))) {
    throw "Frontend node_modules fehlt: $FrontendDir\node_modules`n  Erst: cd frontend; npm install"
}

if (-not $SkipBackend -and -not (Test-PortFree $BackendPort)) {
    throw "Port $BackendPort ist belegt. Anderer Backend-Prozess läuft? Mit -BackendPort 8001 ausweichen oder stop_dev.ps1 / taskkill nutzen."
}
if (-not $SkipFrontend -and -not (Test-PortFree $FrontendPort)) {
    throw "Port $FrontendPort ist belegt. Vite läuft schon? stop_dev.ps1 nutzen oder anderen Port konfigurieren."
}

# ── Boot ─────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Pinta Dev-Stack startet…" -ForegroundColor Cyan
Write-Host "  Backend:  http://127.0.0.1:$BackendPort"
Write-Host "  Frontend: http://127.0.0.1:$FrontendPort"
Write-Host "  Bot:      Long-Polling, sendet an `$BOT_BACKEND_URL"
Write-Host ""

if (-not $SkipBackend) {
    Start-DevWindow -Title "backend" -WorkingDirectory $BackendDir -Command @"
& '$VenvPython' -m uvicorn src.main:app --host 127.0.0.1 --port $BackendPort
"@
}

if (-not $SkipBot) {
    # Bot calls the backend via BOT_BACKEND_URL (default http://127.0.0.1:8000).
    # If the launcher uses a non-default port, override the env so the bot
    # talks to the running backend, not a phantom one.
    $botBackendUrl = "http://127.0.0.1:$BackendPort"
    Start-DevWindow -Title "telegram-bot" -WorkingDirectory $RepoRoot -Command @"
`$env:BOT_BACKEND_URL = '$botBackendUrl'
& '$VenvPython' scripts/run_telegram_bot.py
"@
}

if (-not $SkipFrontend) {
    Start-DevWindow -Title "frontend" -WorkingDirectory $FrontendDir -Command @"
npm run dev -- --host 127.0.0.1
"@
}

Write-Host ""
Write-Host "Drei Fenster sollten sich geöffnet haben." -ForegroundColor Cyan
Write-Host "Stop:  .\scripts\stop_dev.ps1  ODER  Ctrl+C in jedem Fenster."
Write-Host ""
