import type { IdeFile, IdeScanResponse } from './types'

export async function analyzeSnapshot(options: {
  serverUrl: string
  apiKey: string
  tenant: string
  scanType: 'fast' | 'comprehensive'
  includeQualityMetrics: boolean
  persistScan: boolean
  repo?: string
  files: IdeFile[]
}): Promise<IdeScanResponse> {
  const response = await fetch(new URL('/api/v1/ide/analyze', options.serverUrl), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${options.apiKey}`,
      'X-VigilWeave-Tenant': options.tenant,
    },
    body: JSON.stringify({
      repo: options.repo,
      scan_type: options.scanType,
      include_quality_metrics: options.includeQualityMetrics,
      persist_scan: options.persistScan,
      files: options.files,
    }),
  })

  if (!response.ok) {
    throw new Error(`VigilWeave IDE analysis failed (${response.status} ${response.statusText})`)
  }

  return (await response.json()) as IdeScanResponse
}
