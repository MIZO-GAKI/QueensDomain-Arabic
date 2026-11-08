# Installs the Arabic PAK on any game version, backs up any previous patch and,
# only if the user agrees, applies the small right-to-left reveal patch to the game exe (backed up first).
# Save files are never touched.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')

try {
  Write-Log "=== تثبيت التعريب الإصدار $PatchVersion ==="
  $game = Find-GameDir
  if (-not $game) { throw 'لم يُعثر على مجلد اللعبة. تأكد من تثبيت Queen''s Domain ثم أعد المحاولة.' }
  Write-Log "مجلد اللعبة: $game"

  if (Get-Process -Name 'QueensDomain-Win64-Shipping', 'QueensDomain' -ErrorAction SilentlyContinue) {
    throw 'اللعبة تعمل الآن. أغلق اللعبة ثم شغّل التثبيت مرة أخرى.'
  }

  $versionFile = Join-Path $game 'version.txt'
  $ver = if (Test-Path -LiteralPath $versionFile -PathType Leaf) {
    Get-Content -LiteralPath $versionFile | Select-Object -First 1
  } else { '(not supplied)' }
  Write-Log "رقم البناء (للمعلومات فقط): $ver"

  $exe = Join-Path $game $ExeRel
  if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "ملف تشغيل اللعبة مفقود: $exe"
  }
  $exeHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $exe).Hash
  Write-Log "$ExeRel  $exeHash"
  $exeCompatible = $exeHash -eq $ExeOrigHash -or $exeHash -eq $ExePatchedHash
  $useExe = $false
  if ($exeCompatible) {
    $useExe = Ask-YesNo ("هل تريد تفعيل ظهور النص حرفًا حرفًا من اليمين إلى اليسار في الحوارات والمشاهد؟`n`n" +
                         "نعم: يُعدَّل الملف التنفيذي للعبة تعديلًا صغيرًا (تُحفظ نسخة احتياطية، والإزالة تعيده كما كان).`n" +
                         'لا: يظهر نص الحوار كاملًا دفعة واحدة مع تلاشٍ لطيف، ويُستعاد تعديلنا السابق إن كان مفعّلًا.')
  } else {
    Write-Log 'هذا الملف التنفيذي غير مشمول بتعديل ظهور الحروف. سيُثبّت تعريب PAK تلقائيًا دون تغيير EXE.'
  }
  if ($useExe) {
    if ($exeHash -eq $ExeOrigHash) {
      $exeBak = Join-Path $LogDir 'backup\QueensDomain-Win64-Shipping.exe.orig'
      New-Item -ItemType Directory -Force -Path (Split-Path $exeBak) | Out-Null
      if (-not ((Test-Path $exeBak) -and (Get-FileHash -Algorithm SHA256 $exeBak).Hash -eq $ExeOrigHash)) {
        Copy-Item $exe $exeBak -Force
        if ((Get-FileHash -Algorithm SHA256 $exeBak).Hash -ne $ExeOrigHash) { throw 'فشل إنشاء النسخة الاحتياطية للملف التنفيذي.' }
        Write-Log "نسخة احتياطية من الملف التنفيذي الأصلي: $exeBak"
      }
      Set-ExePatch $exe $true
      Write-Log 'عُدّل الملف التنفيذي (ظهور النص من اليمين إلى اليسار).'
    } else { Write-Log 'الملف التنفيذي معدّل مسبقًا بهذا التعريب.' }
    $src = Join-Path $PackageRoot "files\$PatchName"
  } else {
    if ($exeHash -eq $ExePatchedHash) { Set-ExePatch $exe $false; Write-Log 'أُعيد الملف التنفيذي إلى أصله.' }
    $src = Join-Path $PackageRoot "files\fade\$PatchName"
  }

  $paks = Join-Path $game 'QueensDomain\Content\Paks'
  $dest = Join-Path $paks $PatchName
  if (-not (Test-Path $src)) { throw "ملف التعريب مفقود من الحزمة: $src" }
  if (Test-Path $dest) {
    $bak = Join-Path $LogDir ("backup\{0}_{1}" -f (Get-Date -Format 'yyyyMMdd_HHmmss'), $PatchName)
    New-Item -ItemType Directory -Force -Path (Split-Path $bak) | Out-Null
    Copy-Item $dest $bak -Force
    Write-Log "وُجدت نسخة سابقة من التعريب، نُسخت احتياطيًا إلى: $bak"
  }
  Copy-Item $src $dest -Force
  if ((Get-FileHash $dest).Hash -ne (Get-FileHash $src).Hash) { throw 'فشل التحقق من الملف بعد النسخ.' }
  Set-Content -Path (Join-Path $LogDir 'installed.txt') -Value @("game=$game", "file=$dest", "version=$PatchVersion", "sha256=$((Get-FileHash $dest).Hash)", "exepatch=$useExe") -Encoding UTF8
  Write-Log "تم التثبيت: $dest"
  $modeInfo = if (-not $exeCompatible) {
    "ثُبّتت نسخة PAK دون تعديل EXE؛ يظهر الحوار كاملًا مع تلاشٍ لطيف.`n`n"
  } else { '' }
  Show-Msg ("تم تثبيت التعريب بنجاح.`n`n" + $modeInfo +
            "شغّل اللعبة، ثم من: الخيارات ← اللغة، اختر «العربية».`n" +
            "(في أول تشغيل تظهر شاشة اختيار اللغة مباشرة.)`n`n" +
            'تعريب: MIZO و ABDULAZIZ')
}
catch {
  $msg = $_.Exception.Message
  if ($_.Exception -is [System.UnauthorizedAccessException]) {
    $msg = 'لا توجد صلاحية للكتابة في مجلد اللعبة. شغّل install.bat بالنقر بزر الفأرة الأيمن ثم «تشغيل كمسؤول».'
  }
  Write-Log "خطأ: $msg"
  Show-Msg ("تعذّر التثبيت:`n`n$msg`n`nسجل العملية: $LogFile") 'تعريب Queen''s Domain - خطأ' 'Error'
  exit 1
}
