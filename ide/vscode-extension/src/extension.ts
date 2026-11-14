import * as vscode from 'vscode'

import { analyzeSnapshot } from './client'
import { toDiagnostics } from './diagnostics'
import { collectChangedFiles, collectCurrentFile, collectWorkspaceFiles } from './files'
import { assertTrustedWorkspace, readBoundApiKey, serviceOrigin } from './security'

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
      try {
        const origin = serviceOrigin(getConfig().serverUrl)
        await context.secrets.store(SECRET_KEY, JSON.stringify({ apiKey, origin }))
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error)
        vscode.window.showErrorMessage(message)
        return
      }
      vscode.window.showInformationMessage('VigilWeave API key stored securely.')
    }),
  )

  context.subscriptions.push(
    vscode.commands.registerCommand('vigilweave.scanWorkspace', async () => {
      if (!requireTrustedWorkspace()) return
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
      if (!requireTrustedWorkspace()) return
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
      if (!requireTrustedWorkspace()) return
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
  if (!requireTrustedWorkspace()) return
  if (!options.files.length) {
    vscode.window.showInformationMessage('No supported files found for VigilWeave analysis.')
    return
  }

  const storedApiKey = await options.context.secrets.get(SECRET_KEY)
  if (!storedApiKey) {
    vscode.window.showWarningMessage('Set a VigilWeave API key before scanning.')
    return
  }

  const config = getConfig()
  let apiKey: string
  try {
    if (config.dashboardUrl) serviceOrigin(config.dashboardUrl)
    apiKey = readBoundApiKey(storedApiKey, config.serverUrl)
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    vscode.window.showWarningMessage(message)
    return
  }
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
    serverUrl: getMachineSetting(config, 'serverUrl', 'http://localhost:8000'),
    tenant: config.get<string>('tenant', 'default'),
    dashboardUrl: getMachineSetting(config, 'dashboardUrl', 'http://localhost:5173'),
    persistWorkspaceScans: config.get<boolean>('persistWorkspaceScans', true),
    includeQualityMetrics: config.get<boolean>('includeQualityMetrics', true),
  }
}

function getMachineSetting<T>(
  config: vscode.WorkspaceConfiguration,
  key: string,
  fallback: T,
): T {
  const inspected = config.inspect<T>(key)
  return inspected?.globalValue ?? inspected?.defaultValue ?? fallback
}

function requireTrustedWorkspace(): boolean {
  try {
    assertTrustedWorkspace(vscode.workspace.isTrusted)
    return true
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    vscode.window.showWarningMessage(message)
    return false
  }
}
