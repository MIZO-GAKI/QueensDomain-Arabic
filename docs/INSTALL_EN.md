# Installation — v1.3.2

Download **one** package from [Releases](https://github.com/MIZO-GAKI/QueensDomain-Arabic/releases/tag/v1.3.2).

## Full installer

1. Close the game and extract `QueensDomain-Arabic-v1.3.2-Full-Installer.zip` into a normal folder.
2. Keep `install.bat`, `installer/` and `files/` together. Run `install.bat`.
3. The installer searches Steam libraries/common locations; select the game directory if asked.
4. For a known compatible EXE, choose whether to enable progressive Arabic right-to-left character reveal. This optional 108-byte patch is verified by exact hashes and backed up before application.
5. An unknown EXE automatically receives the fade PAK without EXE changes. Choosing No also reverts our known previous EXE patch.
6. Launch the game and select Arabic (العربية) under Options → Language.

## Manual PAK

Extract `QueensDomain-Arabic-v1.3.2-Manual-PAK.zip`. Copy `zz_QueensDomain_Arabic_P.pak` into:

```text
<game installation>/QueensDomain/Content/Paks/
```

Steam → right-click game → Manage → Browse local files locates the installation.
This package does not run scripts or alter the EXE. Dialogue appears as a complete
block with a fade; progressive RTL reveal is unavailable. If our EXE patch was
previously enabled, run the full installer and choose No before switching.

## Update, remove, restore

Close the game before making changes. Run the new installer or replace the existing
mod PAK with the same filename. Do not keep renamed old mod PAKs alongside it.

Full uninstall: run `uninstall.bat`; it removes our PAK and reverts the exact known
patched EXE. An EXE changed by a game update is left untouched. Manual uninstall:
delete **only** `zz_QueensDomain_Arabic_P.pak`, never the original game PAK.

Previous PAKs and the known original EXE backup are stored under
`%LOCALAPPDATA%/QueensDomainArabic/backup/`; the log is `install.log` in the parent
directory. Restore a previous PAK under its original mod filename if needed. Use
the installer to revert the EXE rather than copying an old executable over a game
update. Steam's file verification can restore original game files if necessary.
The installer/uninstaller does not edit saves or game settings.

## Compatibility and troubleshooting

Windows 64-bit, existing game directory structure. PAK installation has no build
number/original-PAK hash restriction and does not require `version.txt`. Runtime
testing used Steam build 13480, game 1.01.03, UE 4.27.2. Future/other game builds
may change UI resources; installation acceptance does not certify compatibility.
The optional EXE patch requires exact known hashes, not merely the version label.

If Arabic is missing, check extraction, filename, the actual installation being
launched, and the PAK location, then restart the game. For installer errors, close
the game and check the complete package and log. Only use administrator elevation
for an actual write-permission error. Never disable security software or force the
EXE patch onto an unknown executable.

Report UI issues with game/mod versions, installation method, resolution/aspect
ratio, reproduction steps and an optional screenshot. Remove personal paths from
logs; never attach game executables, original PAKs or saves to public issues.

[Arabic guide](INSTALL_AR.md) · [README](../README.md)
