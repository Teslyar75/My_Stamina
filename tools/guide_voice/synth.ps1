param([Parameter(Mandatory=$true)][string]$Jobs)
# Build-time only: render a batch of phrases to WAV files with the offline Windows
# OneCore voices (Microsoft Pavel / Irina). Keep this file pure ASCII.
# Jobs: UTF-8 JSON array of {text, voice, out, rate, pitch, pauses}.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media, ContentType=WindowsRuntime]
$streamType = [Windows.Media.SpeechSynthesis.SpeechSynthesisStream, Windows.Media, ContentType=WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
$synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$all = @([Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices)
$list = [System.IO.File]::ReadAllText($Jobs, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
$inv = [Globalization.CultureInfo]::InvariantCulture
foreach ($j in $list) {
  $v = $all | Where-Object { $_.DisplayName -like ('*' + $j.voice + '*') } | Select-Object -First 1
  if (-not $v) { throw ('voice not found: ' + $j.voice) }
  $synth.Voice = $v
  $body = [System.Security.SecurityElement]::Escape([string]$j.text)
  if ($j.pauses) {
    $body = [regex]::Replace($body, '([,;:])\s+', '$1<break time="160ms"/> ')
    $body = [regex]::Replace($body, '([.!?])\s+', '$1<break time="360ms"/> ')
  }
  $attrs = "rate='" + ([double]$j.rate).ToString($inv) + "'"
  if ($j.pitch) { $attrs += " pitch='" + $j.pitch + "'" }
  $ssml = "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='" + $v.Language +
    "'><prosody " + $attrs + ">" + $body + '</prosody></speak>'
  $task = $synth.SynthesizeSsmlToStreamAsync($ssml)
  $w = $asTask.MakeGenericMethod($streamType).Invoke($null, @($task))
  $w.Wait(-1) | Out-Null
  $net = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($w.Result)
  $fs = [System.IO.File]::Create([string]$j.out)
  $net.CopyTo($fs)
  $fs.Close()
  Write-Output ('ok ' + $j.out)
}
