param(
  [string]$Path = '',
  [string]$Voice = '',
  [string]$Lang = '',
  [int]$Rate = 0,
  [int]$Volume = 100,
  [string]$Pitch = '',
  [switch]$Pauses,
  [switch]$ListVoices
)
# NOTE: keep this file pure ASCII. PowerShell 5.1 reads a .ps1 without BOM as ANSI,
# so any non-ASCII byte here breaks parsing. The spoken text arrives via -Path (UTF-8).
#
# Why OneCore: the newest Windows voices (Russian male "Microsoft Pavel" and friends)
# live in the OneCore voice store, and System.Speech cannot see them at all - it only
# offers the old desktop voices (Irina, Zira - both female). So we synthesize speech
# with Windows.Media.SpeechSynthesis (WinRT) and play the WAV with System.Media.SoundPlayer.
# If WinRT is missing (server builds, stripped installs) we fall back to System.Speech,
# so the ship always has a voice.
$ErrorActionPreference = 'Stop'

$onecore = $false
$synth = $null
$streamType = $null
$asTask = $null
try {
  Add-Type -AssemblyName System.Runtime.WindowsRuntime
  $null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media, ContentType=WindowsRuntime]
  $streamType = [Windows.Media.SpeechSynthesis.SpeechSynthesisStream, Windows.Media, ContentType=WindowsRuntime]
  $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
      $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
      $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
  $synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
  $onecore = $true
} catch {
  $onecore = $false
}

if ($ListVoices) {
  if ($onecore) {
    foreach ($v in [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices) {
      Write-Output ('OneCore|' + $v.DisplayName + '|' + $v.Language + '|' + $v.Gender)
    }
  }
  Add-Type -AssemblyName System.Speech
  $sapi = New-Object System.Speech.Synthesis.SpeechSynthesizer
  foreach ($v in $sapi.GetInstalledVoices()) {
    if ($v.Enabled) {
      Write-Output ('SAPI|' + $v.VoiceInfo.Name + '|' + $v.VoiceInfo.Culture.Name + '|' + $v.VoiceInfo.Gender)
    }
  }
  exit 0
}

if (-not $Path) { throw 'Path is required (use -ListVoices to list voices)' }
$text = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue

if ($onecore) {
  $all = @([Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices)
  $pick = $null
  if ($Voice) {
    $pick = $all | Where-Object { $_.DisplayName -like ('*' + $Voice + '*') } | Select-Object -First 1
  }
  if (-not $pick -and $Lang) {
    # Voice by the language of the text: an English book must not be read by Pavel,
    # and a Russian report must not be read by an English voice.
    $pool = @($all | Where-Object { $_.Language -like ($Lang + '*') })
    $male = $pool | Where-Object { $_.Gender -eq 'Male' } | Select-Object -First 1
    if ($male) { $pick = $male } elseif ($pool.Count -gt 0) { $pick = $pool[0] }
  }
  if (-not $pick) {
    # Last resort: the ship's own language, male preferred (Pavel, never Irina).
    $ru = @($all | Where-Object { $_.Language -like 'ru*' })
    $male = $ru | Where-Object { $_.Gender -eq 'Male' } | Select-Object -First 1
    if ($male) { $pick = $male } elseif ($ru.Count -gt 0) { $pick = $ru[0] }
  }
  if (-not $pick) { $pick = $all | Select-Object -First 1 }
  if ($pick) { $synth.Voice = $pick }

  $speed = [double]1 + ([double]$Rate * 0.12)
  if ($speed -lt 0.5) { $speed = 0.5 }
  if ($speed -gt 2.5) { $speed = 2.5 }
  # Developer role (-Pitch, -Pauses): slightly lower pitch and short breaks after
  # commas and full stops make a status report sound less robotic.
  $body = [System.Security.SecurityElement]::Escape($text)
  if ($Pauses) {
    $body = [regex]::Replace($body, '([,;:])\s+', '$1<break time="160ms"/> ')
    $body = [regex]::Replace($body, '([.!?])\s+', '$1<break time="360ms"/> ')
  }
  $pitchAttr = ''
  if ($Pitch -match '^[+-]?\d+%$') { $pitchAttr = " pitch='" + $Pitch + "'" }
  $ssml = "<speak version='1.0' xml:lang='" + $synth.Voice.Language + "'><prosody rate='" +
    $speed.ToString([Globalization.CultureInfo]::InvariantCulture) + "'" + $pitchAttr + ">" +
    $body + '</prosody></speak>'

  $task = $synth.SynthesizeSsmlToStreamAsync($ssml)
  $waiter = $asTask.MakeGenericMethod($streamType).Invoke($null, @($task))
  $waiter.Wait(-1) | Out-Null
  $net = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($waiter.Result)
  $ms = New-Object System.IO.MemoryStream
  $net.CopyTo($ms)

  Write-Output ('voice: ' + $synth.Voice.DisplayName)
  $player = New-Object System.Media.SoundPlayer
  $player.Stream = New-Object System.IO.MemoryStream(, $ms.ToArray())
  $player.PlaySync()
  $player.Dispose()
  exit 0
}

Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
if ($Voice) {
  $p = $s.GetInstalledVoices() |
    Where-Object { $_.Enabled -and $_.VoiceInfo.Name -like ('*' + $Voice + '*') } |
    Select-Object -First 1
  if ($p) { $s.SelectVoice($p.VoiceInfo.Name) }
} else {
  # Classic store: here English means Zira, Russian means Irina - both female, that is
  # all this store has. Still respect the language of the text.
  $sapiPick = $null
  if ($Lang) {
    $sapiPick = $s.GetInstalledVoices() |
      Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like ($Lang + '*') } |
      Select-Object -First 1
  }
  if (-not $sapiPick) {
    $sapiPick = $s.GetInstalledVoices() |
      Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'ru*' } |
      Select-Object -First 1
  }
  if ($sapiPick) { $s.SelectVoice($sapiPick.VoiceInfo.Name) }
}
$s.Rate = $Rate
$s.Volume = $Volume
Write-Output ('voice: ' + $s.Voice.Name)
$s.Speak($text)
$s.Dispose()
