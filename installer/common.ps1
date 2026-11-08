# Shared helpers for the Queen's Domain Arabic patch installer / uninstaller.
Add-Type -AssemblyName System.Windows.Forms, System.Drawing

$PatchName      = 'zz_QueensDomain_Arabic_P.pak'
$PatchVersion   = '1.3.2'
# PAK installation is version-independent. Only the optional EXE patch is hash-gated.
# Optional right-to-left letter reveal: an 11-byte hook + 97-byte routine in unused padding of the game exe
# (see source\tools\exepatch.py). Applied and reverted byte-for-byte, always verified by SHA-256.
$ExeRel         = 'QueensDomain\Binaries\Win64\QueensDomain-Win64-Shipping.exe'
$ExeOrigHash    = '8D805CFF01753F9066BF60E4432A02D91533E4741AC0EAF1649B3C1CD17EE9CF'
$ExePatchedHash = 'D3FD3846E99EEED520CD71BA71F50C45760DA73FA4192EFE07AB08B6C791A417'
$PackageRoot = Split-Path -Parent $PSScriptRoot
$LogDir      = Join-Path $env:LOCALAPPDATA 'QueensDomainArabic'
$LogFile     = Join-Path $LogDir 'install.log'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log([string]$msg) {
  $line = '{0}  {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
  Add-Content -Path $LogFile -Value $line -Encoding UTF8
  Write-Host $line
}

function Show-Msg([string]$text, [string]$title = 'تعريب Queen''s Domain', [string]$icon = 'Information') {
  if ($env:QDA_SILENT -eq '1') { Write-Host "[$icon] $text"; return }   # unattended test mode
  $opts = [System.Windows.Forms.MessageBoxOptions]::RtlReading -bor [System.Windows.Forms.MessageBoxOptions]::RightAlign
  [System.Windows.Forms.MessageBox]::Show($text, $title, 'OK', $icon, 'Button1', $opts) | Out-Null
}

function Ask-YesNo([string]$text) {
  if ($env:QDA_SILENT -eq '1') { Write-Host "[?] $text"; return ($env:QDA_EXEPATCH -ne '0') }   # unattended test mode
  $opts = [System.Windows.Forms.MessageBoxOptions]::RtlReading -bor [System.Windows.Forms.MessageBoxOptions]::RightAlign
  return ([System.Windows.Forms.MessageBox]::Show($text, 'تعريب Queen''s Domain', 'YesNo', 'Question', 'Button1', $opts) -eq 'Yes')
}

function Get-BytesHash([byte[]]$bytes) {
  return ([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash($bytes)) -replace '-', '')
}

function ConvertFrom-Hex([string]$hex) {
  $b = New-Object byte[] ($hex.Length / 2)
  for ($i = 0; $i -lt $b.Length; $i++) { $b[$i] = [Convert]::ToByte($hex.Substring(2 * $i, 2), 16) }
  return ,$b
}

# Applies ($apply = $true) or reverts the exe patch. Every patched range is checked before writing and the
# whole result must match the expected SHA-256, otherwise nothing is written.
function Set-ExePatch([string]$exe, [bool]$apply) {
  $spec  = Get-Content (Join-Path $PackageRoot 'files\exe_patch.json') -Raw | ConvertFrom-Json
  $bytes = [IO.File]::ReadAllBytes($exe)
  foreach ($p in $spec.patches) {
    if ($apply) { $from = ConvertFrom-Hex $p.old; $to = ConvertFrom-Hex $p.new }
    else        { $from = ConvertFrom-Hex $p.new; $to = ConvertFrom-Hex $p.old }
    for ($i = 0; $i -lt $from.Length; $i++) {
      if ($bytes[$p.offset + $i] -ne $from[$i]) { throw 'محتوى الملف التنفيذي غير متوقع؛ لم يُغيَّر أي ملف.' }
    }
    [Array]::Copy($to, 0, $bytes, $p.offset, $to.Length)
  }
  $want = if ($apply) { $ExePatchedHash } else { $ExeOrigHash }
  if ((Get-BytesHash $bytes) -ne $want) { throw 'فشل التحقق من الملف التنفيذي بعد التعديل؛ لم يُغيَّر أي ملف.' }
  $tmp = "$exe.qda_tmp"
  [IO.File]::WriteAllBytes($tmp, $bytes)
  Move-Item -Path $tmp -Destination $exe -Force
  if ((Get-FileHash -Algorithm SHA256 $exe).Hash -ne $want) { throw 'فشل التحقق من الملف التنفيذي بعد الكتابة.' }
}

