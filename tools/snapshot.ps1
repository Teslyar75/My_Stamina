# Снимок корабля перед рискованной правкой.
# Ставит тег snap-YYYYMMDD-HHMM и печатает строку отката.
# Запуск:  powershell -ExecutionPolicy Bypass -File tools\snapshot.ps1 [-Note "перед чем"]

param(
    [string]$Note = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location $root
try {
    $stamp = Get-Date -Format "yyyyMMdd-HHmm"
    $tag = "snap-$stamp"
    $n = 1
    while (git rev-parse -q --verify "refs/tags/$tag" 2>$null) {
        $n++
        $tag = "snap-$stamp-$n"
    }
    if ($Note) {
        git tag -a $tag -m $Note
    } else {
        git tag -a $tag -m "снимок перед правкой"
    }
    $head = git rev-parse --short HEAD
    Write-Output "снимок: $tag (коммит $head)"
    Write-Output "откат:  git checkout $tag"
} finally {
    Pop-Location
}
