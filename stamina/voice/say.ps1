param(
  [string]$Path = '',
  [string]$Voice = '',
  [int]$Rate = 0,
  [int]$Volume = 100,
  [switch]$ListVoices
)
# ВНИМАНИЕ: файл только из ASCII. PowerShell 5.1 читает .ps1 без BOM как ANSI,
# поэтому кириллица здесь ломает разбор. Текст приходит через -Path (UTF-8).
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech

$s = New-Object System.Speech.Synthesis.SpeechSynthesizer

if ($ListVoices) {
  foreach ($v in $s.GetInstalledVoices()) {
    if ($v.Enabled) { Write-Output ($v.VoiceInfo.Name + '|' + $v.VoiceInfo.Culture.Name) }
  }
  exit 0
}

if (-not $Path) { throw 'Path is required (use -ListVoices to list voices)' }
$text = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue

if ($Voice) {
  $pick = $s.GetInstalledVoices() |
    Where-Object { $_.Enabled -and $_.VoiceInfo.Name -like "*$Voice*" } |
    Select-Object -First 1
  if (-not $pick) {
    $all = ($s.GetInstalledVoices() | Where-Object { $_.Enabled } | ForEach-Object { $_.VoiceInfo.Name }) -join '; '
    throw ("Voice not found: " + $Voice + ". Available: " + $all)
  }
  $s.SelectVoice($pick.VoiceInfo.Name)
} else {
  $ru = $s.GetInstalledVoices() |
    Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'ru*' } |
    Select-Object -First 1
  if ($ru) { $s.SelectVoice($ru.VoiceInfo.Name) }
}

$s.Rate = $Rate
$s.Volume = $Volume
Write-Output ("voice: " + $s.Voice.Name)
$s.Speak($text)
$s.Dispose()
