# Get the code
git clone --recursive https://github.com/webgfx/toolkit.git

# Work with GN project
cd misc && python3 gnp.py --sync --runhooks --makefile --build --backup --build-target=xxx --root-dir=xxx

## Build Chromium or Edge

`webgfx.py` automatically puts the matching depot_tools checkout and its
`scripts` directory first on `PATH`:

- Chromium (`--root-dir d:\r\cr`): `d:\r\depot_tools_cr`
- Edge (`--root-dir d:\r\edge`): `d:\r\depot_tools_edge`

No separate `set PATH=...` command is required.

Build Chromium with its matching depot_tools checkout:

```powershell
Set-Location d:\r
python3 webgfx.py --target chrome --root-dir d:\r\cr `
	--sync --makefile --build
```

Apply the Edge Git sync performance fix before the first sync and build:

```powershell
Set-Location d:\r
python3 webgfx.py --target chrome --root-dir d:\r\edge `
	--edge-sync-fix apply --sync --makefile --build
```

Later builds can omit `--edge-sync-fix apply`; an explicit repeat is also safe
and does not create another backup when the fix is already active.

Restore the latest pre-fix local configuration and remote-tracking refs:

```powershell
Set-Location d:\r
python3 webgfx.py --root-dir d:\r\edge --edge-sync-fix revert
```

To restore a specific backup:

```powershell
Set-Location d:\r
python3 webgfx.py --root-dir d:\r\edge --edge-sync-fix revert `
	--edge-sync-fix-backup d:\r\edge\src\.git\edge-sync-analysis\backups\<timestamp>
```

The Edge fix changes only repository-local Git configuration and local
`origin/*` refs. It does not fetch, modify local branches or tags, alter global
Git configuration, or change server-side refs. Apply creates a complete backup
before changing anything and rolls back automatically on failure. Revert
validates the selected backup first, creates an additional pre-revert safety
snapshot, and also rolls back automatically if restoration fails.

# TODO
bisect mesa, webmark, angle, aosp, chromeos, dawn, skia, v8
how to port performance test, how to port webgl-cts
