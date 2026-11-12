import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Cloud, Database, GitBranch, GitPullRequest, ShieldCheck, Upload } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { z } from 'zod'

import { EmptyState } from '@/components/EmptyState'
import { FeatureGate } from '@/components/FeatureGate'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Textarea } from '@/components/ui/textarea'
import {
  fetchCapabilities,
  fetchGitHubAppInstallations,
  fetchGitHubAppLinkedRepos,
  fetchGitHubAppInstallUrlForReturnTo,
  fetchGitHubAppRepositories,
  fetchIntegrationsSetup,
  fetchSCMConnections,
  importPrismaFindings,
  importSonarRules,
  reassignGitHubAppLinkedRepos,
  onboardAzureDevOpsProject,
  type GitHubAppInstallationPublic,
  type GitHubAppLinkedRepoPublic,
  type PrismaImportRequest,
  type SCMConnectionPublic,
  type SonarRulesImportRequest,
  unlinkGitHubAppInstallation,
} from '@/lib/api'
import { useGitHubAppInstallResult } from '@/lib/hooks/useGitHubAppInstallResult'
import { useAuth } from '@/lib/useAuth'

function parseJsonArrayInput(value: string): unknown[] | null {
  try {
    const parsed = JSON.parse(value)
    return Array.isArray(parsed) ? parsed : null
  } catch {
    return null
  }
}

const azureSchema = z.object({
  organization_url: z.string().trim().url('Valid organization URL is required'),
  project: z.string().trim().min(1, 'Project is required'),
  access_token: z.string().trim().min(1, 'Access token is required'),
  auth_scheme: z.enum(['bearer', 'basic']),
  repository: z.string().trim().optional(),
  branch: z.string().trim().optional(),
  webhook_url: z.string().trim().url('Webhook URL is required'),
  secret: z.string().trim().optional(),
  detailed_messages_to_send: z.boolean(),
  events: z.array(z.string()).min(1, 'At least one event is required'),
})

type AzureFormValues = z.infer<typeof azureSchema>

const prismaImportSchema = z.object({
  repo: z.string().trim().min(1, 'Repository is required'),
  payload: z
    .string()
    .trim()
    .min(1, 'Prisma JSON is required')
    .refine((value) => parseJsonArrayInput(value) !== null, 'Must be a valid JSON array'),
})

type PrismaImportFormValues = z.infer<typeof prismaImportSchema>

const sonarImportSchema = z.object({
  language: z.string().trim().min(1, 'Language is required'),
  profileName: z.string().trim().optional(),
  payload: z
    .string()
    .trim()
    .min(1, 'Sonar rules JSON is required')
    .refine((value) => parseJsonArrayInput(value) !== null, 'Must be a valid JSON array'),
})

type SonarImportFormValues = z.infer<typeof sonarImportSchema>

const SAMPLE_PRISMA_JSON = `[
  {
    "severity": "critical",
    "title": "Public S3 bucket",
    "message": "Bucket is publicly accessible",
    "category": "iac",
    "file_path": "infra/main.tf",
    "line": 8,
    "rule_id": "BC_AWS_1"
  }
]`

const SAMPLE_SONAR_JSON = `[
  {
    "key": "python:S5332",
    "name": "Credentials should not be hard-coded",
    "lang": "py",
    "repo": "python",
    "severity": "BLOCKER",
    "type": "VULNERABILITY",
    "mdDesc": "Hard-coded credentials are unsafe.",
    "tags": ["security", "cwe"]
  }
]`

const AZURE_EVENT_OPTIONS = [
  'git.pullrequest.created',
  'git.pullrequest.updated',
]

function StatusPill({ ready, label }: { ready: boolean; label: string }) {
  return (
    <Badge color={ready ? 'success' : 'default'} variant="flat">
      {ready ? 'Configured' : label}
    </Badge>
  )
}

