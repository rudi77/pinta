# Pinta Dev-Launcher — Stop-Helper
#
# Beendet alle Pinta-Dev-Prozesse: identifiziert Fenster mit Titel
# 'Pinta: backend' / 'Pinta: telegram-bot' / 'Pinta: frontend' (gestartet
# durch start_dev.ps1) und schliesst sie. Fallback: kills python/node, die
# auf den bekannten Pinta-Ports lauschen.
#
# Usage:
#   .\scripts\stop_dev.ps1                # stoppt was start_dev.ps1 gestartet hat
#   .\scripts\stop_dev.ps1 -All           # zusaetzlich alle pinta-relevanten
#                                           Listener auf 8000/8001/5183 killen

[CmdletBinding()]
param([switch]$All)

$ErrorActionPreference = 'SilentlyContinue'

$titles = @('Pinta: backend', 'Pinta: telegram-bot', 'Pinta: frontend')
$killed = 0

# 1) Eigene start_dev-Fenster zumachen
foreach ($t in $titles) {
    $procs = Get-Process pwsh -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowTitle -eq $t }
    foreach ($p in $procs) {
        Write-Host "  - kille pwsh PID $($p.Id) ($t)"
        Stop-Process -Id $p.Id -Force
        $killed++
    }
}

# 2) Optional: alle Listener auf bekannten Ports killen
if ($All) {
    $ports = @(8000, 8001, 5173, 5183)
    foreach ($port in $ports) {
        $conn = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
        foreach ($c in $conn) {
            $p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
            if ($p) {
                Write-Host "  - kille $($p.ProcessName) PID $($c.OwningProcess) (Port $port)"
                Stop-Process -Id $c.OwningProcess -Force
                $killed++
            }
        }
    }
}

if ($killed -eq 0) {
    Write-Host "Nichts zum Stoppen gefunden."
} else {
    Write-Host "$killed Prozess(e) beendet." -ForegroundColor Green
}
