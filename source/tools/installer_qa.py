"""Exercise real installer/uninstaller scripts in disposable game directories.

Optional argument: a known patched EXE, copied only to fixtures and never shipped.
No game executable is launched; user settings/saves/install logs are not touched.
"""
import hashlib,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PATCH='zz_QueensDomain_Arabic_P.pak'
EXE='QueensDomain/Binaries/Win64/QueensDomain-Win64-Shipping.exe'
PAKS='QueensDomain/Content/Paks'
ORIG='8D805CFF01753F9066BF60E4432A02D91533E4741AC0EAF1649B3C1CD17EE9CF'
PATCHED='D3FD3846E99EEED520CD71BA71F50C45760DA73FA4192EFE07AB08B6C791A417'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest().upper()
def main():
 work=Path(tempfile.mkdtemp(prefix='installer132-',dir=ROOT/'source/work'))
 package=work/'package';package.mkdir()
 shutil.copytree(ROOT/'installer',package/'installer')
 shutil.copytree(ROOT/'files',package/'files')
 game=work/'game';(game/PAKS).mkdir(parents=True);(game/EXE).parent.mkdir(parents=True)
 base=game/PAKS/'QueensDomain-WindowsNoEditor.pak';base.write_bytes(b'different game PAK build fixture')
 save=game/'Saved/SaveGames/fixture.sav';save.parent.mkdir(parents=True);save.write_bytes(b'preserve saves')
 exe=game/EXE;dest=game/PAKS/PATCH
 env=os.environ.copy()
 # Launch Windows PowerShell with its own modules, not an inherited PS7 path.
 for key in list(env):
  if key.lower()=='psmodulepath':env.pop(key)
 env.update(QDA_SILENT='1',QDA_GAMEDIR=str(game),LOCALAPPDATA=str(work/'localappdata'))
 cases=[]
 def run(script,want=0,choice='1'):
  env['QDA_EXEPATCH']=choice
  r=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(package/'installer'/script)],env=env,capture_output=True)
  assert r.returncode==want,(script,r.returncode,r.stdout.decode(errors='replace'),r.stderr.decode(errors='replace'))
  assert base.read_bytes()==b'different game PAK build fixture'
  assert save.read_bytes()==b'preserve saves'
 def case(name):cases.append(dict(name=name,result='PASS'))
 exe.write_bytes(b'unknown executable fixture, never execute')
 unknown=sha(exe);dest.write_bytes(b'old mod fixture')
 run('install.ps1');assert sha(exe)==unknown and sha(dest)==sha(ROOT/'files/fade'/PATCH)
 assert any(p.read_bytes()==b'old mod fixture' for p in (work/'localappdata/QueensDomainArabic/backup').glob('*.pak'))
 case('Unknown EXE and different base PAK, absent version.txt: automatic fade fallback even when EXE requested; previous PAK backed up')
 (game/'version.txt').write_text('999999-new-build')
 run('install.ps1');assert sha(exe)==unknown and sha(dest)==sha(ROOT/'files/fade'/PATCH)
 case('Arbitrary version.txt accepted')
 run('uninstall.ps1');assert not dest.exists() and sha(exe)==unknown
 case('Unknown EXE preserved during uninstall')
 if len(sys.argv)>1:
  source=Path(sys.argv[1]);assert sha(source)==PATCHED
  shutil.copy2(source,exe)
  run('install.ps1',choice='0');assert sha(exe)==ORIG and sha(dest)==sha(ROOT/'files/fade'/PATCH)
  case('Known patched EXE + no: restored original and selected fade')
  run('install.ps1');assert sha(exe)==PATCHED and sha(dest)==sha(ROOT/'files'/PATCH)
  case('Known original EXE + yes: verified backup, patched EXE and standard PAK')
  run('install.ps1');assert sha(exe)==PATCHED and sha(dest)==sha(ROOT/'files'/PATCH)
  case('Already patched EXE: idempotent standard installation')
  run('uninstall.ps1');assert sha(exe)==ORIG and not dest.exists()
  case('Known patched EXE: uninstall restored exact original')
  run('install.ps1');exe.write_bytes(b'game updated after mod installation')
  updated=sha(exe);run('uninstall.ps1');assert sha(exe)==updated and not dest.exists()
  case('Game updated after installation: uninstall does not restore stale EXE backup')
 # A genuine missing-file error must still be caught, independently of version.
 exe.rename(exe.with_suffix('.fixture'))
 run('install.ps1',want=1);assert not dest.exists()
 case('Missing game EXE rejected before installing')
 report=dict(result='PASS',cases=cases,isolated_fixture=str(work),
  scope='Installer behavior with fixture files; no claim of runtime compatibility with untested game builds',
  original_game_pak_and_saves_unchanged=True)
 (ROOT/'source/reports/installer-verification.json').write_text(json.dumps(report,indent=2),encoding='utf8')
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