export function IntegrationsPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const isTenantAdmin = user?.role === 'admin'
  const githubInstallResult = useGitHubAppInstallResult()
  const [selectedInstallationId, setSelectedInstallationId] = useState<string>('')
  const [reassignTargetType, setReassignTargetType] = useState<'scm' | 'github-app'>('scm')
  const [selectedTargetScmConnectionId, setSelectedTargetScmConnectionId] = useState<string>('')
  const [selectedTargetInstallationId, setSelectedTargetInstallationId] = useState<string>('')
  const [unlinkCandidate, setUnlinkCandidate] = useState<GitHubAppInstallationPublic | null>(null)
  const [installPending, setInstallPending] = useState(false)
  const [installError, setInstallError] = useState<string | null>(null)
  const capabilitiesQuery = useQuery({
    queryKey: ['capabilities'],
    queryFn: fetchCapabilities,
  })
  const setupQuery = useQuery({
    queryKey: ['integrations-setup'],
    queryFn: fetchIntegrationsSetup,
  })
  const githubInstallationsQuery = useQuery({
    queryKey: ['github-app-installations'],
    queryFn: fetchGitHubAppInstallations,
    enabled: isTenantAdmin,
  })
  const githubRepositoriesQuery = useQuery({
    queryKey: ['github-app-installation-repositories', selectedInstallationId],
    queryFn: () => fetchGitHubAppRepositories(Number(selectedInstallationId)),
    enabled: isTenantAdmin && selectedInstallationId.length > 0,
  })
  const githubLinkedReposQuery = useQuery({
    queryKey: ['github-app-installation-linked-repos', selectedInstallationId],
    queryFn: () => fetchGitHubAppLinkedRepos(Number(selectedInstallationId)),
    enabled: isTenantAdmin && selectedInstallationId.length > 0,
  })
  const scmConnectionsQuery = useQuery({
    queryKey: ['scm-connections'],
    queryFn: fetchSCMConnections,
    enabled: isTenantAdmin,
  })

  const setup = setupQuery.data
  const capabilities = capabilitiesQuery.data
  const githubMissingRequirements = setup?.github.missing_requirements ?? []
  const githubInstallations = githubInstallationsQuery.data ?? []
  const selectedInstallation = githubInstallations.find(
    (installation) => String(installation.installation_id) === selectedInstallationId,
  )
  const githubLinkedRepos = githubLinkedReposQuery.data ?? []
  const githubRepositories = githubRepositoriesQuery.data ?? []
  const scmConnections = scmConnectionsQuery.data ?? []
  const eligibleScmConnections = scmConnections.filter(
    (connection) => connection.provider === 'github' && connection.is_active,
  )
  const alternateGitHubInstallations = githubInstallations.filter(
    (installation) => String(installation.installation_id) !== selectedInstallationId,
  )

  const azureForm = useForm<AzureFormValues>({
    resolver: zodResolver(azureSchema),
    values: {
      organization_url: 'https://dev.azure.com/your-org',
      project: '',
      access_token: '',
      auth_scheme: 'bearer',
      repository: '',
      branch: '',
      webhook_url: setup?.azure_devops.webhook_url ?? '',
      secret: '',
      detailed_messages_to_send: true,
      events: setup?.azure_devops.default_events ?? AZURE_EVENT_OPTIONS,
    },
  })

  const prismaForm = useForm<PrismaImportFormValues>({
    resolver: zodResolver(prismaImportSchema),
    defaultValues: {
      repo: 'https://example.com/org/repo.git',
      payload: SAMPLE_PRISMA_JSON,
    },
  })

  const sonarForm = useForm<SonarImportFormValues>({
    resolver: zodResolver(sonarImportSchema),
    defaultValues: {
      language: 'python',
      profileName: 'VigilWeave Python',
      payload: SAMPLE_SONAR_JSON,
    },
  })

  const azureMutation = useMutation({ mutationFn: onboardAzureDevOpsProject })
  const prismaMutation = useMutation({ mutationFn: importPrismaFindings })
  const sonarMutation = useMutation({ mutationFn: importSonarRules })
  const unlinkMutation = useMutation({
    mutationFn: unlinkGitHubAppInstallation,
    onSuccess: async () => {
      setUnlinkCandidate(null)
      await queryClient.invalidateQueries({ queryKey: ['github-app-installations'] })
      await queryClient.invalidateQueries({ queryKey: ['github-app-installation-repositories'] })
      await queryClient.invalidateQueries({ queryKey: ['github-app-installation-linked-repos'] })
    },
  })
  const reassignMutation = useMutation({
    mutationFn: ({
      installationId,
      payload,
    }: {
      installationId: number
      payload: {
        target_scm_connection_id?: number
        target_github_installation_id?: number
      }
    }) => reassignGitHubAppLinkedRepos(installationId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['github-app-installations'] })
      await queryClient.invalidateQueries({ queryKey: ['github-app-installation-linked-repos'] })
      await queryClient.invalidateQueries({ queryKey: ['github-app-installation-repositories'] })
    },
  })
  const azureAuthScheme =
    useWatch({
      control: azureForm.control,
      name: 'auth_scheme',
    }) ?? 'bearer'
  const azureEvents =
    useWatch({
      control: azureForm.control,
      name: 'events',
    }) ?? []
  const azureDetailedMessages =
    useWatch({
      control: azureForm.control,
      name: 'detailed_messages_to_send',
    }) ?? true

  useEffect(() => {
    if (!githubInstallations.length) {
      setSelectedInstallationId('')
      return
    }

    if (!selectedInstallationId || !githubInstallations.some((item) => String(item.installation_id) === selectedInstallationId)) {
      setSelectedInstallationId(String(githubInstallations[0].installation_id))
    }
  }, [githubInstallations, selectedInstallationId])

  useEffect(() => {
    if (reassignTargetType === 'scm') {
      if (eligibleScmConnections.length === 0 && alternateGitHubInstallations.length > 0) {
        setReassignTargetType('github-app')
        return
      }

      if (
        !selectedTargetScmConnectionId ||
        !eligibleScmConnections.some(
          (connection) => String(connection.id) === selectedTargetScmConnectionId,
        )
      ) {
        setSelectedTargetScmConnectionId(
          eligibleScmConnections.length > 0 ? String(eligibleScmConnections[0].id) : '',
        )
      }
      return
    }

    if (alternateGitHubInstallations.length === 0 && eligibleScmConnections.length > 0) {
      setReassignTargetType('scm')
      return
    }

    if (
      !selectedTargetInstallationId ||
      !alternateGitHubInstallations.some(
        (installation) => String(installation.installation_id) === selectedTargetInstallationId,
      )
    ) {
      setSelectedTargetInstallationId(
        alternateGitHubInstallations.length > 0
          ? String(alternateGitHubInstallations[0].installation_id)
          : '',
      )
    }
  }, [
    alternateGitHubInstallations,
    eligibleScmConnections,
    reassignTargetType,
    selectedTargetInstallationId,
    selectedTargetScmConnectionId,
  ])

  useEffect(() => {
    reassignMutation.reset()
  }, [
    reassignMutation,
    reassignTargetType,
    selectedInstallationId,
    selectedTargetInstallationId,
    selectedTargetScmConnectionId,
  ])

  if (setupQuery.isLoading && capabilitiesQuery.isLoading && !setup && !capabilities) {
    return (
      <div className="flex justify-center py-20">
        <p className="text-sm text-muted-foreground">Loading integrations...</p>
      </div>
    )
  }

  function toggleAzureEvent(eventType: string) {
    const current = new Set(azureForm.getValues('events'))
    if (current.has(eventType)) {
      current.delete(eventType)
    } else {
      current.add(eventType)
    }
    azureForm.setValue('events', Array.from(current))
  }

  async function handleGitHubInstall(): Promise<void> {
    setInstallPending(true)
    setInstallError(null)
    try {
      const installLink = await fetchGitHubAppInstallUrlForReturnTo(
        `${window.location.pathname}${window.location.search}`,
      )
      window.location.assign(installLink.install_url)
    } catch (error) {
      setInstallPending(false)
      setInstallError(error instanceof Error ? error.message : 'Failed to start the GitHub App installation flow.')
    }
  }

  function handleReassignLinkedRepos() {
    if (!selectedInstallation) {
      return
    }

    const payload =
      reassignTargetType === 'scm'
        ? { target_scm_connection_id: Number(selectedTargetScmConnectionId) }
        : { target_github_installation_id: Number(selectedTargetInstallationId) }

    reassignMutation.reset()
    reassignMutation.mutate({
      installationId: selectedInstallation.installation_id,
      payload,
    })
  }

  function submitPrisma(values: PrismaImportFormValues) {
    const findings = parseJsonArrayInput(values.payload)
    if (!findings) {
      prismaForm.setError('payload', {
        type: 'manual',
        message: 'Must be a valid JSON array',
      })
      return
    }
    prismaForm.clearErrors('payload')
    prismaMutation.reset()
    prismaMutation.mutate({
      repo: values.repo,
      findings: findings as PrismaImportRequest['findings'],
    })
  }

  function submitSonar(values: SonarImportFormValues) {
    const rules = parseJsonArrayInput(values.payload)
    if (!rules) {
      sonarForm.setError('payload', {
        type: 'manual',
        message: 'Must be a valid JSON array',
      })
      return
    }
    sonarForm.clearErrors('payload')
    sonarMutation.reset()
    sonarMutation.mutate({
      language: values.language,
      profile_name: values.profileName || null,
      rules: rules as SonarRulesImportRequest['rules'],
      persist: true,
    })
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Integrations</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Guided onboarding for GitHub and Azure DevOps, with advanced import flows kept secondary.
        </p>
      </div>

      {setupQuery.isError ? (
        <div className="rounded-sm border border-warning/30 bg-warning/5 px-4 py-3 text-sm text-warning">
          Integration setup details could not be loaded. Existing configuration may still be valid.
        </div>
      ) : null}

      {capabilitiesQuery.isError ? (
        <div className="rounded-sm border border-warning/30 bg-warning/5 px-4 py-3 text-sm text-warning">
          Server capabilities could not be loaded. Feature availability shown on this page may be incomplete.
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="overflow-hidden border-border">
          <CardHeader className="px-6 pt-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-sm bg-primary/10">
                <GitBranch className="text-primary" size={20} />
              </div>
              <div>
                <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
                  Primary
                </p>
                <h2 className="text-lg font-semibold">GitHub App setup</h2>
              </div>
            </div>
          </CardHeader>
          <Separator />
          <CardContent className="space-y-4 p-6">
            {setup ? (
              <>
                <div className="flex flex-wrap gap-2">
                  <StatusPill ready={setup.github.app_id_configured} label="App ID missing" />
                  <StatusPill ready={setup.github.private_key_configured} label="Private key missing" />
                  <StatusPill ready={setup.github.webhook_secret_configured} label="Webhook secret missing" />
                </div>
                <div className="rounded-sm border border-border bg-muted/40 p-4">
                  <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Webhook URL</p>
                  <p className="mt-1 break-all font-mono text-xs">{setup.github.webhook_url}</p>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-sm border border-border bg-muted/40 p-4">
                    <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Tenant</p>
                    <p className="mt-1 text-sm font-semibold">{setup.github.tenant_slug}</p>
                  </div>
                  <div className="rounded-sm border border-border bg-muted/40 p-4">
                    <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Check name</p>
                    <p className="mt-1 text-sm font-semibold">{setup.github.check_name}</p>
                  </div>
                </div>
                {githubMissingRequirements.length > 0 ? (
                  <div className="rounded-sm border border-warning/30 bg-warning/5 p-4">
                    <p className="text-sm font-semibold text-warning">Missing prerequisites</p>
                    <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
                      {githubMissingRequirements.map((item) => (
                        <li key={item}>• {item}</li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <div className="rounded-sm border border-success/30 bg-success/[0.06] p-4">
                    <div className="flex items-center gap-2">
                      <ShieldCheck className="text-success" size={16} />
                      <p className="text-sm font-semibold text-success">GitHub setup is ready</p>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Webhook target, app credentials, and check-run settings are configured.
                    </p>
                  </div>
                )}

                <Separator />

                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Management</p>
                      <h3 className="text-sm font-semibold">Tenant installations</h3>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Install the app for another GitHub account, inspect which installation this tenant is using,
                        and preview the repositories currently visible to that installation.
                      </p>
                    </div>
                    {isTenantAdmin ? (
                      <Button
                        size="sm"
                        onClick={() => void handleGitHubInstall()}
                        disabled={installPending || githubMissingRequirements.length > 0}
                      >
                        {installPending ? 'Opening GitHub...' : githubInstallations.length > 0 ? 'Install or reconnect' : 'Install GitHub App'}
                      </Button>
                    ) : (
                      <Badge variant="flat">Tenant admin required</Badge>
                    )}
                  </div>

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

                  {installError ? (
                    <div className="rounded-sm border border-danger/30 bg-danger/[0.06] px-4 py-3 text-sm text-danger">
                      {installError}
                    </div>
                  ) : null}

                  {unlinkMutation.isError ? (
                    <div className="rounded-sm border border-danger/30 bg-danger/[0.06] px-4 py-3 text-sm text-danger">
                      {unlinkMutation.error instanceof Error
                        ? unlinkMutation.error.message
                        : 'GitHub App unlink failed.'}
                    </div>
                  ) : null}

                  {!isTenantAdmin ? (
                    <EmptyState
                      title="Admin only"
                      body="Tenant admin access is required to install the GitHub App, inspect tenant installations, and preview repository access."
                    />
                  ) : githubInstallationsQuery.isLoading ? (
                    <p className="text-sm text-muted-foreground">Loading tenant installations...</p>
                  ) : githubInstallationsQuery.isError ? (
                    <EmptyState
                      title="Installations unavailable"
                      body="GitHub App installations could not be loaded right now. Refresh the page and verify the API is reachable."
                    />
                  ) : githubInstallations.length === 0 ? (
                    <EmptyState
                      title="No tenant installations"
                      body="No GitHub App installations are linked to this tenant yet. Start the install flow above, then return here to inspect repository access."
                    />
                  ) : (
                    <div className="space-y-4">
                        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                          <div className="space-y-2">
                            <Label>Installation</Label>
                          <Select value={selectedInstallationId} onValueChange={setSelectedInstallationId}>
                            <SelectTrigger>
                              <SelectValue placeholder="Select installation" />
                            </SelectTrigger>
                            <SelectContent>
                              {githubInstallations.map((installation) => (
                                <SelectItem
                                  key={installation.installation_id}
                                  value={String(installation.installation_id)}
                                >
                                  {installation.account_login}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        {selectedInstallation ? (
                          <GitHubInstallationMeta installation={selectedInstallation} />
                        ) : null}
                      </div>

                      {selectedInstallation ? (
                        <div className="flex flex-wrap items-center justify-between gap-3 rounded-sm border border-border bg-muted/30 px-4 py-3">
                          <div>
                            <p className="text-sm font-semibold">Tenant link management</p>
                            <p className="mt-1 text-xs text-muted-foreground">
                              Unlinking removes this installation from VigilWeave for this tenant only. It does not uninstall the GitHub App from GitHub.
                            </p>
                            {selectedInstallation.linked_repo_count > 0 ? (
                              <p className="mt-1 text-xs text-warning">
                                {selectedInstallation.linked_repo_count} linked project repositor{selectedInstallation.linked_repo_count === 1 ? 'y still depends' : 'ies still depend'} on this installation.
                              </p>
                            ) : null}
                          </div>
                          <Button
                            color="danger"
                            size="sm"
                            variant="flat"
                            disabled={unlinkMutation.isPending || selectedInstallation.linked_repo_count > 0}
                            onClick={() => setUnlinkCandidate(selectedInstallation)}
                          >
                            Unlink from tenant
                          </Button>
                        </div>
                      ) : null}

                      {selectedInstallation ? (
                        <GitHubLinkedRepoReassignmentCard
                          alternateInstallations={alternateGitHubInstallations}
                          isLoadingConnections={scmConnectionsQuery.isLoading}
                          isLoadingLinkedRepos={githubLinkedReposQuery.isLoading}
                          linkedRepos={githubLinkedRepos}
                          linkedReposError={
                            githubLinkedReposQuery.isError
                              ? 'Linked project repositories could not be loaded for this installation.'
                              : null
                          }
                          onReassign={() => handleReassignLinkedRepos()}
                          onSelectTargetInstallation={setSelectedTargetInstallationId}
                          onSelectTargetScmConnection={setSelectedTargetScmConnectionId}
                          onSetTargetType={setReassignTargetType}
                          reassignError={
                            reassignMutation.isError
                              ? reassignMutation.error instanceof Error
                                ? reassignMutation.error.message
                                : 'Linked repository reassignment failed.'
                              : null
                          }
                          reassignPending={reassignMutation.isPending}
                          reassignSuccess={reassignMutation.data?.reassigned_count ?? null}
                          scmConnections={eligibleScmConnections}
                          selectedInstallation={selectedInstallation}
                          selectedTargetInstallationId={selectedTargetInstallationId}
                          selectedTargetScmConnectionId={selectedTargetScmConnectionId}
                          targetType={reassignTargetType}
                        />
                      ) : null}

                      {githubRepositoriesQuery.isLoading ? (
                        <p className="text-sm text-muted-foreground">Loading installation repositories...</p>
                      ) : githubRepositoriesQuery.isError ? (
                        <div className="rounded-sm border border-warning/30 bg-warning/5 px-4 py-3 text-sm text-warning">
                          GitHub repositories could not be loaded for this installation.
                        </div>
                      ) : githubRepositories.length === 0 ? (
                        <EmptyState
                          title="No repositories visible"
                          body="This installation is connected, but no repositories are currently visible to VigilWeave. Adjust repository access in GitHub, then refresh this page."
                        />
                      ) : (
                        <div className="space-y-2">
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-sm font-semibold">Repository preview</p>
                            <p className="text-xs text-muted-foreground">
                              {githubRepositories.length} repositor{githubRepositories.length === 1 ? 'y' : 'ies'} visible
                            </p>
                          </div>
                          <div className="max-h-64 space-y-2 overflow-y-auto">
                            {githubRepositories.slice(0, 12).map((repo) => (
                              <div key={repo.id} className="rounded-sm border border-border bg-muted/40 px-3 py-3">
                                <div className="flex items-start justify-between gap-3">
                                  <div className="min-w-0">
                                    <p className="text-sm font-medium">{repo.full_name}</p>
                                    {repo.description ? (
                                      <p className="mt-1 text-xs text-muted-foreground">{repo.description}</p>
                                    ) : null}
                                  </div>
                                  <div className="shrink-0 text-right text-xs text-muted-foreground">
                                    <p>{repo.is_private ? 'Private' : 'Public'}</p>
                                    <p>{repo.default_branch || 'main'}</p>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                          {githubRepositories.length > 12 ? (
                            <p className="text-xs text-muted-foreground">
                              Showing the first 12 repositories. Use project import flows to browse the full installation.
                            </p>
                          ) : null}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </>
            ) : setupQuery.isError ? (
              <EmptyState body="Integration setup details are unavailable right now." title="Setup unavailable" />
            ) : (
              <EmptyState body="Integration setup status is unavailable." title="No setup contract" />
            )}
          </CardContent>
        </Card>

        <Card className="overflow-hidden border-border">
          <CardHeader className="px-6 pt-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-sm bg-primary/10">
                <GitPullRequest className="text-primary" size={20} />
              </div>
              <div>
                <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
                  Primary
                </p>
                <h2 className="text-lg font-semibold">Azure DevOps onboarding</h2>
              </div>
            </div>
          </CardHeader>
          <Separator />
          <CardContent className="p-6">
            <FeatureGate
              feature="custom_adapters"
              fallback={
                <EmptyState
                  body="Azure DevOps onboarding is available on the Enterprise tier."
                  title="Enterprise integration"
                />
              }
            >
              {isTenantAdmin ? (
                <form className="space-y-4" onSubmit={azureForm.handleSubmit((values) => azureMutation.mutate(values))}>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label>Organization URL</Label>
                      <Input {...azureForm.register('organization_url')} />
                      {azureForm.formState.errors.organization_url ? (
                        <p className="text-xs text-danger">{azureForm.formState.errors.organization_url.message}</p>
                      ) : null}
                    </div>
                    <div className="space-y-2">
                      <Label>Project</Label>
                      <Input {...azureForm.register('project')} placeholder="Payments Platform" />
                      {azureForm.formState.errors.project ? (
                        <p className="text-xs text-danger">{azureForm.formState.errors.project.message}</p>
                      ) : null}
                    </div>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label>Access token / PAT</Label>
                      <Input {...azureForm.register('access_token')} type="password" />
                      {azureForm.formState.errors.access_token ? (
                        <p className="text-xs text-danger">{azureForm.formState.errors.access_token.message}</p>
                      ) : null}
                    </div>
                    <div className="space-y-2">
                      <Label>Auth scheme</Label>
                      <div className="grid grid-cols-2 gap-2">
                        {(['bearer', 'basic'] as const).map((scheme) => (
                          <Button
                            key={scheme}
                            type="button"
                            variant={azureAuthScheme === scheme ? 'default' : 'flat'}
                            onClick={() => azureForm.setValue('auth_scheme', scheme)}
                          >
                            {scheme.toUpperCase()}
                          </Button>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label>Repository filter</Label>
                      <Input {...azureForm.register('repository')} placeholder="api-service" />
                    </div>
                    <div className="space-y-2">
                      <Label>Branch filter</Label>
                      <Input {...azureForm.register('branch')} placeholder="main" />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>Webhook URL</Label>
                    <Input {...azureForm.register('webhook_url')} />
                    <p className="text-xs text-muted-foreground">
                      Suggested target: {setup?.azure_devops.webhook_url ?? 'Loading...'}
                    </p>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label>Webhook secret</Label>
                      <Input {...azureForm.register('secret')} placeholder="Optional shared secret" />
                    </div>
                    <div className="flex items-center gap-2 pt-8">
                      <Checkbox
                        checked={azureDetailedMessages}
                        onCheckedChange={(checked) =>
                          azureForm.setValue('detailed_messages_to_send', checked === true)
                        }
                      />
                      <Label>Request detailed payloads</Label>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>Events</Label>
                    <div className="grid gap-2 md:grid-cols-2">
                      {AZURE_EVENT_OPTIONS.map((eventType) => {
                        const checked = azureEvents.includes(eventType)
                        return (
                          <label
                            className="flex items-start gap-3 rounded-sm border border-border bg-muted/40 px-3 py-3"
                            key={eventType}
                          >
                            <Checkbox checked={checked} onCheckedChange={() => toggleAzureEvent(eventType)} />
                            <span className="font-mono text-xs">{eventType}</span>
                          </label>
                        )
                      })}
                    </div>
                  </div>

                  {azureMutation.isError ? (
                    <p className="text-sm text-danger">
                      {azureMutation.error instanceof Error
                        ? azureMutation.error.message
                        : 'Azure onboarding failed. Check the org URL, PAT, and service-hook permissions.'}
                    </p>
                  ) : null}

                  {azureMutation.data ? (
                    <div className="rounded-sm border border-success/30 bg-success/[0.06] p-4">
                      <p className="text-sm font-semibold text-success">
                        Created {azureMutation.data.subscriptions_created} subscription(s)
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Project: {azureMutation.data.project}
                      </p>
                    </div>
                  ) : null}

                  <Button color="primary" isLoading={azureMutation.isPending} type="submit">
                    <ArrowRight size={14} />
                    Onboard project
                  </Button>
                </form>
              ) : (
                <EmptyState
                  body="Tenant admin access is required to create Azure DevOps service hooks for this workspace."
                  title="Admin only"
                />
              )}
            </FeatureGate>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="px-6 pt-5">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
              Platform
            </p>
            <h2 className="text-lg font-semibold">Server capabilities</h2>
          </div>
        </CardHeader>
        <Separator />
          <CardContent className="p-6">
          {capabilities ? (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <Card className="bg-muted/50">
                <CardContent className="gap-1 p-4">
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Auth</p>
                  <p className="text-sm font-semibold">
                    {capabilities.authentication?.api_keys ? 'API Keys Required' : 'Open Mode'}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Tenants: {capabilities.authentication?.tenant_headers ? 'enabled' : 'disabled'}
                  </p>
                </CardContent>
              </Card>
              <Card className="bg-muted/50">
                <CardContent className="gap-1 p-4">
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Scan modes</p>
                  <p className="text-sm font-semibold">{capabilities.scan_types?.join(', ') ?? 'N/A'}</p>
                </CardContent>
              </Card>
              <Card className="bg-muted/50">
                <CardContent className="gap-1 p-4">
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground">GitHub App</p>
                  <p className="text-sm font-semibold">
                    {setup?.github.configured ? 'Ready' : 'Needs config'}
                  </p>
                </CardContent>
              </Card>
              <Card className="bg-muted/50">
                <CardContent className="gap-1 p-4">
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Azure DevOps</p>
                  <p className="text-sm font-semibold">
                    {setup?.azure_devops.onboarding_enabled ? 'Onboarding enabled' : 'Disabled'}
                  </p>
                </CardContent>
              </Card>
            </div>
          ) : capabilitiesQuery.isError ? (
            <EmptyState body="Server capabilities are unavailable right now." title="Capabilities unavailable" />
          ) : (
            <EmptyState body="Capabilities unavailable." title="No contract" />
          )}
        </CardContent>
      </Card>

      <FeatureGate
        feature="custom_adapters"
        fallback={
          <Card>
            <CardContent className="p-6">
              <EmptyState
                body="Prisma Cloud and SonarQube import workflows unlock on the Enterprise tier."
                title="Enterprise connectors"
              />
            </CardContent>
          </Card>
        }
      >
        <div className="grid gap-4 xl:grid-cols-2">
          <Card>
            <CardHeader className="px-6 pt-5">
              <div className="flex items-center gap-3">
                <Cloud size={18} />
                <div>
                  <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
                    Advanced
                  </p>
                  <h2 className="text-lg font-semibold">Prisma import</h2>
                </div>
              </div>
            </CardHeader>
            <Separator />
            <CardContent className="p-6">
              <form className="space-y-4" onSubmit={prismaForm.handleSubmit(submitPrisma)}>
                <div className="space-y-2">
                  <Label>Repository</Label>
                  <Input {...prismaForm.register('repo')} />
                </div>
                <div className="space-y-2">
                  <Label>Prisma findings JSON</Label>
                  <Textarea {...prismaForm.register('payload')} className="font-mono text-xs" rows={8} />
                </div>
                {prismaMutation.isError ? (
                  <p className="text-sm text-danger">
                    {prismaMutation.error instanceof Error ? prismaMutation.error.message : 'Prisma import failed.'}
                  </p>
                ) : null}
                {prismaMutation.data ? (
                  <p className="text-xs text-muted-foreground">
                    Imported scan #{prismaMutation.data.scan.id}.
                  </p>
                ) : null}
                <Button color="primary" isLoading={prismaMutation.isPending} type="submit">
                  <Upload size={14} />
                  Import findings
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="px-6 pt-5">
              <div className="flex items-center gap-3">
                <Database size={18} />
                <div>
                  <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
                    Advanced
                  </p>
                  <h2 className="text-lg font-semibold">SonarQube rule import</h2>
                </div>
              </div>
            </CardHeader>
            <Separator />
            <CardContent className="p-6">
              <form className="space-y-4" onSubmit={sonarForm.handleSubmit(submitSonar)}>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label>Language</Label>
                    <Input {...sonarForm.register('language')} />
                  </div>
                  <div className="space-y-2">
                    <Label>Profile name</Label>
                    <Input {...sonarForm.register('profileName')} />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Rules JSON</Label>
                  <Textarea {...sonarForm.register('payload')} className="font-mono text-xs" rows={8} />
                </div>
                {sonarMutation.isError ? (
                  <p className="text-sm text-danger">
                    {sonarMutation.error instanceof Error
                      ? sonarMutation.error.message
                      : 'SonarQube rule import failed.'}
                  </p>
                ) : null}
                {sonarMutation.data ? (
                  <p className="text-xs text-muted-foreground">
                    Imported {sonarMutation.data.rules_imported} rules for {sonarMutation.data.language}.
                  </p>
                ) : null}
                <Button color="primary" isLoading={sonarMutation.isPending} type="submit">
                  <Upload size={14} />
                  Import rules
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      </FeatureGate>

      <Dialog open={unlinkCandidate !== null} onOpenChange={(open) => !open && setUnlinkCandidate(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Unlink GitHub App installation</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Unlink <span className="font-semibold">{unlinkCandidate?.account_login}</span> from this tenant? This only removes the VigilWeave tenant mapping and does not uninstall the GitHub App in GitHub.
            </p>
            {unlinkCandidate?.linked_repo_count ? (
              <div className="rounded-sm border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-warning">
                This installation is still linked to {unlinkCandidate.linked_repo_count} project repositor{unlinkCandidate.linked_repo_count === 1 ? 'y' : 'ies'} and cannot be unlinked yet.
              </div>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="flat" onClick={() => setUnlinkCandidate(null)}>
              Cancel
            </Button>
            <Button
              color="danger"
              isLoading={unlinkMutation.isPending}
              disabled={!unlinkCandidate || unlinkCandidate.linked_repo_count > 0}
              onClick={() => {
                if (unlinkCandidate) {
                  unlinkMutation.mutate(unlinkCandidate.installation_id)
                }
              }}
            >
              Unlink
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function GitHubInstallationMeta({ installation }: { installation: GitHubAppInstallationPublic }) {
  return (
    <div className="rounded-sm border border-border bg-muted/40 p-4">
      <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Selected installation</p>
      <p className="mt-1 text-sm font-semibold">{installation.account_login}</p>
      <p className="mt-1 text-xs text-muted-foreground">
        {installation.account_type ?? 'GitHub account'}
        {' · '}linked {new Date(installation.created_at).toLocaleDateString()}
        {' · '}updated {new Date(installation.updated_at).toLocaleDateString()}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        {installation.linked_repo_count} linked project repositor{installation.linked_repo_count === 1 ? 'y' : 'ies'}
      </p>
    </div>
  )
}

function GitHubLinkedRepoReassignmentCard({
  alternateInstallations,
  isLoadingConnections,
  isLoadingLinkedRepos,
  linkedRepos,
  linkedReposError,
  onReassign,
  onSelectTargetInstallation,
  onSelectTargetScmConnection,
  onSetTargetType,
  reassignError,
  reassignPending,
  reassignSuccess,
  scmConnections,
  selectedInstallation,
  selectedTargetInstallationId,
  selectedTargetScmConnectionId,
  targetType,
}: {
  alternateInstallations: GitHubAppInstallationPublic[]
  isLoadingConnections: boolean
  isLoadingLinkedRepos: boolean
  linkedRepos: GitHubAppLinkedRepoPublic[]
  linkedReposError: string | null
  onReassign: () => void
  onSelectTargetInstallation: (value: string) => void
  onSelectTargetScmConnection: (value: string) => void
  onSetTargetType: (value: 'scm' | 'github-app') => void
  reassignError: string | null
  reassignPending: boolean
  reassignSuccess: number | null
  scmConnections: SCMConnectionPublic[]
  selectedInstallation: GitHubAppInstallationPublic
  selectedTargetInstallationId: string
  selectedTargetScmConnectionId: string
  targetType: 'scm' | 'github-app'
}) {
  const reassignmentDisabled =
    linkedRepos.length === 0 ||
    reassignPending ||
    (targetType === 'scm'
      ? selectedTargetScmConnectionId.length === 0
      : selectedTargetInstallationId.length === 0)

  return (
    <div className="space-y-4 rounded-sm border border-border bg-muted/20 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">Linked project repositories</p>
          <p className="mt-1 text-xs text-muted-foreground">
            These project repository links currently use {selectedInstallation.account_login} for credentials.
          </p>
        </div>
        <Badge variant="flat">
          {selectedInstallation.linked_repo_count} linked repo{selectedInstallation.linked_repo_count === 1 ? '' : 's'}
        </Badge>
      </div>

      {isLoadingLinkedRepos ? (
        <p className="text-sm text-muted-foreground">Loading linked project repositories...</p>
      ) : linkedReposError ? (
        <div className="rounded-sm border border-warning/30 bg-warning/5 px-4 py-3 text-sm text-warning">
          {linkedReposError}
        </div>
      ) : linkedRepos.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No project repositories are currently assigned to this installation.
        </p>
      ) : (
        <div className="max-h-56 space-y-2 overflow-y-auto">
          {linkedRepos.map((repo) => (
            <div key={`${repo.project_key}:${repo.repo}`} className="rounded-sm border border-border bg-background px-3 py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium">{repo.project_name}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{repo.project_key}</p>
                </div>
                <p className="max-w-[60%] truncate text-right font-mono text-xs text-muted-foreground">
                  {repo.repo}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      <Separator />

      <div className="space-y-3">
        <div>
          <p className="text-sm font-semibold">Reassign linked repositories</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Move every linked project repository to an SCM connection or another tenant GitHub App installation.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            type="button"
            variant={targetType === 'scm' ? 'default' : 'flat'}
            onClick={() => onSetTargetType('scm')}
          >
            SCM connection
          </Button>
          <Button
            size="sm"
            type="button"
            variant={targetType === 'github-app' ? 'default' : 'flat'}
            onClick={() => onSetTargetType('github-app')}
          >
            Another GitHub App
          </Button>
        </div>

        {targetType === 'scm' ? (
          isLoadingConnections ? (
            <p className="text-sm text-muted-foreground">Loading SCM connections...</p>
          ) : scmConnections.length === 0 ? (
            <div className="rounded-sm border border-warning/30 bg-warning/5 px-4 py-3 text-sm text-warning">
              No active GitHub SCM connections are available for this tenant.
            </div>
          ) : (
            <div className="space-y-2">
              <Label>Target GitHub SCM connection</Label>
              <Select value={selectedTargetScmConnectionId} onValueChange={onSelectTargetScmConnection}>
                <SelectTrigger>
                  <SelectValue placeholder="Select SCM connection" />
                </SelectTrigger>
                <SelectContent>
                  {scmConnections.map((connection) => (
                    <SelectItem key={connection.id} value={String(connection.id)}>
                      {connection.name} · {connection.provider}
                      {connection.is_active ? '' : ' · inactive'}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )
        ) : alternateInstallations.length === 0 ? (
          <div className="rounded-sm border border-warning/30 bg-warning/5 px-4 py-3 text-sm text-warning">
            No alternate GitHub App installations are available for this tenant.
          </div>
        ) : (
          <div className="space-y-2">
            <Label>Target GitHub App installation</Label>
            <Select value={selectedTargetInstallationId} onValueChange={onSelectTargetInstallation}>
              <SelectTrigger>
                <SelectValue placeholder="Select installation" />
              </SelectTrigger>
              <SelectContent>
                {alternateInstallations.map((installation) => (
                  <SelectItem
                    key={installation.installation_id}
                    value={String(installation.installation_id)}
                  >
                    {installation.account_login}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {reassignError ? (
          <div className="rounded-sm border border-danger/30 bg-danger/[0.06] px-4 py-3 text-sm text-danger">
            {reassignError}
          </div>
        ) : null}

        {reassignSuccess !== null ? (
          <div className="rounded-sm border border-success/30 bg-success/[0.06] px-4 py-3 text-sm text-success">
            Reassigned {reassignSuccess} linked project repositor{reassignSuccess === 1 ? 'y' : 'ies'}.
          </div>
        ) : null}

        <Button
          color="primary"
          disabled={reassignmentDisabled}
          isLoading={reassignPending}
          onClick={onReassign}
        >
          Reassign linked repos
        </Button>
      </div>
    </div>
  )
}
