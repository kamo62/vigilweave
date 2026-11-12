import type { JSX } from "react";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearch } from "@tanstack/react-router";
import {
  CheckCircle2,
  ChevronRight,
  Loader2,
  Scan,
  Shield,
} from "lucide-react";

import { SCMConnectionForm } from "../components/SCMConnectionForm";
import { GitHubAppRepoPicker } from "../components/GitHubAppRepoPicker";
import { SCMRepoPicker } from "../components/SCMRepoPicker";
import { Button } from "../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Spinner } from "../components/ui/spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { useGitHubAppInstallResult } from "../lib/hooks/useGitHubAppInstallResult";
import { useAuth } from "../lib/useAuth";
import {
  createSCMConnection,
  createProject,
  createScan,
  fetchIntegrationsSetup,
  fetchSCMConnections,
  fetchSCMOrganizations,
  fetchSCMRepositories,
  fetchScan,
  updateCurrentUser,
} from "../lib/api";
import { normalizeNextPath } from "../lib/navigation";
import { validateRepositoryUrls } from '../lib/repositories'
import type {
  IntegrationsSetupResponse,
  ProjectCreate,
  SCMConnectionPublic,
  SCMOrganization,
  SCMRepository,
  ScanCreate,
} from "../lib/api";

interface Step {
  id: number;
  title: string;
  description: string;
}

const steps: Step[] = [
  { id: 0, title: "Welcome", description: "Get started with VigilWeave" },
  {
    id: 1,
    title: "Connect Repository",
    description: "Link your first repository",
  },
  { id: 2, title: "First Scan", description: "Run your initial security scan" },
  { id: 3, title: "Results", description: "Review your findings" },
  { id: 4, title: "Complete", description: "You are all set!" },
];

