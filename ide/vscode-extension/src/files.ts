import * as fs from 'node:fs/promises'
import * as path from 'node:path'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'

import * as vscode from 'vscode'

import type { IdeFile } from './types'

const execFileAsync = promisify(execFile)

const SOURCE_EXTENSIONS = new Set(['.py', '.js', '.jsx', '.ts', '.tsx', '.tf', '.yaml', '.yml'])

export async function collectWorkspaceFiles(folder: vscode.WorkspaceFolder): Promise<IdeFile[]> {
  const uris = await vscode.workspace.findFiles(
    new vscode.RelativePattern(folder, '**/*'),
    '{**/.git/**,**/node_modules/**,**/dist/**,**/coverage/**}',
  )
  return readFiles(folder, uris)
}

export async function collectChangedFiles(folder: vscode.WorkspaceFolder): Promise<IdeFile[]> {
  const { stdout } = await execFileAsync('git', ['diff', '--name-only', 'HEAD'], {
    cwd: folder.uri.fsPath,
  })
  const candidates = stdout
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((relativePath) => vscode.Uri.file(path.join(folder.uri.fsPath, relativePath)))
  return readFiles(folder, candidates)
}

export async function collectCurrentFile(editor: vscode.TextEditor): Promise<IdeFile[]> {
  const relativePath = vscode.workspace.asRelativePath(editor.document.uri, false)
  return [{ path: relativePath, content: editor.document.getText() }]
}

async function readFiles(
  folder: vscode.WorkspaceFolder,
  uris: readonly vscode.Uri[],
): Promise<IdeFile[]> {
  const files: IdeFile[] = []
  for (const uri of uris) {
    if (!(await includeUri(uri))) continue
    const relativePath = path.relative(folder.uri.fsPath, uri.fsPath)
    const content = await fs.readFile(uri.fsPath, 'utf-8')
    files.push({ path: relativePath, content })
  }
  return files
}

async function includeUri(uri: vscode.Uri): Promise<boolean> {
  try {
    const stats = await fs.stat(uri.fsPath)
    if (!stats.isFile()) return false
  } catch {
    return false
  }

  const extension = path.extname(uri.fsPath).toLowerCase()
  return SOURCE_EXTENSIONS.has(extension) || path.basename(uri.fsPath).toLowerCase() === 'dockerfile'
}
