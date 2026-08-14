param(
    [switch]$Check
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Stop-Launcher {
    param(
        [string]$Message
    )

    Write-Host "[ERROR] $Message" -ForegroundColor Red
    if (-not $Check) {
        Read-Host "Press Enter to close"
    }
    exit 1
}

Set-Location -LiteralPath $PSScriptRoot
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
    $pythonExecutable = $venvPython
}
else {
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        Stop-Launcher "Python was not found. Install Python 3.12 or newer first."
    }
    $pythonExecutable = $pythonCommand.Source
}

& $pythonExecutable -c "import streamlit" *> $null
if ($LASTEXITCODE -ne 0) {
    Stop-Launcher "Project dependencies are missing. Run: python -m pip install -r requirements.txt"
}

if ($Check) {
    Write-Host "Launcher check passed."
    exit 0
}

if ([string]::IsNullOrWhiteSpace($env:DEEPSEEK_API_KEY)) {
    Write-Host "[INFO] DEEPSEEK_API_KEY is not configured." -ForegroundColor Yellow
    Write-Host "[INFO] The app will start without AI chat; local demo data management remains available."
    Write-Host ""
}

Write-Host "Starting Enterprise Data Q&A Assistant. Keep this window open..."
& $pythonExecutable -m streamlit run app.py

if ($LASTEXITCODE -ne 0) {
    Stop-Launcher "The app failed to start. Review the messages above."
}
