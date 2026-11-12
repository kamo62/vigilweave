import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  FolderOpen,
  Plus,
  Shield,
  Trash2,
  XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/EmptyState";
import { GitHubAppRepoPicker } from "@/components/GitHubAppRepoPicker";
import { SCMRepoPicker } from '@/components/SCMRepoPicker';
import { StatsCard } from "@/components/StatsCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { Spinner } from "@/components/ui/spinner";
import {
  createProject,
  deleteProject,
  fetchProjectMetrics,
  fetchProjects,
  fetchScans,
  fetchSCMConnections,
  fetchSCMOrganizations,
  fetchSCMRepositories,
  type ProjectPublic,
  type Scan,
  type SCMOrganization,
  type SCMRepository,
} from "@/lib/api";
import { useGitHubAppInstallResult } from '@/lib/hooks/useGitHubAppInstallResult';
import { validateRepositoryUrls } from '@/lib/repositories';
import { pickLatestScan } from "@/lib/scan-recency";
import { useAuth } from "@/lib/useAuth";
import { gradeColor, qualityGrade, securityGrade } from "@/lib/utils";

function GradeBadge({ grade }: { grade: string }) {
  const color =
    gradeColor[grade as keyof typeof gradeColor] ??
    "bg-default text-default-foreground";
  return (
    <span
      className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${color}`}
    >
      {grade}
    </span>
  );
}

function MetricRow({
  label,
  value,
  grade,
}: {
  label: string;
  value: string | number;
  grade: string;
}) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-sm text-muted-foreground">{label}</span>
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold">{value}</span>
        <GradeBadge grade={grade} />
      </div>
    </div>
  );
}

function ProjectCard({ project, canManage }: { project: ProjectPublic; canManage: boolean }) {
  const queryClient = useQueryClient();
  const [showDelete, setShowDelete] = useState(false);
  const [deleteScans, setDeleteScans] = useState(false);
  const projectName = project.name?.trim() || "Untitled Project";
  const projectKey = project.key?.trim() || "";
  const canOpenProject = projectKey.length > 0;
  const deleteMutation = useMutation({
    mutationFn: () =>
      deleteProject(projectKey, { deleteScans, projectId: project.id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      queryClient.invalidateQueries({ queryKey: ["scans"] });
      setShowDelete(false);
      setDeleteScans(false);
    },
  });

  const metricsQuery = useQuery({
    queryKey: ["project-metrics", project.id, projectKey],
    queryFn: () => fetchProjectMetrics(projectKey),
    enabled: canOpenProject,
  });
  const scansQuery = useQuery({
    queryKey: ["scans"],
    queryFn: fetchScans,
  });

  const metrics = metricsQuery.data;
  const gatePassed = metrics?.quality_gate_passed;
  const repoCount = metrics?.repo_count ?? project.repos?.length ?? 0;
  const secGrade = securityGrade(
    metrics?.critical_findings ?? 0,
    metrics?.high_findings ?? 0,
  );
  const qualGrade = qualityGrade(metrics?.avg_quality_score);

  // Find the latest scan for any repo in this project
  const repos = project.repos ?? [];
  const latestScan = pickLatestScan((scansQuery.data ?? []).filter((scan) => repos.includes(scan.repo)));

  const cardBody = (
    <>
      {/* Header: name + gate badge */}
      {canOpenProject ? (
        <Link
          to="/projects/$projectKey"
          params={{ projectKey }}
          className="block"
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              {project.tags && project.tags.length > 0 ? (
                <p className="truncate text-xs text-muted-foreground">
                  {project.tags.join(" · ")}
                </p>
              ) : null}
              <p className="truncate text-sm font-bold">{projectName}</p>
            </div>
            {gatePassed === true ? (
              <div className="flex items-center gap-1.5 text-success">
                <CheckCircle2 size={16} />
                <span className="text-xs font-semibold">Passed</span>
              </div>
            ) : gatePassed === false ? (
              <div className="flex items-center gap-1.5 text-danger">
                <XCircle size={16} />
                <span className="text-xs font-semibold">Failed</span>
              </div>
            ) : (
              <span className="text-xs text-muted-foreground">N/A</span>
            )}
          </div>

          {/* Subtitle: repo count */}
          <p className="text-xs text-muted-foreground">
            {repoCount} {repoCount === 1 ? "repository" : "repositories"}
            {project.description ? ` · ${project.description}` : ""}
          </p>

          {/* Metric rows */}
          <div className="mt-1 divide-y divide-border">
            <MetricRow
              grade={secGrade}
              label="Security"
              value={metrics?.critical_findings ?? 0}
            />
            <MetricRow
              grade={qualGrade}
              label="Quality"
              value={metrics?.avg_quality_score?.toFixed(1) ?? "N/A"}
            />
            <MetricRow
              grade={
                (metrics?.total_findings ?? 0) === 0
                  ? "A"
                  : (metrics?.total_findings ?? 0) <= 10
                    ? "B"
                    : (metrics?.total_findings ?? 0) <= 50
                      ? "C"
                      : (metrics?.total_findings ?? 0) <= 100
                        ? "D"
                        : "E"
              }
              label="Total Findings"
              value={metrics?.total_findings ?? 0}
            />
          </div>
        </Link>
      ) : (
        <div className="block">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              {project.tags && project.tags.length > 0 ? (
                <p className="truncate text-xs text-muted-foreground">
                  {project.tags.join(" · ")}
                </p>
              ) : null}
              <p className="truncate text-sm font-bold">{projectName}</p>
            </div>
            <span className="text-xs text-amber-700">Missing project key</span>
          </div>
          <p className="text-xs text-muted-foreground">
            {repoCount} {repoCount === 1 ? "repository" : "repositories"}
            {project.description ? ` · ${project.description}` : ""}
          </p>
          <div className="mt-1 divide-y divide-border">
            <MetricRow
              grade={secGrade}
              label="Security"
              value={metrics?.critical_findings ?? 0}
            />
            <MetricRow
              grade={qualGrade}
              label="Quality"
              value={metrics?.avg_quality_score?.toFixed(1) ?? "N/A"}
            />
            <MetricRow
              grade={
                (metrics?.total_findings ?? 0) === 0
                  ? "A"
                  : (metrics?.total_findings ?? 0) <= 10
                    ? "B"
                    : (metrics?.total_findings ?? 0) <= 50
                      ? "C"
                      : (metrics?.total_findings ?? 0) <= 100
                        ? "D"
                        : "E"
              }
              label="Total Findings"
              value={metrics?.total_findings ?? 0}
            />
          </div>
        </div>
      )}

      {/* Footer: latest scan + delete */}
      <div className="mt-3 flex items-center justify-between border-t border-border pt-3">
          {latestScan ? (
            <>
              <span className="text-[11px] text-muted-foreground">
                Latest: Scan #{latestScan.id} &middot;{" "}
                {latestScan.total_findings} findings
              </span>
              <div className="flex items-center gap-1">
                {canManage ? (
                  <Button
                    isIconOnly
                    size="sm"
                    variant="light"
                    className="text-danger/60 hover:text-danger hover:bg-danger/10"
                    onClick={() => setShowDelete(true)}
                  >
                    <Trash2 size={14} />
                  </Button>
                ) : null}
                <Button asChild isIconOnly size="sm" variant="light">
                  <Link
                    to="/scans/$scanId"
                    params={{ scanId: String(latestScan.id) }}
                  >
                    <ArrowRight size={14} />
                  </Link>
                </Button>
              </div>
            </>
          ) : (
            <>
              <span className="text-[11px] text-muted-foreground">
                No scans yet
              </span>
              {canManage ? (
                <Button
                  isIconOnly
                  size="sm"
                  variant="light"
                  className="text-danger/60 hover:text-danger hover:bg-danger/10"
                  onClick={() => setShowDelete(true)}
                >
                  <Trash2 size={14} />
                </Button>
              ) : null}
            </>
          )}
      </div>

      <Dialog
          open={showDelete}
          onOpenChange={(open) => {
            setShowDelete(open);
            if (!open) setDeleteScans(false);
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete &ldquo;{projectName}&rdquo;</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-muted-foreground">
              This will permanently delete the project. This action cannot be
              undone.
            </p>
            <label className="flex items-center gap-2 rounded-sm border border-border p-3 cursor-pointer hover:bg-accent/50">
              <Checkbox
                checked={deleteScans}
                onCheckedChange={(checked) => setDeleteScans(checked === true)}
              />
              <div>
                <p className="text-sm font-medium">Also delete all scans</p>
                <p className="text-xs text-muted-foreground">
                  Remove all scans for the {project.repos?.length ?? 0} linked{" "}
                  {(project.repos?.length ?? 0) === 1
                    ? "repository"
                    : "repositories"}{" "}
                  and their findings.
                </p>
              </div>
            </label>
            {deleteMutation.isError ? (
              <p className="text-sm text-danger">
                {deleteMutation.error instanceof Error
                  ? deleteMutation.error.message
                  : 'Failed to delete project. Try again, or refresh and retry if this is a legacy blank-key project.'}
              </p>
            ) : null}
            <DialogFooter>
              <Button variant="flat" onClick={() => setShowDelete(false)}>
                Cancel
              </Button>
              <Button
                color="danger"
                isLoading={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate()}
              >
                {deleteScans ? "Delete Project & Scans" : "Delete Project"}
              </Button>
            </DialogFooter>
          </DialogContent>
      </Dialog>
    </>
  );

  return (
    <Card className="transition-colors hover:border-foreground/20">
      <CardContent className="gap-3 p-5">{cardBody}</CardContent>
    </Card>
  );
}

export function ProjectsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [preferredCreateTab, setPreferredCreateTab] = useState<'manual' | 'import' | 'github-app'>('manual');
  const githubInstallResult = useGitHubAppInstallResult()
  const [newKey, setNewKey] = useState("");
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newTags, setNewTags] = useState("");
  const [newRepos, setNewRepos] = useState("");

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: fetchProjects,
  });

  const scansQuery = useQuery({
    queryKey: ["scans"],
    queryFn: fetchScans,
  });

  const createMutation = useMutation({
    mutationFn: createProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setOpen(false);
      setNewKey("");
      setNewName("");
      setNewDescription("");
      setNewTags("");
      setNewRepos("");
    },
  });

  const projects = projectsQuery.data ?? [];
  const scans = scansQuery.data ?? [];
  const canManageProjects = user?.role === 'admin';

  useEffect(() => {
    if (!githubInstallResult) {
      return;
    }

    setOpen(true);
    setPreferredCreateTab('github-app');
  }, [githubInstallResult]);

  if (projectsQuery.isLoading && !projectsQuery.data) {
    return (
      <div className="flex justify-center py-20">
        <Spinner label="Loading projects..." />
      </div>
    );
  }

  if (projectsQuery.isError) {
    return (
      <EmptyState
        title="Projects unavailable"
        body="The project list could not be loaded. Refresh the page and verify the API is reachable."
      />
    );
  }

  // Calculate aggregate stats
  const totalProjects = projects.length;

  const trackedRepos = new Set(
    projects.flatMap((project) => project.repos ?? []),
  );
  const latestCompletedScansByRepo = new Map<string, Scan>();
  for (const scan of scans) {
    if (!trackedRepos.has(scan.repo) || scan.status !== "completed") {
      continue;
    }
    const currentLatest = latestCompletedScansByRepo.get(scan.repo);
    if (!currentLatest || pickLatestScan([currentLatest, scan])?.id === scan.id) {
      latestCompletedScansByRepo.set(scan.repo, scan);
    }
  }

  const currentProjectScans = [...latestCompletedScansByRepo.values()];
  const activeFindings = currentProjectScans.reduce((total, scan) => {
    return total + (scan.total_findings ?? 0);
  }, 0);

  const passedScans = currentProjectScans.filter(
    (scan) => scan.quality_gate_passed === true,
  );
  const securityScore =
    currentProjectScans.length > 0
      ? Math.round((passedScans.length / currentProjectScans.length) * 100)
      : 0;

  // Find most recent scan timestamp
  const projectScans = scans.filter((scan) => trackedRepos.has(scan.repo));
  const lastScanDate =
    projectScans.length > 0
      ? projectScans.reduce((latest, scan) => {
          const scanDate = new Date(scan.started_at);
          return scanDate > latest ? scanDate : latest;
        }, new Date(0))
      : null;

  const formatLastScan = (date: Date | null) => {
    if (!date || date.getTime() === 0) return "No scans yet";
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Projects</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Explore projects to see aggregate code health across repositories.
          </p>
        </div>
        {canManageProjects ? (
          <Button color="primary" onClick={() => {
            setPreferredCreateTab('manual')
            setOpen(true)
          }}>
            <Plus size={16} />
            New Project
          </Button>
        ) : null}
      </div>

      {scansQuery.isError ? (
        <div className="rounded-sm border border-warning/30 bg-warning/5 px-4 py-3 text-sm text-warning">
          Scan summaries could not be loaded. Project inventory is still available, but latest-scan rollups may be incomplete.
        </div>
      ) : null}

      {githubInstallResult ? (
        <div className={`rounded-sm border px-4 py-3 text-sm ${githubInstallResult.connected ? 'border-success/30 bg-success/[0.06] text-success' : 'border-danger/30 bg-danger/[0.06] text-danger'}`}>
          {githubInstallResult.message}
        </div>
      ) : null}

      {projects.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatsCard
            title="Total Projects"
            value={totalProjects}
            icon={FolderOpen}
          />
          <StatsCard
            title="Active Findings"
            value={activeFindings.toLocaleString()}
            icon={Activity}
          />
          <StatsCard
            title="Security Score"
            value={`${securityScore}%`}
            icon={Shield}
            progress={{ value: securityScore, showValue: false }}
          />
          <StatsCard
            title="Last Scan"
            value={formatLastScan(lastScanDate)}
            icon={Activity}
          />
        </div>
      )}

      {projects.length === 0 ? (
        <EmptyState
          body={canManageProjects
            ? "Create a project to group repositories and track aggregate quality metrics."
            : "No projects are visible yet for this tenant. Ask an administrator to create one or link repositories."}
          title="No projects yet"
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} canManage={canManageProjects} />
          ))}
        </div>
      )}

      {canManageProjects ? (
        <CreateProjectDialog
          open={open}
          onOpenChange={setOpen}
          createMutation={createMutation}
          newKey={newKey}
          setNewKey={setNewKey}
          newName={newName}
          setNewName={setNewName}
          newDescription={newDescription}
          setNewDescription={setNewDescription}
          newTags={newTags}
          setNewTags={setNewTags}
          newRepos={newRepos}
          setNewRepos={setNewRepos}
          initialTab={preferredCreateTab}
          githubInstallResult={githubInstallResult}
        />
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Create Project Dialog — Manual + Import from SCM
// ---------------------------------------------------------------------------

function CreateProjectDialog({
  open,
  onOpenChange,
  createMutation,
  newKey,
  setNewKey,
  newName,
  setNewName,
  newDescription,
  setNewDescription,
  newTags,
  setNewTags,
  newRepos,
  setNewRepos,
  initialTab,
  githubInstallResult,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  createMutation: ReturnType<typeof useMutation<ProjectPublic, Error, Parameters<typeof createProject>[0]>>;
  newKey: string;
  setNewKey: (v: string) => void;
  newName: string;
  setNewName: (v: string) => void;
  newDescription: string;
  setNewDescription: (v: string) => void;
  newTags: string;
  setNewTags: (v: string) => void;
  newRepos: string;
  setNewRepos: (v: string) => void;
  initialTab: 'manual' | 'import' | 'github-app';
  githubInstallResult: { connected: boolean; message: string } | null;
}) {
  const [tab, setTab] = useState<string>(initialTab);

  // SCM import state
  const [selectedConnectionId, setSelectedConnectionId] = useState<string>("");
  const [selectedOrg, setSelectedOrg] = useState<string>("");
  const [scmRepos, setScmRepos] = useState<SCMRepository[]>([]);
  const [selectedRepoUrls, setSelectedRepoUrls] = useState<Set<string>>(new Set());
  const [selectedGitHubRepoUrls, setSelectedGitHubRepoUrls] = useState<Set<string>>(new Set());
  const [selectedGitHubInstallationId, setSelectedGitHubInstallationId] = useState<number | null>(null)
  const [loadingOrgs, setLoadingOrgs] = useState(false);
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [scmError, setScmError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [orgs, setOrgs] = useState<SCMOrganization[]>([]);

  const connectionsQuery = useQuery({
    queryKey: ["scm-connections"],
    queryFn: fetchSCMConnections,
    enabled: open,
  });

  const connections = connectionsQuery.data ?? [];

  useEffect(() => {
    if (open) {
      return;
    }
    setTab('manual');
    setSelectedConnectionId('');
    setSelectedOrg('');
    setScmRepos([]);
    setSelectedRepoUrls(new Set());
    setSelectedGitHubRepoUrls(new Set());
    setSelectedGitHubInstallationId(null)
    setScmError(null)
    setFormError(null)
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    setTab(initialTab)
  }, [initialTab, open])

  async function handleConnectionChange(connId: string) {
    setSelectedConnectionId(connId);
    setSelectedOrg("");
    setScmRepos([]);
    setSelectedRepoUrls(new Set());
    setScmError(null)

    if (!connId) return;
    setLoadingOrgs(true);
    try {
      const data = await fetchSCMOrganizations(Number(connId));
      setOrgs(data);
    } catch (error) {
      setOrgs([]);
      setScmError(error instanceof Error ? error.message : 'Failed to load SCM organizations.')
    } finally {
      setLoadingOrgs(false);
    }
  }

  async function handleOrgChange(org: string) {
    setSelectedOrg(org);
    setScmRepos([]);
    setSelectedRepoUrls(new Set());
    setScmError(null)

    if (!selectedConnectionId) return;
    setLoadingRepos(true);
    try {
      const data = await fetchSCMRepositories(Number(selectedConnectionId), org);
      setScmRepos(data);
    } catch (error) {
      setScmRepos([]);
      setScmError(error instanceof Error ? error.message : 'Failed to load SCM repositories.')
    } finally {
      setLoadingRepos(false);
    }
  }

  function handleCreate() {
    const reposList =
      tab === "manual"
        ? newRepos
            .split("\n")
            .map((r) => r.trim())
            .filter(Boolean)
        : tab === 'import'
          ? [...selectedRepoUrls]
          : [...selectedGitHubRepoUrls];

    const repoValidationError = validateRepositoryUrls(reposList)
    if (repoValidationError) {
      setFormError(repoValidationError)
      return
    }

    setFormError(null)

    createMutation.mutate({
      key: newKey.trim(),
      name: newName.trim(),
      description: newDescription.trim() || undefined,
      default_branch: "main",
      tags: newTags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      repos: reposList,
      scm_connection_id: tab === "import" && selectedConnectionId ? Number(selectedConnectionId) : undefined,
      github_installation_id:
        tab === 'github-app' && selectedGitHubInstallationId
          ? selectedGitHubInstallationId
          : undefined,
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Create Project</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          {/* Common fields */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Key *</Label>
              <Input
                placeholder="platform-api"
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Name *</Label>
              <Input
                placeholder="Platform API"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Description</Label>
            <Input
              placeholder="Optional description"
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label>Tags (comma-separated)</Label>
            <Input
              placeholder="backend, api"
              value={newTags}
              onChange={(e) => setNewTags(e.target.value)}
            />
          </div>

          {/* Repository source tabs */}
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList>
              <TabsTrigger value="manual">Manual</TabsTrigger>
              <TabsTrigger value="import">Import from SCM</TabsTrigger>
              <TabsTrigger value="github-app">GitHub App</TabsTrigger>
            </TabsList>

            <TabsContent value="manual">
              <div className="space-y-2 pt-2">
                <Label>Repository URLs (one per line)</Label>
                <Textarea
                  placeholder="https://dev.azure.com/org/project/_git/repo"
                  value={newRepos}
                  onChange={(e) => setNewRepos(e.target.value)}
                  rows={3}
                />
              </div>
            </TabsContent>

            <TabsContent value="import">
              <div className="space-y-3 pt-2">
                <SCMRepoPicker
                  connections={connections}
                  selectedConnectionId={selectedConnectionId}
                  onConnectionChange={handleConnectionChange}
                  selectedOrg={selectedOrg}
                  onOrgChange={handleOrgChange}
                  orgs={orgs}
                  repositories={scmRepos}
                  selectedRepoUrls={selectedRepoUrls}
                  onSelectionChange={setSelectedRepoUrls}
                  connectionsLoading={connectionsQuery.isLoading}
                  connectionsError={connectionsQuery.isError ? 'Failed to load SCM connections. Refresh and verify the API is reachable.' : null}
                  organizationsLoading={loadingOrgs}
                  repositoriesLoading={loadingRepos}
                  repositoriesError={scmError}
                  emptyConnectionsContent={(
                    <p className="text-sm text-muted-foreground">
                      No SCM connections configured.{" "}
                      <Link to="/settings" search={{ tab: 'connections' }} className="text-primary underline">
                        Add one in Settings → Connections
                      </Link>
                    </p>
                  )}
                />
              </div>
            </TabsContent>

            <TabsContent value="github-app">
                <div className="pt-2">
                  <GitHubAppRepoPicker
                    selectedRepoUrls={selectedGitHubRepoUrls}
                    onSelectionChange={setSelectedGitHubRepoUrls}
                    onInstallationChange={setSelectedGitHubInstallationId}
                    installResult={githubInstallResult}
                  />
                </div>
              </TabsContent>
          </Tabs>

          {formError ? <p className="text-sm text-danger">{formError}</p> : null}

          {createMutation.isError ? (
            <p className="text-sm text-danger">
              {createMutation.error instanceof Error
                ? createMutation.error.message
                : 'Failed to create project. Check the key is unique.'}
            </p>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="flat" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            color="primary"
            isLoading={createMutation.isPending}
            disabled={
              !newKey.trim() ||
              !newName.trim() ||
              (tab === 'import' && selectedRepoUrls.size === 0) ||
              (tab === 'github-app' && selectedGitHubRepoUrls.size === 0)
            }
            onClick={handleCreate}
          >
            Create
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
