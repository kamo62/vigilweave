import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'
import {
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  GitBranch,
  Play,
  Plus,
  ShieldCheck,
  Tag,
  Trash2,
  XCircle,
} from 'lucide-react'
import { useEffect, useState } from 'react'

import { EmptyState } from '@/components/EmptyState'
import { GitHubAppRepoPicker } from '@/components/GitHubAppRepoPicker'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Spinner } from '@/components/ui/spinner'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import {
  addProjectRepos,
  fetchProjectMetrics,
  fetchProjects,
  fetchRepositoryHistory,
  fetchScans,
  removeProjectRepo,
} from '@/lib/api'
import { useGitHubAppInstallResult } from '@/lib/hooks/useGitHubAppInstallResult'
import { validateRepositoryUrls } from '@/lib/repositories'
import { pickLatestScan } from '@/lib/scan-recency'
import { useAuth } from '@/lib/useAuth'
import { gradeColor, qualityGrade, qualityTone, securityGrade } from '@/lib/utils'

function GradeBadge({ grade, size = 'md' }: { grade: string; size?: 'sm' | 'md' | 'lg' }) {
  const color = gradeColor[grade as keyof typeof gradeColor] ?? 'bg-default text-default-foreground'
  const sizeClass =
    size === 'lg'
      ? 'h-10 w-10 text-lg'
      : size === 'sm'
        ? 'h-5 w-5 text-[10px]'
        : 'h-7 w-7 text-sm'
  return (
    <span
      className={`inline-flex items-center justify-center rounded-full font-bold ${color} ${sizeClass}`}
    >
      {grade}
    </span>
  )
}

