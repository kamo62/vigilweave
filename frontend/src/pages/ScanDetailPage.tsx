import { useEffect, useMemo, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from '@tanstack/react-router'
import {
  BarChart3,
  CheckSquare,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Code2,
  Download,
  ShieldAlert,
  Square,
  Trash2,
  Wrench,
  X,
} from 'lucide-react'

import { CodeSnippet } from '@/components/CodeSnippet'
import type { CodeContext } from '@/components/CodeSnippet'
import { EmptyState } from '@/components/EmptyState'
import { FeatureGate } from '@/components/FeatureGate'
import { MetricCard } from '@/components/MetricCard'
import { SeverityBadge } from '@/components/SeverityBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Spinner } from '@/components/ui/spinner'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  bulkTriageFindings,
  deleteScan,
  downloadScanFindingsCsv,
  downloadScanReportPdf,
  fetchFindings,
  fetchQualityMetrics,
  fetchScan,
  triageFinding,
} from '@/lib/api'
import type { Finding, FindingFilters, ReviewStatus } from '@/lib/api'
import { useAuth } from '@/lib/useAuth'
import { useLicense } from '@/lib/hooks/useLicense'
import { formatMinutes, qualityTone } from '@/lib/utils'

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

const PAGE_SIZE = 50

const REVIEW_STATUS_OPTIONS: { value: ReviewStatus; label: string; color: string }[] = [
  { value: 'open', label: 'Open', color: '' },
  { value: 'acknowledged', label: 'Acknowledged', color: 'text-primary' },
  { value: 'false_positive', label: 'False Positive', color: 'text-warning' },
  { value: 'fixed', label: 'Fixed', color: 'text-success' },
  { value: 'wont_fix', label: "Won't Fix", color: 'text-muted-foreground' },
]

/** Human-readable category labels + descriptions */
const CATEGORY_INFO: Record<string, { label: string; description: string }> = {
  maintainability: {
    label: 'Maintainability',
    description:
      'Code that is hard to read, modify, or extend. Includes poor naming, long functions, deep nesting, and high cognitive complexity.',
  },
  style: {
    label: 'Style',
    description:
      'Formatting and coding convention issues like indentation, unused imports, and naming conventions.',
  },
  complexity: {
    label: 'Complexity',
    description:
      'Functions or classes with too many branches, loops, or decision paths, making them error-prone and hard to test.',
  },
  secret: {
    label: 'Secret',
    description: 'Hardcoded credentials, API keys, tokens, or passwords found in source code.',
  },
  container: {
    label: 'Container',
    description:
      'Security or best-practice issues in Dockerfiles and container configurations.',
  },
  iac: {
    label: 'Infrastructure',
    description:
      'Misconfigurations in infrastructure-as-code files (Terraform, CloudFormation, Kubernetes manifests).',
  },
  security: {
    label: 'Security',
    description:
      'Vulnerabilities such as injection flaws, insecure defaults, and missing input validation.',
  },
  vulnerability: {
    label: 'Vulnerability',
    description: 'Known CVEs or security weaknesses in dependencies or code.',
  },
}

const ENGINE_LABELS: Record<string, string> = {
  semgrep: 'SAST',
  bandit: 'SAST (Python)',
  eslint: 'SAST (JS/TS)',
  gitleaks: 'Secrets',
  trivy: 'Container & IaC',
  checkov: 'IaC',
  tflint: 'IaC (Terraform)',
  'cfn-lint': 'IaC (CloudFormation)',
  grype: 'SCA',
  ruff: 'Quality (Python)',
  sqlfluff: 'Quality (SQL)',
  swiftlint: 'Quality (Swift)',
  detekt: 'Quality (Kotlin)',
  'android-lint': 'Quality (Android)',
  'dotnet-analyzers': 'Quality (.NET)',
}

function engineLabel(raw: string): string {
  return ENGINE_LABELS[raw] ?? raw
}

function categoryLabel(raw: string): string {
  return CATEGORY_INFO[raw]?.label ?? raw
}

