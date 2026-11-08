"""Create independently installable, audited GitHub release assets."""
import hashlib,json,zipfile
from io import BytesIO
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(data):return hashlib.sha256(data).hexdigest().upper()
def check(name,data):
    assert Path(name).suffix.lower() not in {'.exe','.dll','.sav','.bin','.zip','.rar','.7z','.tar','.gz','.cab'},name
    assert not zipfile.is_zipfile(BytesIO(data)),name
    assert not data.startswith((b'7z\xbc\xaf\x27\x1c',b'Rar!\x1a\x07',b'\x1f\x8b',b'MSCF')),name
def pack(target,entries):
    for n,d in entries.items():check(n,d)
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for n,d in sorted(entries.items()):
            info=zipfile.ZipInfo(n,(2026,11,8,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,d,compresslevel=9)
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        assert set(z.namelist())==set(entries)
        for n in z.namelist():assert z.read(n)==entries[n]
    return {'file':target.name,'sha256':sha(target.read_bytes()),'bytes':target.stat().st_size,
            'files':sorted(entries),'crc':'PASS','content_equality':'PASS','nested_archives':0}
def main():
    version=json.loads((ROOT/'VERSION.json').read_text())['version']
    manifest=json.loads((ROOT/'docs/release-manifest.json').read_text(encoding='utf8'))
    for n,info in manifest['pak_files'].items():assert sha((ROOT/n).read_bytes())==info['sha256'],n
    common={n:(ROOT/n).read_bytes() for n in ['docs/INSTALL_AR.md','docs/INSTALL_EN.md','CHANGELOG.md',
            'THIRD_PARTY_NOTICES.md','LICENSES/OFL-NotoNaskhArabicUI.txt',
            'docs/VALIDATION.md','docs/release-manifest.json']}
    full=dict(common)
    for n in ['install.bat','uninstall.bat','installer/common.ps1','installer/install.ps1','installer/uninstall.ps1',
              'files/exe_patch.json','files/zz_QueensDomain_Arabic_P.pak','files/fade/zz_QueensDomain_Arabic_P.pak']:
        full[n]=(ROOT/n).read_bytes()
    full['README.md']='''<div dir="rtl">

# تعريب Queen's Domain — النسخة الكاملة

**MIZO & ABDULAZIZ — 1.3.2**

أغلق اللعبة، وفك الضغط، ثم شغّل <bdi>install.bat</bdi>. عند توافق EXE يمكنك اختيار الظهور التدريجي من اليمين إلى اليسار. الملف غير المتوافق يبقى دون تعديل وتُثبّت نسخة العرض الكامل تلقائيًا.

شغّل اللعبة واختر العربية من خيارات اللغة. للإزالة شغّل <bdi>uninstall.bat</bdi>. لا تعدّل الحزمة ملفات الحفظ. قبول التثبيت دون قيد إصدار لا يضمن التوافق مع تحديثات اللعبة المستقبلية.

[التثبيت وحل المشكلات](docs/INSTALL_AR.md) · [English](docs/INSTALL_EN.md) · [الحقوق](THIRD_PARTY_NOTICES.md)

</div>
'''.encode('utf8')
    manual=dict(common)
    manual['zz_QueensDomain_Arabic_P.pak']=(ROOT/'files/fade/zz_QueensDomain_Arabic_P.pak').read_bytes()
    manual['README.md']='''<div dir="rtl">

# تعريب Queen's Domain — النسخة اليدوية

**MIZO & ABDULAZIZ — 1.3.2**

أغلق اللعبة وفك الضغط، ثم انسخ <bdi>zz_QueensDomain_Arabic_P.pak</bdi> إلى <bdi>QueensDomain/Content/Paks</bdi> داخل مجلد تثبيت اللعبة. اختر العربية من خيارات اللغة.

هذه النسخة لا تعدّل EXE؛ يظهر الحوار كاملًا مع تلاشي، دون ظهور الحروف التدريجي. إذا سبق أن فعّلت تعديل EXE، استخدم المثبّت الكامل واختر «لا» لاستعادته قبل الانتقال لهذه النسخة.

للإزالة احذف ملف التعريب فقط، ولا تحذف PAK اللعبة الأصلي. لا تثبّت نسختين من التعريب معًا. اختُبر العرض على اللعبة 1.01.03؛ لا نضمن توافق التحديثات الأخرى.

[التثبيت وحل المشكلات](docs/INSTALL_AR.md) · [English](docs/INSTALL_EN.md) · [الحقوق](THIRD_PARTY_NOTICES.md)

</div>
'''.encode('utf8')
    out=ROOT/'dist';out.mkdir(exist_ok=True)
    reports=[pack(out/f'QueensDomain-Arabic-v{version}-Full-Installer.zip',full),
             pack(out/f'QueensDomain-Arabic-v{version}-Manual-PAK.zip',manual)]
    (out/'SHA256SUMS.txt').write_text(''.join(r['sha256']+'  '+r['file']+'\n' for r in reports),encoding='ascii')
    (out/'PACKAGING-CHECK.json').write_text(json.dumps({'version':version,'archives':reports},indent=2),encoding='utf8')
    print(json.dumps(reports,indent=2))
if __name__=='__main__':main()