function SnapshotCard({
  title,
  value,
  grade,
  subtitle,
}: {
  title: string
  value: string | number
  grade: string
  subtitle?: string
}) {
  return (
    <Card className="bg-muted/50">
      <CardContent className="gap-3 p-5">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{title}</p>
        <div className="flex items-center gap-4">
          <GradeBadge grade={grade} size="lg" />
          <div>
            <p className="text-2xl font-bold">{value}</p>
            {subtitle ? <p className="text-xs text-muted-foreground">{subtitle}</p> : null}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function RepoTimeline({ repoUrl }: { repoUrl: string }) {
  const historyQuery = useQuery({
    queryKey: ['repository-history', repoUrl],
    queryFn: () => fetchRepositoryHistory(repoUrl, 10),
  })
  const points = historyQuery.data?.points ?? []

  return (
    <div>
      <p className="mb-2 truncate text-sm font-semibold">{repoUrl}</p>
      {historyQuery.isLoading ? (
        <p className="text-xs text-muted-foreground">Loading...</p>
      ) : historyQuery.isError ? (
        <p className="text-xs text-danger">Repository history is unavailable right now.</p>
      ) : points.length === 0 ? (
        <p className="text-xs text-muted-foreground">No scan history for this repository.</p>
      ) : (
        <div className="space-y-2">
          {points.map((point) => (
            <div
              className="flex items-center justify-between rounded-sm border border-border bg-muted/50 px-4 py-2"
              key={point.scan_id}
            >
              <div className="flex items-center gap-3">
                <Badge
                  color={
                    point.status === 'completed'
                      ? 'success'
                      : point.status === 'failed'
                        ? 'danger'
                        : 'warning'
                  }
                  variant="flat"
                >
                  {point.status}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  Scan #{point.scan_id}
                </span>
              </div>
              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                <span>{point.total_findings} findings</span>
                <span>Quality: {point.quality_score ?? 'N/A'}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function ProjectDetailPage() {
  const { user } = useAuth()
  const { projectKey } = useParams({ from: '/projects/$projectKey' })
  const queryClient = useQueryClient()
  const [addRepoOpen, setAddRepoOpen] = useState(false)
  const [addRepoMode, setAddRepoMode] = useState<'manual' | 'github-app'>('manual')
  const githubInstallResult = useGitHubAppInstallResult()
  const [newRepos, setNewRepos] = useState('')
  const [selectedGitHubRepoUrls, setSelectedGitHubRepoUrls] = useState<Set<string>>(new Set())
  const [selectedGitHubInstallationId, setSelectedGitHubInstallationId] = useState<number | null>(null)
  const [addRepoError, setAddRepoError] = useState<string | null>(null)
  const [repoToRemove, setRepoToRemove] = useState<string | null>(null)
  const canManageProject = user?.role === 'admin'

  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: fetchProjects,
  })

  const metricsQuery = useQuery({
    queryKey: ['project-metrics', projectKey],
    queryFn: () => fetchProjectMetrics(projectKey),
  })

  const scansQuery = useQuery({
    queryKey: ['scans'],
    queryFn: fetchScans,
  })

  const addRepoMutation = useMutation({
    mutationFn: ({
      githubInstallationId,
      repos,
    }: {
      githubInstallationId?: number
      repos: string[]
    }) =>
      addProjectRepos(projectKey, repos, {
        githubInstallationId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      queryClient.invalidateQueries({ queryKey: ['project-metrics', projectKey] })
      setAddRepoOpen(false)
      setAddRepoMode('manual')
      setNewRepos('')
      setSelectedGitHubRepoUrls(new Set())
      setSelectedGitHubInstallationId(null)
      setAddRepoError(null)
    },
  })

  const removeRepoMutation = useMutation({
    mutationFn: (repo: string) => removeProjectRepo(projectKey, repo),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      queryClient.invalidateQueries({ queryKey: ['project-metrics', projectKey] })
      queryClient.invalidateQueries({ queryKey: ['repository-history'] })
      setRepoToRemove(null)
    },
  })

  const project = projectsQuery.data?.find((p) => p.key === projectKey)
  const metrics = metricsQuery.data
  const allScans = scansQuery.data ?? []

  useEffect(() => {
    if (!githubInstallResult) {
      return
    }

    setAddRepoError(null)
    setAddRepoMode('github-app')
    setAddRepoOpen(true)
  }, [githubInstallResult])

  if (projectsQuery.isLoading || metricsQuery.isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner label="Loading project..." />
      </div>
    )
  }

  if (projectsQuery.isError || metricsQuery.isError) {
    return (
      <EmptyState
        title="Project unavailable"
        body="The project details could not be loaded. Refresh the page and verify the API is reachable."
      />
    )
  }

  if (!project) {
    return <EmptyState body={`Project "${projectKey}" was not found.`} title="Project not found" />
  }

  const repos = project.repos ?? []
  const secGrade = securityGrade(metrics?.critical_findings ?? 0, metrics?.high_findings ?? 0)
  const qualGrade = qualityGrade(metrics?.avg_quality_score)
  const gatePassed = metrics?.quality_gate_passed

  // Get latest scan per repo
  const repoScans = repos.map((repoUrl) => {
    const scan = pickLatestScan(
      allScans.filter((candidate) => candidate.repo === repoUrl && candidate.project_key === projectKey),
    )
    return { repoUrl, scan }
  })

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link className="hover:text-foreground" to="/projects">
          Projects
        </Link>
        <ChevronRight size={14} />
        <span className="text-foreground">{project.name}</span>
      </div>

      {/* Page header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{project.name}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            {project.tags && project.tags.length > 0 ? (
              <span className="flex items-center gap-1">
                <Tag size={12} />
                {project.tags.join(', ')}
              </span>
            ) : (
              <span>No tags</span>
            )}
            <span>·</span>
            <span>{repos.length} {repos.length === 1 ? 'repository' : 'repositories'}</span>
            {project.description ? (
              <>
                <span>·</span>
                <span>{project.description}</span>
              </>
            ) : null}
          </div>
        </div>
        {canManageProject ? (
          <Button color="primary" size="sm" variant="flat" onClick={() => setAddRepoOpen(true)}>
            <Plus size={14} />
            Add Repos
          </Button>
        ) : null}
      </div>

      {scansQuery.isError ? (
        <div className="rounded-sm border border-warning/30 bg-warning/5 px-4 py-3 text-sm text-warning">
          The scan list could not be loaded. Repository membership is still available, but the latest scan rollups may be incomplete.
        </div>
      ) : null}

      {githubInstallResult ? (
        <div
          className={`rounded-sm border px-4 py-3 text-sm ${
            githubInstallResult.connected
              ? 'border-success/30 bg-success/[0.06] text-success'
              : 'border-danger/30 bg-danger/[0.06] text-danger'
          }`}
        >
          {githubInstallResult.message}
        </div>
      ) : null}

      {/* Quality Gate banner */}
      <Card
        className={`border ${
          gatePassed === false
            ? 'border-danger/30 bg-danger/[0.06]'
            : gatePassed === true
              ? 'border-success/30 bg-success/[0.06]'
              : 'border-border bg-card'
        }`}
      >
        <CardContent className="flex flex-row items-center gap-4 p-5">
          {gatePassed === true ? (
            <>
              <CheckCircle2 className="text-success" size={28} />
              <div>
                <p className="text-sm font-semibold text-success">Quality Gate Passed</p>
                <p className="text-xs text-muted-foreground">
                  All repositories meet the configured quality thresholds.
                </p>
              </div>
            </>
          ) : gatePassed === false ? (
            <>
              <XCircle className="text-danger" size={28} />
              <div>
                <p className="text-sm font-semibold text-danger">Quality Gate Failed</p>
                <p className="text-xs text-muted-foreground">
                  One or more repositories exceed quality thresholds.
                </p>
              </div>
            </>
          ) : (
            <>
              <ShieldCheck className="text-muted-foreground" size={28} />
              <div>
                <p className="text-sm font-semibold">Quality Gate</p>
                <p className="text-xs text-muted-foreground">
                  No gate data available. Run scans to generate results.
                </p>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Health dashboard */}
      <div>
        <h2 className="mb-4 text-lg font-semibold">Project health dashboard</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <SnapshotCard
            grade={secGrade}
            subtitle={`${metrics?.high_findings ?? 0} high`}
            title="Security"
            value={metrics?.critical_findings ?? 0}
          />
          <SnapshotCard
            grade={qualGrade}
            subtitle="Average across repos"
            title="Quality Score"
            value={metrics?.avg_quality_score?.toFixed(1) ?? 'N/A'}
          />
          <SnapshotCard
            grade={
              (metrics?.total_findings ?? 0) === 0
                ? 'A'
                : (metrics?.total_findings ?? 0) <= 10
                  ? 'B'
                  : (metrics?.total_findings ?? 0) <= 50
                    ? 'C'
                    : 'D'
            }
            subtitle="Across all repos"
            title="Total Findings"
            value={metrics?.total_findings ?? 0}
          />
          <Card className="bg-muted/50">
            <CardContent className="gap-3 p-5">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Repositories
              </p>
              <div className="flex items-center gap-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                  <GitBranch className="text-primary" size={20} />
                </div>
                <div>
                  <p className="text-2xl font-bold">{metrics?.repo_count ?? repos.length}</p>
                  <p className="text-xs text-muted-foreground">Connected repos</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Repository list */}
      <Card>
        <CardHeader className="px-6 pt-5">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
              Repositories
            </p>
            <h2 className="text-lg font-semibold">Member repositories</h2>
          </div>
        </CardHeader>
        <Separator />
        <CardContent className="space-y-3 p-6">
          {repos.length === 0 ? (
            <EmptyState
              body="Add repositories to this project to track their aggregate metrics."
              title="No repositories"
            />
          ) : (
            repoScans.map(({ repoUrl, scan }) => (
              <Card className="bg-muted/50" key={repoUrl}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold">{repoUrl}</p>
                      {scan ? (
                        <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                          <Badge
                            color={
                              scan.status === 'completed'
                                ? 'success'
                                : scan.status === 'failed'
                                  ? 'danger'
                                  : 'warning'
                            }
                            variant="flat"
                          >
                            {scan.status}
                          </Badge>
                          <span>{scan.total_findings} findings</span>
                          <span>
                            Quality:{' '}
                            <span
                              className={
                                qualityTone(scan.quality_score) === 'success'
                                  ? 'text-success'
                                  : qualityTone(scan.quality_score) === 'danger'
                                    ? 'text-danger'
                                    : ''
                              }
                            >
                              {scan.quality_score?.toFixed(1) ?? 'N/A'}
                            </span>
                          </span>
                          {scan.quality_gate_passed === false ? (
                            <Badge color="danger" variant="dot">
                              Gate failed
                            </Badge>
                          ) : scan.quality_gate_passed === true ? (
                            <Badge color="success" variant="dot">
                              Gate passed
                            </Badge>
                          ) : null}
                        </div>
                      ) : (
                        <p className="mt-1 text-xs text-muted-foreground">No scan data</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <Button asChild color="primary" size="sm" variant="flat">
                        <Link to="/scans/new" search={{ repo: repoUrl, projectKey }}>
                          <Play size={14} />
                          Run Scan
                        </Link>
                      </Button>
                      {scan ? (
                        <Button asChild isIconOnly size="sm" variant="light">
                          <Link to="/scans/$scanId" params={{ scanId: String(scan.id) }}>
                            <ArrowRight size={14} />
                          </Link>
                        </Button>
                      ) : null}
                      {canManageProject ? (
                        <Button
                          color="danger"
                          isIconOnly
                          size="sm"
                          variant="flat"
                          onClick={() => setRepoToRemove(repoUrl)}
                        >
                          <Trash2 size={14} />
                        </Button>
                      ) : null}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </CardContent>
      </Card>

      {/* Scan history per repo */}
      {repos.length > 0 ? (
        <Card>
          <CardHeader className="px-6 pt-5">
            <div>
              <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
                History
              </p>
              <h2 className="text-lg font-semibold">Repository scan timeline</h2>
            </div>
          </CardHeader>
          <Separator />
          <CardContent className="space-y-4 p-6">
            {repos.map((repoUrl) => (
              <RepoTimeline key={repoUrl} repoUrl={repoUrl} />
            ))}
          </CardContent>
        </Card>
      ) : null}

      {/* Add repos modal */}
      <Dialog open={addRepoOpen} onOpenChange={(open) => {
        setAddRepoOpen(open)
        if (!open) {
          setAddRepoMode('manual')
          setNewRepos('')
          setSelectedGitHubRepoUrls(new Set())
        }
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Repositories</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <Tabs value={addRepoMode} onValueChange={(value) => setAddRepoMode(value as 'manual' | 'github-app')}>
              <TabsList>
                <TabsTrigger value="manual">Manual</TabsTrigger>
                <TabsTrigger value="github-app">GitHub App</TabsTrigger>
              </TabsList>
              <TabsContent value="manual">
                <div className="space-y-2 pt-2">
                  <Label>Repository URLs (one per line)</Label>
                  <Textarea
                    placeholder="https://dev.azure.com/org/project/_git/repo"
                    value={newRepos}
                    onChange={(e) => setNewRepos(e.target.value)}
                    rows={4}
                  />
                </div>
              </TabsContent>
              <TabsContent value="github-app">
                <div className="pt-2">
                  <GitHubAppRepoPicker
                    selectedRepoUrls={selectedGitHubRepoUrls}
                    onSelectionChange={setSelectedGitHubRepoUrls}
                    onInstallationChange={setSelectedGitHubInstallationId}
                    excludedRepoUrls={new Set(repos)}
                    installResult={githubInstallResult}
                  />
                </div>
              </TabsContent>
            </Tabs>
            {addRepoError ? <p className="text-sm text-danger">{addRepoError}</p> : null}
            {addRepoMutation.isError ? (
              <p className="text-sm text-danger">
                {addRepoMutation.error instanceof Error
                  ? addRepoMutation.error.message
                  : 'Failed to add repositories to this project.'}
              </p>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="flat" onClick={() => setAddRepoOpen(false)}>
              Cancel
            </Button>
            <Button
              color="primary"
              isLoading={addRepoMutation.isPending}
              disabled={
                (addRepoMode === 'manual' && newRepos.trim().length === 0) ||
                (addRepoMode === 'github-app' && selectedGitHubRepoUrls.size === 0)
              }
              onClick={() => {
                const reposToAdd =
                  addRepoMode === 'manual'
                    ? newRepos
                        .split('\n')
                        .map((r) => r.trim())
                        .filter(Boolean)
                    : [...selectedGitHubRepoUrls]
                const repoValidationError = validateRepositoryUrls(reposToAdd)
                if (repoValidationError) {
                  setAddRepoError(repoValidationError)
                  return
                }
                setAddRepoError(null)
                addRepoMutation.mutate({
                  githubInstallationId:
                    addRepoMode === 'github-app' && selectedGitHubInstallationId
                      ? selectedGitHubInstallationId
                      : undefined,
                  repos: reposToAdd,
                })
              }}
            >
              Add
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={repoToRemove !== null} onOpenChange={(open) => !open && setRepoToRemove(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove Repository</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              Remove this repository from <span className="font-semibold">{project.name}</span>?
            </p>
            {repoToRemove ? (
              <p className="rounded-sm border border-border bg-muted/50 px-3 py-2 font-mono text-xs">
                {repoToRemove}
              </p>
            ) : null}
            <p className="text-xs text-muted-foreground">
              Existing scans remain stored, but this repository will no longer be part of the project rollup.
            </p>
            {removeRepoMutation.isError ? (
              <p className="text-sm text-danger">
                {removeRepoMutation.error instanceof Error
                  ? removeRepoMutation.error.message
                  : 'Failed to remove repository.'}
              </p>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="flat" onClick={() => setRepoToRemove(null)}>
              Cancel
            </Button>
            <Button
              color="danger"
              isLoading={removeRepoMutation.isPending}
              onClick={() => {
                if (repoToRemove) {
                  removeRepoMutation.mutate(repoToRemove)
                }
              }}
            >
              Remove
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