function categoryTooltip(raw: string): string | null {
  return CATEGORY_INFO[raw]?.description ?? null
}

function gateBadgeState(scan: {
  status: string
  quality_gate_passed?: boolean | null
}): { color: 'success' | 'warning' | 'danger' | 'default'; label: string } {
  if (scan.status !== 'completed') {
    if (scan.status === 'failed') return { color: 'default', label: 'Gate Not Evaluated' }
    return { color: 'warning', label: 'Gate Pending' }
  }
  if (scan.quality_gate_passed === true) return { color: 'success', label: 'Gate Passed' }
  if (scan.quality_gate_passed === false) return { color: 'danger', label: 'Gate Failed' }
  return { color: 'default', label: 'Gate Not Evaluated' }
}

type FindingWithStatus = Finding & { review_status?: string }

// ---------------------------------------------------------------------------
// Facet helpers
// ---------------------------------------------------------------------------

function countBy<T>(items: T[], key: (item: T) => string): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const item of items) {
    const k = key(item)
    counts[k] = (counts[k] ?? 0) + 1
  }
  return counts
}

function FacetSection({
  title,
  counts,
  selected,
  onToggle,
  labelFn,
  tooltipFn,
}: {
  title: string
  counts: Record<string, number>
  selected: Set<string>
  onToggle: (value: string) => void
  labelFn?: (value: string) => string
  tooltipFn?: (value: string) => string | null
}) {
  const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1])
  if (sorted.length === 0) return null
  return (
    <div>
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </p>
      <div className="space-y-0.5">
        {sorted.map(([value, count]) => {
          const active = selected.size === 0 || selected.has(value)
          const label = labelFn ? labelFn(value) : value
          const tip = tooltipFn ? tooltipFn(value) : null
          const btn = (
            <button
              className={`flex w-full items-center justify-between rounded px-2 py-1 text-left text-xs transition-colors ${
                active
                  ? 'text-foreground hover:bg-accent'
                  : 'text-muted-foreground/50 hover:bg-accent hover:text-muted-foreground'
              }`}
              key={value}
              onClick={() => onToggle(value)}
              type="button"
            >
              <span className="truncate">{label}</span>
              <span className="ml-2 tabular-nums">{count}</span>
            </button>
          )
          if (tip) {
            return (
              <Tooltip key={value}>
                <TooltipTrigger asChild>{btn}</TooltipTrigger>
                <TooltipContent side="right" className="max-w-[240px] text-xs">
                  {tip}
                </TooltipContent>
              </Tooltip>
            )
          }
          return btn
        })}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Finding card (replaces table row)
// ---------------------------------------------------------------------------

function FindingCard({
  finding,
  selected,
  expanded,
  selectable,
  onSelect,
  onExpand,
  onTriage,
}: {
  finding: FindingWithStatus
  selected: boolean
  expanded: boolean
  selectable: boolean
  onSelect: (findingId: number) => void
  onExpand: (findingId: number) => void
  onTriage: (findingId: number, status: ReviewStatus) => void
}) {
  const shortPath = finding.file_path
    ? finding.file_path.replace(/^\/var\/tmp\/vigilweave-[^/]+\//, '')
    : null

  const tip = categoryTooltip(finding.category)
  const codeContext = (finding.tool_metadata as Record<string, unknown> | undefined)
    ?.code_context as CodeContext | undefined

  return (
    <div
      className={`rounded-sm border transition-colors ${
        selected
          ? 'border-primary/40 bg-primary/5'
          : 'border-border bg-card hover:border-foreground/10'
      }`}
    >
      <div className="flex items-start gap-3 px-4 py-3">
        {selectable ? (
          <button
            className="mt-0.5 shrink-0 text-muted-foreground hover:text-foreground"
            onClick={(e) => {
              e.stopPropagation()
              onSelect(finding.id)
            }}
            type="button"
          >
            {selected ? (
              <CheckSquare size={16} className="text-primary" />
            ) : (
              <Square size={16} />
            )}
          </button>
        ) : null}
        <button
          className="min-w-0 flex-1 space-y-1.5 text-left"
          onClick={() => onExpand(finding.id)}
          type="button"
        >
          <div className="flex items-center gap-2">
            <SeverityBadge severity={finding.severity} />
            <span className="truncate text-sm font-medium">{finding.title}</span>
            {codeContext ? (
              <Code2
                size={13}
                className={`shrink-0 ${expanded ? 'text-primary' : 'text-muted-foreground/40'}`}
              />
            ) : null}
            <ChevronDown
              size={14}
              className={`shrink-0 text-muted-foreground/40 transition-transform ${expanded ? 'rotate-180' : ''}`}
            />
          </div>
          <p className="text-xs text-muted-foreground line-clamp-1">{finding.message}</p>
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
            {tip ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <span>
                    <Badge variant="bordered" className="cursor-help">
                      {categoryLabel(finding.category)}
                    </Badge>
                  </span>
                </TooltipTrigger>
                <TooltipContent side="top" className="max-w-[260px] text-xs">
                  {tip}
                </TooltipContent>
              </Tooltip>
            ) : (
              <Badge variant="bordered">{categoryLabel(finding.category)}</Badge>
            )}
            <span className="font-mono">{engineLabel(finding.tool)}</span>
            {shortPath ? (
              <>
                <span>&middot;</span>
                <span className="font-mono truncate max-w-[300px]">
                  {shortPath}:{finding.line ?? 1}
                </span>
              </>
            ) : null}
            {finding.rule_id ? (
              <>
                <span>&middot;</span>
                <span className="font-mono">{finding.rule_id}</span>
              </>
            ) : null}
          </div>
        </button>
        <Select
          defaultValue={finding.review_status ?? 'open'}
          onValueChange={(value) => onTriage(finding.id, value as ReviewStatus)}
        >
          <SelectTrigger className="h-7 w-[120px] shrink-0 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {REVIEW_STATUS_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                <span className={opt.color}>{opt.label}</span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Expanded detail: code context */}
      {expanded ? (
        <div className="border-t border-border px-4 py-3 space-y-3">
          {finding.description ? (
            <p className="text-xs text-muted-foreground">{finding.description}</p>
          ) : null}
          {codeContext ? (
            <CodeSnippet context={codeContext} message={finding.message} />
          ) : (
            <div className="rounded-sm border border-dashed border-border px-4 py-6 text-center">
              <Code2 size={20} className="mx-auto mb-2 text-muted-foreground/40" />
              <p className="text-xs text-muted-foreground">
                Code context not available for this finding.
              </p>
              <p className="mt-1 text-[11px] text-muted-foreground/60">
                Re-run the scan to capture source code snippets.
              </p>
            </div>
          )}
          <div className="flex flex-wrap gap-4 text-[11px] text-muted-foreground">
            {finding.cwe_id ? (
              <span>
                <span className="font-semibold">CWE:</span> {finding.cwe_id}
              </span>
            ) : null}
            {finding.owasp_category ? (
              <span>
                <span className="font-semibold">OWASP:</span> {finding.owasp_category}
              </span>
            ) : null}
            {finding.confidence ? (
              <span>
                <span className="font-semibold">Confidence:</span> {finding.confidence}
              </span>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function ScanDetailPage() {
  const { user } = useAuth()
  const params = useParams({ from: '/scans/$scanId' })
  const scanId = Number(params.scanId)
  const navigate = useNavigate()
  const { hasFeature } = useLicense()
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const isTenantAdmin = user?.role === 'admin'

  // Filters
  const [severityFilter, setSeverityFilter] = useState<Set<string>>(new Set())
  const [categoryFilter, setCategoryFilter] = useState<Set<string>>(new Set())
  const [toolFilter, setToolFilter] = useState<Set<string>>(new Set())
  const [statusFilter, setStatusFilter] = useState<Set<string>>(new Set())
  const [includeSuppressed, setIncludeSuppressed] = useState(false)
  const [page, setPage] = useState(0)

  // Selection & expansion
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [expandedId, setExpandedId] = useState<number | null>(null)

  // Queries
  const scanQuery = useQuery({
    queryKey: ['scan', scanId],
    queryFn: () => fetchScan(scanId),
    enabled: Number.isFinite(scanId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status && status !== 'completed' && status !== 'failed' ? 2000 : false
    },
  })
  const findingsQuery = useQuery({
    queryKey: ['findings', scanId, includeSuppressed],
    queryFn: () => fetchFindings(scanId, { include_suppressed: includeSuppressed }),
    enabled: Number.isFinite(scanId),
  })
  const qualityQuery = useQuery({
    queryKey: ['quality-metrics', scanId],
    queryFn: () => fetchQualityMetrics(scanId),
    enabled: Number.isFinite(scanId),
  })

  const queryClient = useQueryClient()
  const triageMutation = useMutation({
    mutationFn: ({ findingId, status }: { findingId: number; status: ReviewStatus }) =>
      triageFinding(scanId, findingId, { review_status: status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['findings', scanId] })
    },
  })

  const bulkTriageMutation = useMutation({
    mutationFn: ({ ids, status }: { ids: number[]; status: ReviewStatus }) =>
      bulkTriageFindings(scanId, { finding_ids: ids, review_status: status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['findings', scanId] })
      setSelectedIds(new Set())
    },
  })

  const reportMutation = useMutation({
    mutationFn: (filters: FindingFilters) => downloadScanReportPdf(scanId, filters),
  })

  const exportMutation = useMutation({
    mutationFn: (filters: FindingFilters) => downloadScanFindingsCsv(scanId, filters),
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteScan(scanId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scans'] })
      navigate({ to: '/scans' })
    },
  })

  const scan = scanQuery.data
  const gate = scan ? gateBadgeState(scan) : null
  const canBulkTriage = hasFeature('bulk_triage')
  const allFindings = useMemo(
    () => (findingsQuery.data ?? []) as FindingWithStatus[],
    [findingsQuery.data],
  )
  const quality = qualityQuery.data

  // Facet counts (from ALL findings, before filtering)
  const severityCounts = useMemo(() => countBy(allFindings, (f) => f.severity), [allFindings])
  const categoryCounts = useMemo(() => countBy(allFindings, (f) => f.category), [allFindings])
  const toolCounts = useMemo(() => countBy(allFindings, (f) => f.tool), [allFindings])
  const statusCounts = useMemo(
    () => countBy(allFindings, (f) => f.review_status ?? 'open'),
    [allFindings],
  )

  // Apply filters
  const filtered = useMemo(() => {
    return allFindings.filter((f) => {
      if (severityFilter.size > 0 && !severityFilter.has(f.severity)) return false
      if (categoryFilter.size > 0 && !categoryFilter.has(f.category)) return false
      if (toolFilter.size > 0 && !toolFilter.has(f.tool)) return false
      if (statusFilter.size > 0 && !statusFilter.has(f.review_status ?? 'open')) return false
      return true
    })
  }, [allFindings, severityFilter, categoryFilter, toolFilter, statusFilter])

  const activeFilters = useMemo<FindingFilters>(
    () => ({
      severity: Array.from(severityFilter),
      category: Array.from(categoryFilter),
      tool: Array.from(toolFilter),
      review_status: Array.from(statusFilter) as ReviewStatus[],
      include_suppressed: includeSuppressed,
    }),
    [severityFilter, categoryFilter, toolFilter, statusFilter, includeSuppressed],
  )
  const downloadError = reportMutation.error ?? exportMutation.error
  const downloadErrorMessage =
    downloadError instanceof Error
      ? downloadError.message
      : 'Report download failed. Verify reporting is enabled and the server can launch Chromium.'

  useEffect(() => {
    if (!canBulkTriage && selectedIds.size > 0) {
      setSelectedIds(new Set())
    }
  }, [canBulkTriage, selectedIds.size])

  // Pagination
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))

  const paginatedFindings = useMemo(() => {
    const start = page * PAGE_SIZE
    return filtered.slice(start, start + PAGE_SIZE)
  }, [filtered, page])

  const paginatedGrouped = useMemo(() => {
    const groups: Record<string, FindingWithStatus[]> = {}
    for (const f of paginatedFindings) {
      const key = f.file_path ?? 'Unknown'
      ;(groups[key] ??= []).push(f)
    }
    return groups
  }, [paginatedFindings])

  // Toggle helpers
  function toggleFilter(set: Set<string>, setFn: (s: Set<string>) => void, value: string) {
    const next = new Set(set)
    if (next.has(value)) {
      next.delete(value)
    } else {
      next.add(value)
    }
    setFn(next)
    setPage(0)
  }

  function handleTriage(findingId: number, status: ReviewStatus) {
    triageMutation.mutate({ findingId, status })
  }

  function toggleExpand(findingId: number) {
    setExpandedId((prev) => (prev === findingId ? null : findingId))
  }

  function toggleSelect(findingId: number) {
    if (!canBulkTriage) return
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(findingId)) {
        next.delete(findingId)
      } else {
        next.add(findingId)
      }
      return next
    })
  }

  function selectAllOnPage() {
    if (!canBulkTriage) return
    setSelectedIds((prev) => {
      const next = new Set(prev)
      for (const f of paginatedFindings) {
        next.add(f.id)
      }
      return next
    })
  }

  function selectAllFiltered() {
    if (!canBulkTriage) return
    setSelectedIds(new Set(filtered.map((f) => f.id)))
  }

  function clearSelection() {
    setSelectedIds(new Set())
  }

  function handleBulkTriage(status: ReviewStatus) {
    if (!canBulkTriage) return
    const ids = Array.from(selectedIds)
    if (ids.length === 0) return
    bulkTriageMutation.mutate({ ids, status })
  }

  function resetDownloadState() {
    reportMutation.reset()
    exportMutation.reset()
  }

  function triggerPdfDownload() {
    resetDownloadState()
    reportMutation.mutate(activeFilters)
  }

  function triggerCsvDownload() {
    resetDownloadState()
    exportMutation.mutate(activeFilters)
  }

  const pageAllSelected =
    canBulkTriage &&
    paginatedFindings.length > 0 &&
    paginatedFindings.every((f) => selectedIds.has(f.id))

  if (scanQuery.isLoading && !scan) {
    return (
      <div className="flex justify-center py-20">
        <Spinner label="Loading scan..." />
      </div>
    )
  }

  if (scanQuery.isError) {
    return (
      <EmptyState
        body="The requested scan could not be loaded. Refresh the page and verify the API is reachable."
        title="Scan unavailable"
      />
    )
  }

  if (!scan) {
    return (
      <EmptyState
        body="The requested scan does not exist or has not been loaded yet."
        title="Scan not found"
      />
    )
  }

  return (
    <TooltipProvider delayDuration={300}>
      <div className="space-y-6">
        {findingsQuery.isError ? (
          <div className="rounded-sm border border-warning/30 bg-warning/5 px-4 py-3 text-sm text-warning">
            Findings could not be loaded for this scan. Try refreshing the page.
          </div>
        ) : null}
        {qualityQuery.isError ? (
          <div className="rounded-sm border border-warning/30 bg-warning/5 px-4 py-3 text-sm text-warning">
            Quality metrics are unavailable for this scan right now.
          </div>
        ) : null}
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
              Scan #{scan.id}
            </p>
            <h1 className="text-2xl font-bold tracking-tight">{scan.repo}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {scan.scan_type} scan &middot; {scan.status}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <FeatureGate
              feature="reporting"
              fallback={
                <Button disabled size="sm" variant="flat">
                  <Download size={14} />
                  Pro reports
                </Button>
              }
            >
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="flat"
                  isLoading={reportMutation.isPending}
                  onClick={triggerPdfDownload}
                >
                  <Download size={14} />
                  PDF report
                </Button>
                <Button
                  size="sm"
                  variant="flat"
                  isLoading={exportMutation.isPending}
                  onClick={triggerCsvDownload}
                >
                  <Download size={14} />
                  CSV export
                </Button>
              </div>
            </FeatureGate>
            <Badge color={gate?.color ?? 'default'} size="lg" variant="flat">
              {gate?.label ?? 'Gate Unknown'}
            </Badge>
            {isTenantAdmin ? (
              <Button
                variant="flat"
                size="sm"
                onClick={() => setShowDeleteDialog(true)}
                className="text-danger hover:bg-danger/10"
              >
                <Trash2 size={14} />
                Delete
              </Button>
            ) : null}
          </div>
        </div>

        {/* KPI row */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <MetricCard
            icon={<ShieldAlert size={16} />}
            label="Total findings"
            value={String(scan.total_findings)}
          />
          <MetricCard
            icon={<BarChart3 size={16} />}
            label="Quality score"
            tone={qualityTone(scan.quality_score)}
            value={scan.quality_score?.toFixed(1) ?? 'N/A'}
          />
          <MetricCard
            icon={<Wrench size={16} />}
            label="Tech debt"
            value={formatMinutes(scan.technical_debt_minutes)}
          />
          {scan.quality_grade ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center gap-1 p-4">
                <span className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
                  Grade
                </span>
                <span
                  className={`text-4xl font-black ${
                    scan.quality_grade === 'A'
                      ? 'text-success'
                      : scan.quality_grade === 'B'
                        ? 'text-primary'
                        : scan.quality_grade === 'C'
                          ? 'text-warning'
                          : 'text-danger'
                  }`}
                >
                  {scan.quality_grade}
                </span>
              </CardContent>
            </Card>
          ) : null}
        </div>

        {/* Issues section: sidebar + cards */}
        <div className="flex gap-6">
          {/* Filter sidebar */}
          {allFindings.length > 0 ? (
            <aside className="hidden w-[200px] shrink-0 space-y-5 lg:block">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
                  Filters
                </p>
                {(severityFilter.size > 0 ||
                  categoryFilter.size > 0 ||
                  toolFilter.size > 0 ||
                  statusFilter.size > 0) && (
                  <button
                    className="mt-1 text-[11px] text-primary hover:underline"
                    onClick={() => {
                      setSeverityFilter(new Set())
                      setCategoryFilter(new Set())
                      setToolFilter(new Set())
                      setStatusFilter(new Set())
                      setIncludeSuppressed(false)
                      setPage(0)
                    }}
                    type="button"
                  >
                    Clear all
                  </button>
                )}
              </div>
              <FacetSection
                counts={severityCounts}
                selected={severityFilter}
                title="Severity"
                onToggle={(v) => toggleFilter(severityFilter, setSeverityFilter, v)}
              />
              <FacetSection
                counts={categoryCounts}
                selected={categoryFilter}
                title="Category"
                onToggle={(v) => toggleFilter(categoryFilter, setCategoryFilter, v)}
                labelFn={categoryLabel}
                tooltipFn={categoryTooltip}
              />
              <FacetSection
                counts={toolCounts}
                selected={toolFilter}
                title="Tool"
                onToggle={(v) => toggleFilter(toolFilter, setToolFilter, v)}
              />
              <FacetSection
                counts={statusCounts}
                selected={statusFilter}
                title="Status"
                onToggle={(v) => toggleFilter(statusFilter, setStatusFilter, v)}
              />
              <div className="rounded-sm border border-border bg-card px-3 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Suppressed
                    </p>
                    <p className="text-xs text-muted-foreground">Include waived findings in the view.</p>
                  </div>
                  <Switch checked={includeSuppressed} onCheckedChange={setIncludeSuppressed} />
                </div>
              </div>
            </aside>
          ) : null}

          {/* Main findings area */}
          <div className="min-w-0 flex-1 space-y-4">
            {/* Bulk action bar */}
            {selectedIds.size > 0 ? (
              <FeatureGate feature="bulk_triage" fallback={null}>
                <div className="flex items-center gap-3 rounded-sm border border-primary/30 bg-primary/5 px-4 py-2.5">
                  <span className="text-sm font-medium">
                    {selectedIds.size.toLocaleString()} selected
                  </span>
                  <Separator orientation="vertical" className="h-5" />
                  <span className="text-xs text-muted-foreground">Change status to:</span>
                  {REVIEW_STATUS_OPTIONS.map((opt) => (
                    <Button
                      key={opt.value}
                      size="sm"
                      variant="flat"
                      onClick={() => handleBulkTriage(opt.value)}
                      disabled={bulkTriageMutation.isPending}
                      className="text-xs"
                    >
                      <span className={opt.color}>{opt.label}</span>
                    </Button>
                  ))}
                  <div className="flex-1" />
                  <Button size="sm" variant="flat" onClick={clearSelection} isIconOnly>
                    <X size={14} />
                  </Button>
                </div>
              </FeatureGate>
            ) : null}

            {reportMutation.isError || exportMutation.isError ? (
              <Card className="border-danger/30 bg-danger/[0.06]">
                <CardContent className="flex items-center justify-between gap-3 p-4 text-sm text-danger">
                  <span>{downloadErrorMessage}</span>
                  <Button size="sm" variant="flat" onClick={resetDownloadState}>
                    Dismiss
                  </Button>
                </CardContent>
              </Card>
            ) : null}

            {/* Count + pagination + selection header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <p className="text-sm font-semibold">
                  {filtered.length.toLocaleString()} issue{filtered.length !== 1 ? 's' : ''}
                  {filtered.length !== allFindings.length
                    ? ` (of ${allFindings.length.toLocaleString()})`
                    : ''}
                </p>
                {canBulkTriage ? (
                  <>
                    <Separator orientation="vertical" className="h-4" />
                    {pageAllSelected ? (
                      <button
                        className="text-xs text-primary hover:underline"
                        onClick={
                          selectedIds.size < filtered.length ? selectAllFiltered : clearSelection
                        }
                        type="button"
                      >
                        {selectedIds.size < filtered.length
                          ? `Select all ${filtered.length.toLocaleString()} filtered`
                          : 'Clear selection'}
                      </button>
                    ) : (
                      <button
                        className="text-xs text-muted-foreground hover:text-foreground hover:underline"
                        onClick={selectAllOnPage}
                        type="button"
                      >
                        Select page ({paginatedFindings.length})
                      </button>
                    )}
                  </>
                ) : null}
              </div>
              {totalPages > 1 && (
                <div className="flex items-center gap-2">
                  <Button
                    disabled={page === 0}
                    isIconOnly
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    size="sm"
                    variant="flat"
                  >
                    <ChevronLeft size={14} />
                  </Button>
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {page + 1} / {totalPages}
                  </span>
                  <Button
                    disabled={page >= totalPages - 1}
                    isIconOnly
                    onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                    size="sm"
                    variant="flat"
                  >
                    <ChevronRight size={14} />
                  </Button>
                </div>
              )}
            </div>

            {/* Grouped finding cards */}
            {filtered.length === 0 ? (
              <EmptyState
                body="No findings match the selected filters."
                title="No matching findings"
              />
            ) : (
              Object.entries(paginatedGrouped).map(([filePath, fileFindings]) => {
                const shortPath = filePath.replace(/^\/var\/tmp\/vigilweave-[^/]+\//, '')
                return (
                  <div key={filePath}>
                    <p className="mb-2 truncate text-xs font-mono text-muted-foreground">
                      {shortPath}
                    </p>
                    <div className="space-y-2">
                      {fileFindings.map((finding) => (
                        <FindingCard
                          finding={finding}
                          key={finding.id}
                          selected={selectedIds.has(finding.id)}
                          expanded={expandedId === finding.id}
                          selectable={canBulkTriage}
                          onSelect={toggleSelect}
                          onExpand={toggleExpand}
                          onTriage={handleTriage}
                        />
                      ))}
                    </div>
                  </div>
                )
              })
            )}

            {/* Bottom pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 pt-2">
                <Button
                  disabled={page === 0}
                  isIconOnly
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  size="sm"
                  variant="flat"
                >
                  <ChevronLeft size={14} />
                </Button>
                <span className="text-xs text-muted-foreground tabular-nums">
                  Page {page + 1} of {totalPages}
                </span>
                <Button
                  disabled={page >= totalPages - 1}
                  isIconOnly
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  size="sm"
                  variant="flat"
                >
                  <ChevronRight size={14} />
                </Button>
              </div>
            )}
          </div>
        </div>

        {/* File metrics */}
        <Card>
          <CardHeader className="px-6 pt-5">
            <div>
              <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
                Quality
              </p>
              <h2 className="text-lg font-semibold">File-level metrics</h2>
            </div>
          </CardHeader>
          <Separator />
          <CardContent className="p-0">
            {quality?.files?.length ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>File</TableHead>
                    <TableHead>Language</TableHead>
                    <TableHead>LOC</TableHead>
                    <TableHead>
                      <Tooltip>
                        <TooltipTrigger className="cursor-help underline decoration-dotted underline-offset-4">
                          Complexity
                        </TooltipTrigger>
                        <TooltipContent className="max-w-[260px] text-xs">
                          Cyclomatic complexity measures how many independent paths exist through a
                          function. Higher values mean more branches and harder-to-test code.
                          Values above 14 are flagged.
                        </TooltipContent>
                      </Tooltip>
                    </TableHead>
                    <TableHead>
                      <Tooltip>
                        <TooltipTrigger className="cursor-help underline decoration-dotted underline-offset-4">
                          Maintainability
                        </TooltipTrigger>
                        <TooltipContent className="max-w-[260px] text-xs">
                          A 0-100 score estimating how easy the code is to understand and change.
                          Combines complexity, lines of code, and nesting depth. Below 55 is
                          flagged as hard to maintain.
                        </TooltipContent>
                      </Tooltip>
                    </TableHead>
                    <TableHead>
                      <Tooltip>
                        <TooltipTrigger className="cursor-help underline decoration-dotted underline-offset-4">
                          Debt
                        </TooltipTrigger>
                        <TooltipContent className="max-w-[240px] text-xs">
                          Estimated time to fix all quality issues in this file. Calculated from
                          complexity, duplication, and style violations.
                        </TooltipContent>
                      </Tooltip>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {quality.files.map((file) => (
                    <TableRow key={file.id}>
                      <TableCell>
                        <span className="text-xs font-mono">{file.file_path}</span>
                      </TableCell>
                      <TableCell>
                        <Badge variant="flat">{file.language}</Badge>
                      </TableCell>
                      <TableCell>{file.lines_of_code}</TableCell>
                      <TableCell>
                        <span
                          className={
                            file.cyclomatic_complexity >= 14 ? 'text-danger font-semibold' : ''
                          }
                        >
                          {file.cyclomatic_complexity}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span
                          className={
                            file.maintainability_index < 55 ? 'text-warning font-semibold' : ''
                          }
                        >
                          {file.maintainability_index.toFixed(1)}
                        </span>
                      </TableCell>
                      <TableCell>{formatMinutes(file.technical_debt_minutes)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="p-6">
                <EmptyState body="This scan has no file metrics." title="No file metrics" />
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={isTenantAdmin && showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Scan #{scan.id}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            This will permanently delete this scan and all {scan.total_findings.toLocaleString()}{' '}
            findings. This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="flat" onClick={() => setShowDeleteDialog(false)}>
              Cancel
            </Button>
            <Button
              color="danger"
              isLoading={deleteMutation.isPending}
              onClick={() => deleteMutation.mutate()}
            >
              Delete Scan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </TooltipProvider>
  )
}
