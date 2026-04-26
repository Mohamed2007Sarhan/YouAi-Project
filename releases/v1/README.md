# YouAI Release v1

This folder contains the first release pipeline for YouAI.

## Structure

- `build/` : build scripts and installer definition.
- `package/` : final setup output (`YouAI_v1_Setup.exe`).

## Build EXE

From project root or this folder:

```powershell
powershell -ExecutionPolicy Bypass -File "releases\v1\build\build_exe.ps1" -Clean
```

Output:

- `releases\v1\build\dist\YouAI\YouAI.exe`

## Build Setup Installer

Requires Inno Setup 6 installed.

```powershell
powershell -ExecutionPolicy Bypass -File "releases\v1\build\build_setup.ps1" -BuildExeFirst
```

Output:

- `releases\v1\package\YouAI_v1_Setup.exe`

## Installer behavior

- Opens a setup wizard.
- Default install directory: `C:\ProgramData\YouAI`.
- User can change installation directory from setup UI.
- Creates Start Menu shortcut.
- Optional Desktop shortcut task included.