# Plain .NET path checks: unlike Join-Path/Test-Path they never throw for a drive letter that does not exist
# (e.g. a Steam library on a removed disk listed in libraryfolders.vdf).
function Test-GameDir([string]$dir) {
  try { return ($dir -and [IO.File]::Exists([IO.Path]::Combine($dir, 'QueensDomain\Content\Paks\QueensDomain-WindowsNoEditor.pak'))) }
  catch { return $false }
}

# Accepts the game folder itself or any folder inside it (QueensDomain, Content, Paks, Binaries ...).
function Resolve-GameDir([string]$dir) {
  try {
    $d = [IO.Path]::GetFullPath($dir)
    while ($d) {
      if (Test-GameDir $d) { return $d.TrimEnd('\') }
      $d = [IO.Path]::GetDirectoryName($d)
    }
  } catch {}
  return $null
}

function Find-GameDir {
  # 0) explicit QDA_GAMEDIR, 1) package placed inside the game folder, 2) Steam libraries (registry +
  # libraryfolders.vdf), 3) common folders on every drive, 4) ask the user to pick the folder.
  if ($env:QDA_GAMEDIR) { return (Resolve-GameDir $env:QDA_GAMEDIR) }
  $candidates = New-Object System.Collections.Generic.List[string]
  $candidates.Add($PackageRoot)
  $steamRoots = @()
  foreach ($k in 'HKCU:\Software\Valve\Steam', 'HKLM:\SOFTWARE\WOW6432Node\Valve\Steam', 'HKLM:\SOFTWARE\Valve\Steam') {
    try { $p = (Get-ItemProperty -Path $k -ErrorAction Stop); if ($p.SteamPath) { $steamRoots += ($p.SteamPath -replace '/', '\') }; if ($p.InstallPath) { $steamRoots += $p.InstallPath } } catch {}
  }
  if (${env:ProgramFiles(x86)}) { $steamRoots += "${env:ProgramFiles(x86)}\Steam" }
  $drives = @()
  try { $drives = [IO.DriveInfo]::GetDrives() | Where-Object { $_.IsReady -and $_.DriveType -in 'Fixed', 'Removable' } | ForEach-Object { $_.RootDirectory.FullName } } catch {}
  foreach ($root in ($steamRoots | Select-Object -Unique)) {
    $libs = @($root)
    try {
      $vdf = [IO.Path]::Combine($root, 'steamapps\libraryfolders.vdf')
      if ([IO.File]::Exists($vdf)) {
        foreach ($m in [regex]::Matches([IO.File]::ReadAllText($vdf), '"path"\s+"([^"]+)"')) { $libs += ($m.Groups[1].Value -replace '\\\\', '\') }
      }
    } catch {}
    foreach ($lib in $libs) { try { $candidates.Add([IO.Path]::Combine($lib, 'steamapps\common\QueensDomain')) } catch {} }
  }
  foreach ($drv in $drives) {
    foreach ($rel in 'SteamLibrary', 'Steam', 'Games\Steam', 'Games\SteamLibrary', 'Program Files (x86)\Steam', 'Program Files\Steam') {
      $candidates.Add([IO.Path]::Combine($drv, $rel, 'steamapps\common\QueensDomain'))
    }
    foreach ($rel in 'QueensDomain', 'Games\QueensDomain', "Games\Queen's Domain") { $candidates.Add([IO.Path]::Combine($drv, $rel)) }
  }
  foreach ($c in $candidates) { $r = Resolve-GameDir $c; if ($r) { return $r } }
  if ($env:QDA_SILENT -eq '1') { return $null }
  while ($true) {
    $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
    $dlg.Description = 'لم يُعثر على اللعبة تلقائيًا. اختر مجلد اللعبة Queen''s Domain (المجلد الذي يحتوي QueensDomain.exe)'
    $dlg.ShowNewFolderButton = $false
    if ($dlg.ShowDialog() -ne 'OK') { return $null }
    $r = Resolve-GameDir $dlg.SelectedPath
    if ($r) { return $r }
    Show-Msg ("المجلد المختار لا يحتوي ملفات Queen's Domain:`n$($dlg.SelectedPath)`n`n" +
              'اختر المجلد الذي يحتوي QueensDomain.exe (في Steam: كليك يمين على اللعبة ← إدارة ← تصفح الملفات المحلية).') 'تعريب Queen''s Domain' 'Warning'
  }
}
