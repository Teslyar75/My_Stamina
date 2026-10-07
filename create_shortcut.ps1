# ----------------------------------------------------------------
# Star Typing (formerly Stamina) - create a desktop shortcut.
# Run:  powershell -ExecutionPolicy Bypass -File create_shortcut.ps1
# ----------------------------------------------------------------

$ErrorActionPreference = "Stop"

$root   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$mainPy = Join-Path $root "main.py"

# pythonw.exe runs the GUI without a console window; fallback to python.exe
$target = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $target) {
    $target = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
}
if (-not $target) {
    Write-Error "pythonw.exe / python.exe not found in PATH."
    exit 1
}

# Star icon from the project; fallback: Windows shell32 keyboard icon
$ico = Join-Path $root "stamina\assets\star_typing.ico"
if (Test-Path $ico) { $iconLocation = "$ico,0" }
else { $iconLocation = "$env:SystemRoot\System32\shell32.dll,173" }

$desktop = [Environment]::GetFolderPath("Desktop")
$lnkPath = Join-Path $desktop "Star Typing.lnk"
$oldLnk  = Join-Path $desktop "Stamina.lnk"   # old name (before the rename)
if (Test-Path $oldLnk) { Remove-Item $oldLnk }

$wsh      = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($lnkPath)
$shortcut.TargetPath       = $target
$shortcut.Arguments        = "`"$mainPy`""
$shortcut.WorkingDirectory = $root
$shortcut.WindowStyle      = 1
$shortcut.IconLocation     = $iconLocation
$shortcut.Description      = "Star Typing - touch typing trainer (formerly Stamina)"
$shortcut.Save()

Write-Host "Shortcut created:" -ForegroundColor Green
Write-Host "  $lnkPath"
Write-Host "Runs: $target $mainPy"
