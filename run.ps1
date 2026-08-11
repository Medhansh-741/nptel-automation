# ============================================================================
# NPTEL Course Automation Pipeline — launcher
# Loads .env (device config), ensures Ollama is up with the OCR model loaded,
# validates the DB exists, then hands off to the assistant.
# Usage:  .\run.ps1
# ============================================================================

$ErrorActionPreference = "Stop"

function Read-EnvFile([string]$Path) {
    $envMap = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $envMap
    }
    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $kv = $line.Split("=", 2)
            $envMap[$kv[0].Trim()] = $kv[1].Trim()
        }
    }
    return $envMap
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$envFile = Join-Path $Root ".env"

Write-Host "=== NPTEL Course Automation Pipeline ==="

if (-not (Test-Path -LiteralPath $envFile)) {
    Write-Warning ".env missing. Copy .env.example to .env and fill in your device values first."
    exit 1
}

$cfg = Read-EnvFile $envFile

$ollamaHost = $cfg["OLLAMA_HOST"]
$model      = $cfg["OLLAMA_MODEL"]
$dbPath     = Join-Path $Root $cfg["DB_PATH"]
$keepAlive  = if ($cfg.ContainsKey("OLLAMA_KEEP_ALIVE")) { $cfg["OLLAMA_KEEP_ALIVE"] } else { "-1" }

Write-Host "Ollama host : $ollamaHost"
Write-Host "OCR model   : $model"
Write-Host "DB path     : $dbPath"

$ollamaRunning = Get-Process -Name ollama -ErrorAction SilentlyContinue
if (-not $ollamaRunning) {
    Write-Host "Starting ollama serve (keep_alive=$keepAlive)..."
    $env:OLLAMA_KEEP_ALIVE = $keepAlive
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 5
} else {
    Write-Host "ollama already running."
}

Write-Host "Checking model list..."
$models = ollama list 2>$null | Select-String $model
if ($models) {
    Write-Host "Model '$model' present:"
    $models | ForEach-Object { Write-Host "  $($_.Line.Trim())" }
} else {
    Write-Warning "Model '$model' not found. Create it once with:  ollama create $model -f Modelfile"
}

if (-not (Test-Path -LiteralPath $dbPath)) {
    Write-Warning "DB not found at $dbPath. Ensure db/schema.sql has been applied."
} else {
    Write-Host "DB present ($((Get-Item -LiteralPath $dbPath).Length) bytes)."
}

Write-Host ""
Write-Host "Session check: state.json / browser profile managed by the assistant via the Playwright MCP browser."
Write-Host "Handing off to assistant: auth check -> inventory -> dispatch."
