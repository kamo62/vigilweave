# VigilWeave VS Code Extension

Commands:

- `VigilWeave: Set API Key`
- `VigilWeave: Scan Workspace`
- `VigilWeave: Scan Current File`
- `VigilWeave: Scan Changed Files`

The extension sends workspace snapshots to `POST /api/v1/ide/analyze`, renders diagnostics in the Problems panel, and can deep-link back to the VigilWeave dashboard when a persisted scan is returned.
