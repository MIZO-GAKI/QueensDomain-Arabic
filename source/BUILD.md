# Build and audit

The repository contains the Arabic source strings, inventory, layout/build tools,
installer scripts and OFL-licensed Arabic font. Compiled PAKs are Release assets,
not committed binaries. A locally installed, legitimate copy of the game is required.
The cooked property layouts are engineered against **game 1.01.03 / UE 4.27.2**;
do not assume that building against any future game PAK is safe.

## Requirements

Python 3.11+ (standard library only), the original game PAK, and Windows PowerShell
for installer integration tests. The game/editor/UnrealPak/EXE are not distributed.

From the repository root in PowerShell:

```powershell
$gamePak = 'C:/path/to/game/QueensDomain/Content/Paks/QueensDomain-WindowsNoEditor.pak'
$env:PRINT_SPEED = '0'
py -I source/tools/build.py $gamePak files/zz_QueensDomain_Arabic_P.pak
Remove-Item Env:PRINT_SPEED
py -I source/tools/build.py $gamePak files/fade/zz_QueensDomain_Arabic_P.pak
py -I source/tools/qa.py --original-pak $gamePak
py -I source/tools/package_release.py
```

Standard PAK preserves the progressive renderer and is paired with the optional
known-hash EXE patch. Fade PAK sets the existing text reveal speed to a near-instant
value so full blocks appear with the original fade, without EXE patching.

`ar-MA` deliberately preserves Western number formatting used by the game's save
filenames. Translation JSON remains logical Unicode; animated text's shaping and
visual reordering are display-only transforms. Native text uses native shaping.
`rtl_layout.py` performs selected culture-aware row changes, not global mirroring.
The only added display string is the user-approved main-menu signature; original
2,382 translation entries stay intact.

The build reads the Latin font from the user's game into an ignored working file.
Never commit that extracted file, original game packages, saves or EXEs.

## Checks and packaging

`qa.py` verifies translation coverage, placeholders/newline parity and Arabic glyph
coverage. `ui_audit.py` can inspect the caller's original packages. Use an existing
UnrealPak installation with `<pak> -Verify` to check both PAKs if available.

`installer_qa.py` runs the real scripts in disposable fixtures under `source/work`.
Close the game first. Its optional argument is a locally available known patched
EXE to exercise apply/revert cases; this file is never launched or distributed.
Without it, only unknown-version/error cases are tested.

Historical exact-delta gates depended on private frozen comparison PAKs. Those old
builds and machine-specific logs are intentionally not published. The public
validation summary distinguishes their recorded results from reproducible checks.

`package_release.py` uses explicit allowlists, verifies the release PAK hashes,
rejects nested archives and executables, checks CRC/content equality and creates
the two standalone ZIPs plus SHA256SUMS.txt under ignored `dist/`. For a future
release, review/update VERSION.json and the manifest deliberately, after testing.
Do not zip the entire repository or include one release ZIP inside another.

The EXE byte diff is in `files/exe_patch.json`; `installer/common.ps1` validates
both original and patched hashes. Unknown EXEs automatically use fade. Never remove
the EXE hash checks to claim broader compatibility.
