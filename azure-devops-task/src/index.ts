import * as fs from 'node:fs/promises'
import * as path from 'node:path'
import * as task from 'azure-pipelines-task-lib/task'

import { VigilWeaveClient } from './client'
import { evaluateGates } from './gates'
import { buildPrComment, upsertPullRequestComment } from './pr'
import { normalizeStats } from './severity'

async function main(): Promise<void> {
  try {
    const vigilweaveUrl = requiredInput('vigilweaveUrl')
    const apiKey = requiredInput('apiKey')
    const repo = task.getInput('repo', false) || process.env.BUILD_REPOSITORY_URI || ''
    const branch = task.getInput('branch', false) || process.env.BUILD_SOURCEBRANCHNAME || undefined
    const commit = task.getInput('commit', false) || process.env.BUILD_SOURCEVERSION || undefined
    const scanType = (task.getInput('scanType', true) ||
      'comprehensive') as 'comprehensive' | 'fast' | 'security-only' | 'custom'
    const pollIntervalSeconds = Number(task.getInput('pollIntervalSeconds', false) || '10')
    const timeoutSeconds = Number(task.getInput('timeoutSeconds', false) || '900')
    const summaryOutputPath =
      task.getInput('summaryOutputPath', false) ||
      path.join(process.env.BUILD_ARTIFACTSTAGINGDIRECTORY || '.', 'vigilweave-summary.json')
    const sarifOutputPath =
      task.getInput('sarifOutputPath', false) ||
      path.join(
        process.env.BUILD_ARTIFACTSTAGINGDIRECTORY || '.',
        'vigilweave',
        'vigilweave.sarif',
      )
    const publishPrComment = task.getBoolInput('publishPrComment', false)
    const failOnCritical = task.getBoolInput('failOnCritical', false)
    const failOnHigh = task.getBoolInput('failOnHigh', false)

    if (!repo) {
      throw new Error('Repository URL was not provided and Build.Repository.Uri is unavailable.')
    }

    const client = new VigilWeaveClient(vigilweaveUrl, apiKey)
    const created = await client.createScan({
      repo,
      branch,
      commit,
      scan_type: scanType,
      include_quality_metrics: true,
    })

    task.setVariable('VigilWeave.ScanId', String(created.id))
    const scan = await pollForCompletion(client, created.id, pollIntervalSeconds, timeoutSeconds)
    const stats = normalizeStats(await client.getStats(scan.id))
    const sarif = await client.getSarif(scan.id)

    await writeJson(summaryOutputPath, { scan, stats })
    await writeJson(sarifOutputPath, sarif)
    task.setVariable('VigilWeave.SarifPath', sarifOutputPath)
    task.setResult(
      task.TaskResult.Succeeded,
      `VigilWeave scan ${scan.id} completed. SARIF staged for AdvancedSecurity-Publish@1.`,
    )

    if (publishPrComment) {
      await tryPublishPullRequestComment(vigilweaveUrl, scan, stats)
    }

    const gates = evaluateGates(stats, { failOnCritical, failOnHigh })
    if (!gates.passed) {
      task.setResult(task.TaskResult.Failed, gates.reasons.join('; '))
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    task.setResult(task.TaskResult.Failed, message)
  }
}

async function pollForCompletion(
  client: VigilWeaveClient,
  scanId: number,
  pollIntervalSeconds: number,
  timeoutSeconds: number,
) {
  const deadline = Date.now() + timeoutSeconds * 1000
  while (Date.now() < deadline) {
    const scan = await client.getScan(scanId)
    if (scan.status === 'completed' || scan.status === 'failed') {
      return scan
    }
    await new Promise((resolve) => setTimeout(resolve, pollIntervalSeconds * 1000))
  }
  throw new Error(`Timed out waiting for VigilWeave scan ${scanId}`)
}

async function writeJson(outputPath: string, payload: unknown): Promise<void> {
  await fs.mkdir(path.dirname(outputPath), { recursive: true })
  await fs.writeFile(outputPath, JSON.stringify(payload, null, 2), 'utf-8')
}

async function tryPublishPullRequestComment(
  vigilweaveUrl: string,
  scan: Awaited<ReturnType<VigilWeaveClient['getScan']>>,
  stats: Awaited<ReturnType<VigilWeaveClient['getStats']>>,
): Promise<void> {
  const systemAccessToken = process.env.SYSTEM_ACCESSTOKEN
  const pullRequestId = process.env.SYSTEM_PULLREQUEST_PULLREQUESTID
  const repositoryId = process.env.BUILD_REPOSITORY_ID
  const organizationUrl = process.env.SYSTEM_COLLECTIONURI
  const project = process.env.SYSTEM_TEAMPROJECT

  if (!systemAccessToken || !pullRequestId || !repositoryId || !organizationUrl || !project) {
    task.debug('Pull request context is incomplete; skipping PR comment update.')
    return
  }

  await upsertPullRequestComment({
    organizationUrl,
    project,
    repositoryId,
    pullRequestId,
    accessToken: systemAccessToken,
    body: buildPrComment(scan, stats, vigilweaveUrl),
  })
}

function requiredInput(name: string): string {
  const value = task.getInput(name, true)
  if (!value) {
    throw new Error(`Missing required input: ${name}`)
  }
  return value
}

void main()
