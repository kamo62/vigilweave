import type { FindingStats, ScanResponse } from './types'

const MARKER = '<!-- vigilweave-summary -->'

export function buildPrComment(scan: ScanResponse, stats: FindingStats, vigilweaveUrl: string): string {
  const lines = [
    MARKER,
    '## VigilWeave Scan Summary',
    '',
    `- Scan ID: ${scan.id}`,
    `- Repository: ${scan.repo}`,
    `- Status: ${scan.status}`,
    `- Type: ${scan.scan_type}`,
    `- Findings: ${stats.total_findings}`,
    '',
    '| Severity | Count |',
    '| --- | ---: |',
    `| Critical | ${stats.critical_findings} |`,
    `| High | ${stats.high_findings} |`,
    `| Medium | ${stats.medium_findings} |`,
    `| Low | ${stats.low_findings} |`,
    `| Info | ${stats.info_findings} |`,
    '',
    `[Open scan in VigilWeave](${new URL(`/scans/${scan.id}`, vigilweaveUrl).toString()})`,
  ]
  return lines.join('\n')
}

export async function upsertPullRequestComment(options: {
  organizationUrl: string
  project: string
  repositoryId: string
  pullRequestId: string
  accessToken: string
  body: string
}): Promise<void> {
  const threadUrl = `${options.organizationUrl}/${options.project}/_apis/git/repositories/${options.repositoryId}/pullRequests/${options.pullRequestId}/threads?api-version=7.1`
  const headers = {
    Authorization: `Bearer ${options.accessToken}`,
    'Content-Type': 'application/json',
  }

  const existingResponse = await fetch(threadUrl, { headers })
  if (!existingResponse.ok) {
    throw new Error(`Failed to list PR threads (${existingResponse.status})`)
  }
  const existing = (await existingResponse.json()) as {
    value?: Array<{ id: number; comments?: Array<{ content?: string }> }>
  }
  const thread = existing.value?.find((item) =>
    item.comments?.some((comment) => comment.content?.includes(MARKER)),
  )

  const payload = {
    comments: [{ content: options.body, commentType: 1 }],
    status: 1,
  }

  if (thread) {
    const updateUrl = `${threadUrl}/${thread.id}?api-version=7.1`
    const response = await fetch(updateUrl, {
      method: 'PATCH',
      headers,
      body: JSON.stringify(payload),
    })
    if (!response.ok) {
      throw new Error(`Failed to update PR comment (${response.status})`)
    }
    return
  }

  const response = await fetch(threadUrl, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    throw new Error(`Failed to create PR comment (${response.status})`)
  }
}
