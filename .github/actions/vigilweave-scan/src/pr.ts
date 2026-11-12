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

interface OctokitLike {
  rest: {
    issues: {
      listComments: (args: { owner: string; repo: string; issue_number: number }) => Promise<{ data: Array<{ id: number; body?: string }> }>
      updateComment: (args: { owner: string; repo: string; comment_id: number; body: string }) => Promise<unknown>
      createComment: (args: { owner: string; repo: string; issue_number: number; body: string }) => Promise<unknown>
    }
  }
}

export async function upsertGitHubPrComment(options: {
  octokit: OctokitLike
  owner: string
  repo: string
  prNumber: number
  body: string
}): Promise<void> {
  const { octokit, owner, repo, prNumber, body } = options
  const { data: comments } = await octokit.rest.issues.listComments({
    owner,
    repo,
    issue_number: prNumber,
  })

  const existing = comments.find((c) => c.body?.includes(MARKER))
  if (existing) {
    await octokit.rest.issues.updateComment({ owner, repo, comment_id: existing.id, body })
  } else {
    await octokit.rest.issues.createComment({ owner, repo, issue_number: prNumber, body })
  }
}
