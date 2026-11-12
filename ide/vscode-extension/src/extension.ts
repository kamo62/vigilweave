import * as vscode from 'vscode'

import { analyzeSnapshot } from './client'
import { toDiagnostics } from './diagnostics'
import { collectChangedFiles, collectCurrentFile, collectWorkspaceFiles } from './files'

const SECRET_KEY = 'vigilweave.apiKey'

export function activate(context: vscode.ExtensionContext): void {
  const diagnostics = vscode.languages.createDiagnosticCollection('vigilweave')
  const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100)
  statusBar.text = 'VigilWeave idle'
  statusBar.show()

  context.subscriptions.push(diagnostics, statusBar)

  context.subscriptions.push(
    vscode.commands.registerCommand('vigilweave.setApiKey', async () => {
      const apiKey = await vscode.window.showInputBox({
        password: true,
        title: 'Store VigilWeave API key',
        placeHolder: 'vw_...',
      })
      if (!apiKey) return
      await context.secrets.store(SECRET_KEY, apiKey)
      vscode.window.showInformationMessage('VigilWeave API key stored securely.')
    }),
  )

  context.subscriptions.push(
    vscode.commands.registerCommand('vigilweave.scanWorkspace', async () => {
      const folder = getWorkspaceFolder()
      if (!folder) return
      const files = await collectWorkspaceFiles(folder)
      await runScan({
        context,
        diagnostics,
        statusBar,
        files,
        persistScan: getConfig().persistWorkspaceScans,
        repo: folder.uri.fsPath,
      })
    }),
  )

  context.subscriptions.push(
    vscode.commands.registerCommand('vigilweave.scanCurrentFile', async () => {
      const editor = vscode.window.activeTextEditor
      if (!editor) {
        vscode.window.showWarningMessage('Open a file before running VigilWeave.')
        return
      }
      await runScan({
        context,
        diagnostics,
        statusBar,
        files: await collectCurrentFile(editor),
        persistScan: false,
      })
    }),
  )

  context.subscriptions.push(
    vscode.commands.registerCommand('vigilweave.scanChangedFiles', async () => {
      const folder = getWorkspaceFolder()
      if (!folder) return
      const files = await collectChangedFiles(folder)
      await runScan({
        context,
        diagnostics,
        statusBar,
        files,
        persistScan: false,
        repo: folder.uri.fsPath,
      })
    }),
  )
}

export function deactivate(): void {}

async function runScan(options: {
  context: vscode.ExtensionContext
  diagnostics: vscode.DiagnosticCollection
  statusBar: vscode.StatusBarItem
  files: Array<{ path: string; content: string }>
  persistScan: boolean
  repo?: string
}): Promise<void> {
  if (!options.files.length) {
    vscode.window.showInformationMessage('No supported files found for VigilWeave analysis.')
    return
  }

  const apiKey = await options.context.secrets.get(SECRET_KEY)
  if (!apiKey) {
    vscode.window.showWarningMessage('Set a VigilWeave API key before scanning.')
    return
  }

  const config = getConfig()
  options.statusBar.text = 'VigilWeave scanning...'

  try {
    const response = await analyzeSnapshot({
      serverUrl: config.serverUrl,
      apiKey,
      tenant: config.tenant,
      scanType: options.persistScan ? 'comprehensive' : 'fast',
      includeQualityMetrics: config.includeQualityMetrics,
      persistScan: options.persistScan,
      repo: options.repo,
      files: options.files,
    })

    options.diagnostics.clear()
    const grouped = toDiagnostics(
      response.findings,
      config.dashboardUrl,
      response.scan?.id ?? null,
    )
    for (const [relativePath, items] of grouped.entries()) {
      const target = vscode.Uri.joinPath(getWorkspaceFolder()?.uri ?? vscode.Uri.file('/'), relativePath)
      options.diagnostics.set(target, items)
    }

    options.statusBar.text = `VigilWeave ${response.findings.length} findings`
    vscode.window.showInformationMessage(
      `VigilWeave completed with ${response.findings.length} findings.`,
    )
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    options.statusBar.text = 'VigilWeave failed'
    vscode.window.showErrorMessage(message)
  }
}

function getWorkspaceFolder(): vscode.WorkspaceFolder | undefined {
  return vscode.workspace.workspaceFolders?.[0]
}

function getConfig() {
  const config = vscode.workspace.getConfiguration('vigilweave')
  return {
    serverUrl: config.get<string>('serverUrl', 'http://localhost:8000'),
    tenant: config.get<string>('tenant', 'default'),
    dashboardUrl: config.get<string>('dashboardUrl', ''),
    persistWorkspaceScans: config.get<boolean>('persistWorkspaceScans', true),
    includeQualityMetrics: config.get<boolean>('includeQualityMetrics', true),
  }
}
