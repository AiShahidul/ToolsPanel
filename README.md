# Tools Panel

Small GTK4 / Adwaita control panel for Linux desktop tools.

- Red **Stopped** / **Run** → start
- Green **Running** → stop
- One-shot actions for IVAC Restart Bot / Panel / Browser Auto Arrange
- Paths auto-detect laptop (`Github All Repositories`) vs desktop (`GitHub Repository`)
- Per-tool logs under `~/.cache/tools-panel/`

## Tools

| Tool | Kind |
|------|------|
| PDF Folder Mapper (`:5057`) | daemon |
| PDF Server Upload (`:5058`) | daemon |
| Folder MAP Rename (`:5059`) | daemon |
| IVAC Open Solver | daemon |
| IVAC Restart Bot | one-shot |
| IVAC Restart Panel | one-shot |
| Browser Auto Arrange | one-shot |

## Run

```bash
python3 tools_panel.py
```

Or use the desktop launcher **Tools Panel**.

Requires: `python3-gi`, GTK 4, libadwaita.