export function OnboardingPage(): JSX.Element {
  const navigate = useNavigate();
  const search = useSearch({ from: "/onboarding" });
  const { user, refreshUser, sessionAuthProvider } = useAuth();
  const githubInstallResult = useGitHubAppInstallResult();
  const [currentStep, setCurrentStep] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [repoMode, setRepoMode] = useState<"manual" | "import" | "github_app">("manual");
  const [repoUrl, setRepoUrl] = useState("");
  const [repoBranch, setRepoBranch] = useState("main");
  const [projectKey, setProjectKey] = useState("");
  const [, setScanId] = useState<number | null>(null);
  const [scanStatus, setScanStatus] = useState<
    "idle" | "running" | "completed" | "failed"
  >("idle");
  const [findingsCount, setFindingsCount] = useState(0);
  const [connectError, setConnectError] = useState<string | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  const [connections, setConnections] = useState<SCMConnectionPublic[]>([]);
  const [connectionsLoading, setConnectionsLoading] = useState(false);
  const [connectionsError, setConnectionsError] = useState<string | null>(null);
  const [loadingOrgs, setLoadingOrgs] = useState(false);
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [scmError, setScmError] = useState<string | null>(null);
  const [selectedConnectionId, setSelectedConnectionId] = useState("");
  const [selectedOrg, setSelectedOrg] = useState("");
  const [orgs, setOrgs] = useState<SCMOrganization[]>([]);
  const [scmRepos, setScmRepos] = useState<SCMRepository[]>([]);
  const [selectedRepoUrl, setSelectedRepoUrl] = useState("");
  const [showConnectionForm, setShowConnectionForm] = useState(false);
  const [integrationsSetup, setIntegrationsSetup] =
    useState<IntegrationsSetupResponse | null>(null);
  const [integrationsLoading, setIntegrationsLoading] = useState(false);
  const [integrationsError, setIntegrationsError] = useState<string | null>(null);
  const [selectedGitHubInstallationId, setSelectedGitHubInstallationId] = useState<number | null>(null);
  const [selectedGitHubRepoUrls, setSelectedGitHubRepoUrls] = useState<Set<string>>(new Set());
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const scanStatusRef = useRef(scanStatus);
  scanStatusRef.current = scanStatus;

  const getScanFailureMessage = (metadata: unknown): string | null => {
    if (!metadata || typeof metadata !== "object") {
      return null;
    }

    const error = (metadata as { error?: unknown }).error;
    return typeof error === "string" && error.trim().length > 0 ? error : null;
  };

  const clearScanPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
  };

  // Redirect users who have already completed onboarding
  useEffect(() => {
    if (sessionAuthProvider !== "workos") {
      void navigate({ to: "/projects" });
      return
    }
    if (user?.onboarding_completed) {
      window.location.replace(normalizeNextPath(search.next));
    }
  }, [navigate, search.next, sessionAuthProvider, user?.onboarding_completed]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
      }
      if (pollTimeoutRef.current) {
        clearTimeout(pollTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (search.repoMode === "github_app") {
      setRepoMode("github_app");
      setCurrentStep(1);
    }
  }, [search.repoMode]);

  useEffect(() => {
    if (currentStep !== 1 || repoMode !== "import") {
      return;
    }
    void loadConnections();
  }, [currentStep, repoMode]);

  useEffect(() => {
    if (currentStep !== 1 || repoMode !== "github_app") {
      return;
    }
    void loadGitHubAppSetup();
  }, [currentStep, repoMode]);

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleBack = () => {
    if (currentStep === 2) {
      clearScanPolling();
      setIsLoading(false);
      setScanStatus("idle");
      setScanError(null);
    }
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleSkip = () => {
    completeOnboarding();
  };

  const completeOnboarding = async () => {
    try {
      await updateCurrentUser({ onboarding_completed: true });
      await refreshUser();
      window.location.assign(normalizeNextPath(search.next));
    } catch (error) {
      console.error("Failed to complete onboarding:", error);
    }
  };

  const loadConnections = async () => {
    setConnectionsLoading(true);
    setConnectionsError(null);
    try {
      const data = await fetchSCMConnections();
      setConnections(data);
      if (data.length === 0) {
        setShowConnectionForm(true);
      }
    } catch (error) {
      console.error("Failed to load SCM connections:", error);
      setConnectionsError(
        "Failed to load SCM connections. You can still connect a public repository by URL.",
      );
    } finally {
      setConnectionsLoading(false);
    }
  };

  const loadGitHubAppSetup = async () => {
    setIntegrationsLoading(true);
    setIntegrationsError(null);

    try {
      const setup = await fetchIntegrationsSetup();
      setIntegrationsSetup(setup);
    } catch (error) {
      console.error("Failed to load GitHub App setup:", error);
      setIntegrationsError(
        "Failed to load GitHub App onboarding details. You can still connect repositories with a PAT-backed SCM connection.",
      );
    } finally {
      setIntegrationsLoading(false);
    }
  };

  const handleCreateConnection = async (payload: Parameters<typeof createSCMConnection>[0]) => {
    const connection = await createSCMConnection(payload)
    await loadConnections()
    setShowConnectionForm(false)
    await handleConnectionChange(String(connection.id))
  }

  const handleConnectionChange = async (connectionId: string) => {
    setSelectedConnectionId(connectionId);
    setSelectedOrg("");
    setOrgs([]);
    setScmRepos([]);
    setSelectedRepoUrl("");
    setScmError(null);

    if (!connectionId) {
      return;
    }

    setLoadingOrgs(true);
    try {
      const data = await fetchSCMOrganizations(Number(connectionId));
      setOrgs(data);
    } catch (error) {
      console.error("Failed to load SCM organizations:", error);
      setScmError(
        "Failed to load organizations for this connection. Check the token scopes and try again.",
      );
    } finally {
      setLoadingOrgs(false);
    }
  };

  const handleOrgChange = async (org: string) => {
    setSelectedOrg(org);
    setScmRepos([]);
    setSelectedRepoUrl("");
    setScmError(null);

    if (!selectedConnectionId) {
      return;
    }

    setLoadingRepos(true);
    try {
      const data = await fetchSCMRepositories(Number(selectedConnectionId), org);
      setScmRepos(data);
    } catch (error) {
      console.error("Failed to load SCM repositories:", error);
      setScmError(
        "Failed to load repositories for this connection. Confirm that the token can read the repositories you want to scan.",
      );
    } finally {
      setLoadingRepos(false);
    }
  };

  const handleConnectRepo = async () => {
    const trimmedProjectKey = projectKey.trim();
    const selectedRepo =
      repoMode === "manual"
        ? repoUrl.trim()
        : repoMode === "import"
          ? scmRepos.find((repo) => repo.clone_url === selectedRepoUrl)?.clone_url ?? ""
          : Array.from(selectedGitHubRepoUrls)[0] ?? "";

    if (!trimmedProjectKey || !selectedRepo) {
      return;
    }

    const repoValidationError = validateRepositoryUrls([selectedRepo])
    if (repoValidationError) {
      setConnectError(repoValidationError)
      return
    }

    setIsLoading(true);
    setConnectError(null);
    try {
      const importedRepo =
        repoMode === "import"
          ? scmRepos.find((repo) => repo.clone_url === selectedRepo)
          : undefined;
      const defaultBranch = importedRepo?.default_branch || repoBranch || "main";
      const projectData: ProjectCreate = {
        key: trimmedProjectKey,
        name: trimmedProjectKey,
        default_branch: defaultBranch,
        repos: [selectedRepo],
        scm_connection_id:
          repoMode === "import" && selectedConnectionId
            ? Number(selectedConnectionId)
            : undefined,
        github_installation_id:
          repoMode === "github_app" && selectedGitHubInstallationId
            ? selectedGitHubInstallationId
            : undefined,
      };
      await createProject(projectData);

      setProjectKey(trimmedProjectKey);
      setRepoUrl(selectedRepo);
      setRepoBranch(defaultBranch);

      handleNext();
    } catch (error) {
      console.error("Failed to connect repository:", error);
      setConnectError(
        error instanceof Error
          ? error.message
          : repoMode === "manual"
            ? "Failed to connect repository. Check the URL and project key, then try again."
            : repoMode === "import"
              ? "Failed to connect repository. Verify the selected connection and repository, then try again."
              : "Failed to connect repository. Verify the GitHub App installation and repository, then try again.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleStartScan = async () => {
    setIsLoading(true);
    setScanStatus("running");
    setScanError(null);

    try {
      // Start scan
      const scanData: ScanCreate = {
        repo: repoUrl,
        project_key: projectKey.trim(),
        branch: repoBranch || "main",
        scan_type: "fast",
        include_quality_metrics: true,
      };
      const scan = await createScan(scanData);
      setScanId(scan.id);

      // Poll for completion using ref for stable access
      pollRef.current = setInterval(async () => {
        try {
          const scanData = await fetchScan(scan.id);

          if (scanData.status === "completed") {
            clearScanPolling();
            setScanStatus("completed");
            setFindingsCount(scanData.total_findings || 0);
            setIsLoading(false);
            handleNext();
          } else if (scanData.status === "failed") {
            clearScanPolling();
            setScanStatus("failed");
            setScanError(
              getScanFailureMessage(scanData.scan_metadata) ??
                "The scan failed. You can retry here or continue in the Scans page.",
            );
            setIsLoading(false);
          }
        } catch (error) {
          console.error("Failed to poll scan status:", error);
          clearScanPolling();
          setScanStatus("failed");
          setScanError(
            error instanceof Error
              ? error.message
              : "The scan status could not be refreshed. Continue from the Scans page once it finishes.",
          );
          setIsLoading(false);
        }
      }, 2000);

      // Timeout after 5 minutes
      pollTimeoutRef.current = setTimeout(() => {
        clearScanPolling();
        if (scanStatusRef.current === "running") {
          setScanStatus("failed");
          setScanError(
            "The scan is taking longer than expected. You can continue from the Scans page once it finishes.",
          );
          setIsLoading(false);
        }
      }, 300000);
    } catch (error) {
      console.error("Failed to start scan:", error);
      setScanStatus("failed");
      setScanError(
        error instanceof Error ? error.message : "Failed to start the scan. Please try again.",
      );
      setIsLoading(false);
    }
  };

  const renderStepContent = () => {
    const githubMissingRequirements =
      integrationsSetup?.github.missing_requirements ?? [];

    switch (currentStep) {
      case 0:
        return (
          <div className="text-center py-8">
            <div className="w-20 h-20 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-6">
              <Shield className="h-10 w-10 text-primary" />
            </div>
            <h2 className="text-2xl font-bold mb-4">
              Welcome to VigilWeave, {user?.name || user?.email}!
            </h2>
            <p className="text-muted-foreground mb-8 max-w-md mx-auto">
              Let us get you set up in just a few steps. We will connect your
              first repository, run a security scan, and show you how VigilWeave
              works.
            </p>
            <div className="flex gap-4 justify-center">
              <Button size="lg" onClick={handleNext}>
                Get Started
                <ChevronRight className="ml-2 h-4 w-4" />
              </Button>
              <Button size="lg" variant="ghost" onClick={handleSkip}>
                Skip for now
              </Button>
            </div>
          </div>
        );

      case 1:
        return (
            <div className="py-4">
              <div className="flex items-center gap-3 mb-6">
                <Shield className="h-8 w-8 text-primary" />
                <div>
                  <h2 className="text-xl font-semibold">Connect a Repository</h2>
                  <p className="text-muted-foreground text-sm">
                  Use a direct URL for public repos, or import from an SCM
                  connection for private repos.
                </p>
              </div>
            </div>

            <div className="space-y-4">
              <Tabs
                value={repoMode}
                onValueChange={(value) =>
                  setRepoMode(value as "manual" | "import" | "github_app")
                }
              >
                <TabsList>
                  <TabsTrigger value="manual">Public repo URL</TabsTrigger>
                  <TabsTrigger value="import">Private repo via SCM</TabsTrigger>
                  <TabsTrigger value="github_app">GitHub App</TabsTrigger>
                </TabsList>

                <TabsContent value="manual" className="space-y-3">
                  <p className="text-sm text-muted-foreground">
                    Use this when the repository is publicly accessible. Private
                    repositories should use the SCM import path so scans can
                    clone with stored credentials.
                  </p>
                  <div className="max-w-md">
                    <Label htmlFor="repo-url">Repository URL</Label>
                    <Input
                      id="repo-url"
                      placeholder="https://github.com/username/repo"
                      value={repoUrl}
                      onChange={(e) => setRepoUrl(e.target.value)}
                    />
                  </div>
                </TabsContent>

                <TabsContent value="import" className="space-y-4">
                  <p className="text-sm text-muted-foreground">
                    Use a PAT-backed SCM connection to browse and select a
                    private repository without typing its clone URL manually.
                  </p>

                  <div className="rounded-sm border border-border bg-muted/20 p-4 space-y-4">
                    <div className="flex flex-wrap items-center gap-3 justify-between">
                      <div>
                        <p className="text-sm font-medium">SCM connections</p>
                        <p className="text-xs text-muted-foreground">
                          Reuse an existing connection or create one now.
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        type="button"
                        onClick={() => setShowConnectionForm((value) => !value)}
                      >
                        {showConnectionForm ? "Hide connection form" : "Add PAT connection"}
                      </Button>
                    </div>

                    {showConnectionForm ? (
                      <SCMConnectionForm
                        key={showConnectionForm ? 'onboarding-connection-open' : 'onboarding-connection-closed'}
                        onSubmit={handleCreateConnection}
                        onCancel={() => setShowConnectionForm(false)}
                      />
                    ) : null}

                    <SCMRepoPicker
                      connections={connections}
                      selectedConnectionId={selectedConnectionId}
                      onConnectionChange={handleConnectionChange}
                      selectedOrg={selectedOrg}
                      onOrgChange={handleOrgChange}
                      orgs={orgs}
                      repositories={scmRepos}
                      selectedRepoUrls={selectedRepoUrl ? new Set([selectedRepoUrl]) : new Set()}
                      onSelectionChange={(next) => setSelectedRepoUrl(Array.from(next)[0] ?? "")}
                      selectionMode="single"
                      connectionsLoading={connectionsLoading}
                      connectionsError={connectionsError}
                      organizationsLoading={loadingOrgs}
                      repositoriesLoading={loadingRepos}
                      repositoriesError={scmError}
                      emptyConnectionsContent={
                        showConnectionForm ? null : (
                          <p className="text-sm text-muted-foreground">
                            No SCM connections are configured yet. Add one now or continue with a public repository URL.
                          </p>
                        )
                      }
                    />
                  </div>
                </TabsContent>

                <TabsContent value="github_app" className="space-y-4">
                  <p className="text-sm text-muted-foreground">
                    Use the GitHub App when you want repo access without storing
                    a personal access token. Install the app for your GitHub
                    organization or account, then choose a repository below.
                  </p>

                  <div className="rounded-sm border border-border bg-muted/20 p-4 space-y-4">
                    {integrationsLoading ? (
                      <p className="text-sm text-muted-foreground">
                        Loading GitHub App setup...
                      </p>
                    ) : null}

                    {integrationsError ? (
                      <p className="text-sm text-destructive">{integrationsError}</p>
                    ) : null}

                    {integrationsSetup ? (
                      <>
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="text-sm font-medium">GitHub App status</p>
                            <p className="text-xs text-muted-foreground">
                              Install the app once per GitHub account or organization,
                              then choose repositories without using PATs.
                            </p>
                          </div>
                          <div className="rounded-sm border border-border bg-background px-3 py-2 text-xs text-muted-foreground">
                            Tenant: {integrationsSetup.github.tenant_slug}
                          </div>
                        </div>

                        <div className="grid gap-3 md:grid-cols-2">
                          <div className="rounded-sm border border-border bg-background p-3">
                            <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                              Setup URL
                            </p>
                            <p className="mt-1 break-all text-xs font-mono">
                              {integrationsSetup.github.setup_url || "Not configured"}
                            </p>
                          </div>
                          <div className="rounded-sm border border-border bg-background p-3">
                            <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                              Webhook URL
                            </p>
                            <p className="mt-1 break-all text-xs font-mono">
                              {integrationsSetup.github.webhook_url}
                            </p>
                          </div>
                        </div>

                        {githubMissingRequirements.length > 0 ? (
                          <div className="rounded-sm border border-amber-500/30 bg-amber-500/5 p-4">
                            <p className="text-sm font-medium text-amber-700">
                              GitHub App prerequisites are incomplete
                            </p>
                            <div className="mt-2 text-xs text-muted-foreground space-y-1">
                              {githubMissingRequirements.map((item) => (
                                <p key={item}>{item}</p>
                              ))}
                            </div>
                          </div>
                        ) : null}

                        <GitHubAppRepoPicker
                          selectedRepoUrls={selectedGitHubRepoUrls}
                          onSelectionChange={setSelectedGitHubRepoUrls}
                          selectionMode="single"
                          onInstallationChange={setSelectedGitHubInstallationId}
                          installResult={githubInstallResult}
                        />
                      </>
                    ) : null}
                  </div>
                </TabsContent>
              </Tabs>

              <div className="max-w-md">
                <Label htmlFor="project-key">Project Key</Label>
                <Input
                  id="project-key"
                  placeholder="my-project"
                  value={projectKey}
                  onChange={(e) => setProjectKey(e.target.value)}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  A unique identifier for your project (letters, numbers,
                  hyphens).
                </p>
              </div>
            </div>

            {connectError && (
              <p className="text-sm text-destructive mt-4">{connectError}</p>
            )}

            <div className="flex gap-4 mt-8">
              <Button variant="outline" onClick={handleBack} disabled={isLoading}>
                Back
              </Button>
              <Button
                onClick={handleConnectRepo}
                disabled={
                  isLoading ||
                  !projectKey.trim() ||
                  (repoMode === "manual"
                    ? !repoUrl.trim()
                    : repoMode === "import"
                      ? !selectedRepoUrl
                      : selectedGitHubRepoUrls.size === 0)
                }
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Connecting...
                  </>
                ) : (
                  <>
                    Connect Repository
                    <ChevronRight className="ml-2 h-4 w-4" />
                  </>
                )}
              </Button>
              <Button variant="ghost" onClick={handleSkip}>
                Skip
              </Button>
            </div>
          </div>
        );

      case 2:
        return (
          <div className="py-4 text-center">
            <div className="w-20 h-20 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-6">
              <Scan className="h-10 w-10 text-primary" />
            </div>
            <h2 className="text-2xl font-bold mb-4">Run Your First Scan</h2>
            <p className="text-muted-foreground mb-8 max-w-md mx-auto">
              We will run a fast security scan on your repository to detect
              vulnerabilities, secrets, and code quality issues.
            </p>

            {scanStatus === "running" ? (
              <div className="flex flex-col items-center gap-4">
                <Spinner className="h-12 w-12" />
                <p className="text-muted-foreground">Scanning repository...</p>
                <p className="text-xs text-muted-foreground">
                  This usually takes 1-2 minutes
                </p>
              </div>
             ) : (
               <div className="space-y-4">
                 <p className="text-sm text-muted-foreground">
                   Repository: <span className="font-medium text-foreground">{repoUrl}</span>
                 </p>
                 {scanError ? (
                   <p className="text-sm text-destructive">{scanError}</p>
                 ) : null}
                 <div className="flex gap-4 justify-center">
                   <Button size="lg" variant="outline" onClick={handleBack}>
                     Back to Repository
                   </Button>
                   <Button
                     size="lg"
                     onClick={handleStartScan}
                    disabled={isLoading}
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Starting...
                      </>
                    ) : (
                      scanStatus === "failed" ? "Retry Scan" : "Start Scan"
                    )}
                  </Button>
                  <Button size="lg" variant="ghost" onClick={handleSkip}>
                    Skip
                  </Button>
                </div>
              </div>
            )}
          </div>
        );

      case 3:
        return (
          <div className="py-4 text-center">
            <div className="w-20 h-20 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-6">
              <CheckCircle2 className="h-10 w-10 text-primary" />
            </div>
            <h2 className="text-2xl font-bold mb-4">Scan Complete!</h2>

            <Card className="max-w-md mx-auto mb-8">
              <CardContent className="pt-6">
                <div className="text-center">
                  <div className="text-4xl font-bold text-primary mb-2">
                    {findingsCount}
                  </div>
                  <p className="text-muted-foreground">
                    {findingsCount === 0
                      ? "No issues found! Great job!"
                      : "Potential issues detected"}
                  </p>
                </div>
              </CardContent>
            </Card>

            <p className="text-muted-foreground mb-8 max-w-md mx-auto">
              {findingsCount > 0
                ? "Review the findings in your dashboard and start triaging them."
                : "Your repository is looking secure. We will continue monitoring for new issues."}
            </p>

            <Button size="lg" onClick={handleNext}>
              Continue
              <ChevronRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        );

      case 4:
        return (
          <div className="py-4 text-center">
            <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <CheckCircle2 className="h-10 w-10 text-green-600" />
            </div>
            <h2 className="text-2xl font-bold mb-4">You are All Set!</h2>
            <p className="text-muted-foreground mb-8 max-w-md mx-auto">
              Your first repository is connected and scanned. You can now
              explore your dashboard, set up policies, and configure
              integrations.
            </p>

            <div className="flex gap-4 justify-center">
              <Button size="lg" onClick={completeOnboarding}>
                Go to Dashboard
              </Button>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/50 p-4">
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <div className="flex items-center justify-between mb-4">
            {steps.map((step, index) => (
              <div key={step.id} className="flex items-center">
                <div className="flex flex-col items-center">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                      index < currentStep
                        ? "bg-primary text-primary-foreground"
                        : index === currentStep
                          ? "bg-primary/10 text-primary border-2 border-primary"
                          : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {index < currentStep ? (
                      <CheckCircle2 className="h-4 w-4" />
                    ) : (
                      index + 1
                    )}
                  </div>
                  <span className="text-xs mt-1 hidden sm:block">
                    {step.title}
                  </span>
                </div>
                {index < steps.length - 1 && (
                  <div
                    className={`w-12 h-0.5 mx-2 ${
                      index < currentStep ? "bg-primary" : "bg-muted"
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
          <CardTitle>{steps[currentStep].title}</CardTitle>
          <CardDescription>{steps[currentStep].description}</CardDescription>
        </CardHeader>
        <CardContent>{renderStepContent()}</CardContent>
      </Card>
    </div>
  );
}
