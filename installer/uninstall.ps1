# Removes the Arabic patch pak and, if it was applied, reverts the exe patch (verified by SHA-256; falls back to
# the backup copy). Settings and saves are left untouched.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')

try {
  Write-Log "=== إزالة التعريب ==="
  $game = Find-GameDir
  if (-not $game) { throw 'لم يُعثر على مجلد اللعبة.' }
  if (Get-Process -Name 'QueensDomain-Win64-Shipping', 'QueensDomain' -ErrorAction SilentlyContinue) {
    throw 'اللعبة تعمل الآن. أغلق اللعبة ثم شغّل الإزالة مرة أخرى.'
  }
  $exe = Join-Path $game $ExeRel
  $exeHash = (Get-FileHash -Algorithm SHA256 $exe).Hash
  if ($exeHash -eq $ExePatchedHash) {
    try { Set-ExePatch $exe $false }
    catch {
      $exeBak = Join-Path $LogDir 'backup\QueensDomain-Win64-Shipping.exe.orig'
      if (-not ((Test-Path $exeBak) -and (Get-FileHash -Algorithm SHA256 $exeBak).Hash -eq $ExeOrigHash)) { throw }
      Copy-Item $exeBak $exe -Force
      if ((Get-FileHash -Algorithm SHA256 $exe).Hash -ne $ExeOrigHash) { throw 'فشل استعادة الملف التنفيذي الأصلي.' }
    }
    Write-Log 'أُعيد الملف التنفيذي إلى أصله.'
  }
  $dest = Join-Path $game "QueensDomain\Content\Paks\$PatchName"
  if (-not (Test-Path $dest)) {
    Write-Log 'التعريب غير مثبت؛ لا شيء لإزالته.'
    Show-Msg 'التعريب غير مثبت في هذا المجلد.'
    exit 0
  }
  Remove-Item $dest -Force
  Remove-Item (Join-Path $LogDir 'installed.txt') -Force -ErrorAction SilentlyContinue
  Write-Log "أُزيل: $dest"
  Show-Msg ("تمت إزالة التعريب وأُعيدت ملفات اللعبة إلى أصلها. ملفات الحفظ لم تُمس.`n`n" +
            'إن ظهرت اللعبة بالإنجليزية فهذا طبيعي؛ يمكنك اختيار اللغة من الخيارات.')
}
catch {
  Write-Log "خطأ: $($_.Exception.Message)"
  Show-Msg ("تعذّرت الإزالة:`n`n$($_.Exception.Message)`n`nسجل العملية: $LogFile") 'تعريب Queen''s Domain - خطأ' 'Error'
  exit 1
}
