import * as vscode from 'vscode'

import type { IdeFinding } from './types'

export function toDiagnostics(
  findings: IdeFinding[],
  dashboardUrl: string,
  scanId: number | null,
): Map<string, vscode.Diagnostic[]> {
  const grouped = new Map<string, vscode.Diagnostic[]>()

  for (const finding of findings) {
    if (!finding.file_path) continue

    const startLine = Math.max((finding.line ?? 1) - 1, 0)
    const startColumn = Math.max((finding.column ?? 1) - 1, 0)
    const range = new vscode.Range(startLine, startColumn, startLine, startColumn + 1)
    const diagnostic = new vscode.Diagnostic(
      range,
      `${finding.title}: ${finding.message}`,
      toSeverity(finding.severity),
    )
    diagnostic.source = `VigilWeave (${finding.tool})`
    if (scanId && dashboardUrl) {
      diagnostic.code = {
        value: finding.title,
        target: vscode.Uri.parse(`${dashboardUrl.replace(/\/$/, '')}/scans/${scanId}`),
      }
    }

    const bucket = grouped.get(finding.file_path) ?? []
    bucket.push(diagnostic)
    grouped.set(finding.file_path, bucket)
  }

  return grouped
}

function toSeverity(severity: IdeFinding['severity']): vscode.DiagnosticSeverity {
  if (severity === 'Critical' || severity === 'High') return vscode.DiagnosticSeverity.Error
  if (severity === 'Medium') return vscode.DiagnosticSeverity.Warning
  if (severity === 'Low') return vscode.DiagnosticSeverity.Information
  return vscode.DiagnosticSeverity.Hint
}
