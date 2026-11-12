import * as fs from 'node:fs/promises'
import * as path from 'node:path'

import * as core from '@actions/core'
import * as github from '@actions/github'

import { VigilWeaveClient } from './client'
import { evaluateGates } from './gates'
import { buildPrComment, upsertGitHubPrComment } from './pr'

async function main(): Promise<void> {
  try {
    const vigilweaveUrl = core.getInput('vigilweave_url', { required: true })
    const apiKey = core.getInput('api_key', { required: true })
    const repo = core.getInput('repo') || process.env.GITHUB_REPOSITORY || ''
    const branch =
      core.getInput('branch') ||
      process.env.GITHUB_HEAD_REF ||
      process.env.GITHUB_REF_NAME ||
      undefined
    const commit = core.getInput('commit') || process.env.GITHUB_SHA || undefined
    const scanType = (core.getInput('scan_type') || 'comprehensive') as
      | 'comprehensive'
      | 'fast'
      | 'security-only'
      | 'custom'
    const failOnCritical = core.getBooleanInput('fail_on_critical')
    const failOnHigh = core.getBooleanInput('fail_on_high')
    const pollInterval = Number(core.getInput('poll_interval') || '10')
    const timeout = Number(core.getInput('timeout') || '900')
    const githubToken = core.getInput('github_token')

    if (!repo) {
      throw new Error('Repository was not provided and GITHUB_REPOSITORY is unavailable.')
    }

    const client = new VigilWeaveClient(vigilweaveUrl, apiKey)

    // Create scan
    core.info(`Creating ${scanType} scan for ${repo}...`)
    const created = await client.createScan({
      repo,
      branch,
      commit,
      scan_type: scanType,
      include_quality_metrics: true,
    })
    core.setOutput('scan_id', String(created.id))
    core.info(`Scan ${created.id} created. Polling for completion...`)

    // Poll for completion
    const scan = await pollForCompletion(client, created.id, pollInterval, timeout)
    core.info(`Scan ${scan.id} finished with status: ${scan.status}`)

    // Fetch stats and SARIF
    const stats = await client.getStats(scan.id)
    const sarif = await client.getSarif(scan.id)

    // Write SARIF file
    const sarifPath = path.join(process.env.RUNNER_TEMP || '/tmp', 'vigilweave.sarif')
    await fs.mkdir(path.dirname(sarifPath), { recursive: true })
    await fs.writeFile(sarifPath, JSON.stringify(sarif, null, 2), 'utf-8')

    // Set outputs
    core.setOutput('quality_gate_passed', String(scan.quality_gate_passed ?? true))
    core.setOutput('total_findings', String(stats.total_findings))
    core.setOutput('sarif_path', sarifPath)

    // PR comment
    const context = github.context
    if (context.payload.pull_request && githubToken) {
      try {
        const octokit = github.getOctokit(githubToken)
        await upsertGitHubPrComment({
          octokit,
          owner: context.repo.owner,
          repo: context.repo.repo,
          prNumber: context.payload.pull_request.number,
          body: buildPrComment(scan, stats, vigilweaveUrl),
        })
        core.info('PR comment posted.')
      } catch (err) {
        core.warning(`Failed to post PR comment: ${err}`)
      }
    }

    // Quality gates
    const gates = evaluateGates(stats, { failOnCritical, failOnHigh })
    if (!gates.passed) {
      core.setFailed(gates.reasons.join('; '))
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    core.setFailed(message)
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
    core.info(`Scan ${scanId} status: ${scan.status} — polling again in ${pollIntervalSeconds}s...`)
    await new Promise((resolve) => setTimeout(resolve, pollIntervalSeconds * 1000))
  }
  throw new Error(`Timed out waiting for VigilWeave scan ${scanId}`)
}

void main()
