import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchFindings, fetchQualityMetrics, fetchScan } from '@/lib/api'
import type { QualityMetrics, Scan } from '@/lib/api'
import { ScanDetailPage } from './ScanDetailPage'

vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useParams: () => ({ scanId: '42' }),
  }
})

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...actual,
    fetchFindings: vi.fn(),
    fetchQualityMetrics: vi.fn(),
    fetchScan: vi.fn(),
  }
})

vi.mock('@/lib/useAuth', () => ({
  useAuth: () => ({ user: { role: 'admin' } }),
}))

vi.mock('@/lib/hooks/useLicense', () => ({
  useLicense: () => ({ hasFeature: () => true }),
}))

vi.mock('@/components/FeatureGate', () => ({
  FeatureGate: ({ children }: { children: ReactNode }) => children,
}))

function scan(status: Scan['status'], scanMetadata?: Record<string, unknown>): Scan {
  return {
    id: 42,
    tenant_slug: 'default',
    repo: 'https://example.com/team/repo',
    source: 'native',
    scan_type: 'comprehensive',
    status,
    include_quality_metrics: true,
    quality_gate_passed: null,
    total_findings: 0,
    critical_findings: 0,
    high_findings: 0,
    medium_findings: 0,
    low_findings: 0,
    info_findings: 0,
    quality_issues: 0,
    style_issues: 0,
    complexity_issues: 0,
    suppressed_findings: 0,
    assignment_status: 'unassigned',
    started_at: '2026-11-14T08:00:00Z',
    scan_metadata: scanMetadata,
  }
}

function renderScanPage(queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, staleTime: Infinity } },
})) {
  const view = render(
    <QueryClientProvider client={queryClient}>
      <ScanDetailPage />
    </QueryClientProvider>,
  )
  return { ...view, queryClient }
}

describe('ScanDetailPage', () => {
  beforeEach(() => {
    vi.mocked(fetchScan).mockReset()
    vi.mocked(fetchFindings).mockReset()
    vi.mocked(fetchQualityMetrics).mockReset()
    vi.mocked(fetchFindings).mockResolvedValue([])
    vi.mocked(fetchQualityMetrics).mockResolvedValue({
      scan_id: 42,
      quality_issues: 0,
      style_issues: 0,
      complexity_issues: 0,
      files: [],
    } satisfies QualityMetrics)
  })

  it('refreshes findings and file metrics once when a running scan completes', async () => {
    vi.mocked(fetchScan).mockResolvedValue(scan('running'))
    const { queryClient } = renderScanPage()

    expect(await screen.findByText(/comprehensive scan · running/)).toBeInTheDocument()
    await waitFor(() => {
      expect(fetchFindings).toHaveBeenCalledTimes(1)
      expect(fetchQualityMetrics).toHaveBeenCalledTimes(1)
    })

    await act(async () => {
      queryClient.setQueryData(['scan', 42], scan('completed'))
    })

    await waitFor(() => {
      expect(fetchFindings).toHaveBeenCalledTimes(2)
      expect(fetchQualityMetrics).toHaveBeenCalledTimes(2)
    })

    await act(async () => {
      queryClient.setQueryData(['scan', 42], scan('completed'))
    })

    expect(fetchFindings).toHaveBeenCalledTimes(2)
    expect(fetchQualityMetrics).toHaveBeenCalledTimes(2)
  })

  it('displays the backend error for a failed scan', async () => {
    vi.mocked(fetchScan).mockResolvedValue(
      scan('failed', { error: 'Scanner process exited with code 1' }),
    )
    renderScanPage()

    expect(await screen.findByText('Scanner process exited with code 1')).toBeInTheDocument()
  })

  it('explains coverage failures and analyser executions', async () => {
    vi.mocked(fetchScan).mockResolvedValue({
      ...scan('completed', { coverage_reasons: ['No analyser completed successfully'], policy: { reasons: ['High findings exceed limit'] } }),
      quality_gate_passed: false,
      tool_executions: [{ id: 1, scan_id: 42, tool: 'bandit', status: 'failed', findings_count: 0, version: '1.0', started_at: '2026-11-14T08:00:00Z', completed_at: '2026-11-14T08:00:02Z', stderr_summary: 'report missing' }],
    })
    renderScanPage()
    expect(await screen.findByText('No analyser completed successfully')).toBeInTheDocument()
    expect(screen.getByText('High findings exceed limit')).toBeInTheDocument()
    expect(screen.getByText(/report missing/)).toBeInTheDocument()
  })
})
