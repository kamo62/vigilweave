import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Github, Loader2, Shield } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { Checkbox } from '@/components/ui/checkbox'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  fetchGitHubAppInstallations,
  fetchGitHubAppInstallUrlForReturnTo,
  fetchGitHubAppRepositories,
  type SCMRepository,
} from '@/lib/api'

interface GitHubAppRepoPickerProps {
  selectedRepoUrls: Set<string>
  onSelectionChange: (next: Set<string>) => void
  excludedRepoUrls?: Set<string>
  selectionMode?: 'single' | 'multiple'
  onInstallationChange?: (installationId: number | null) => void
  installResult?: {
    connected: boolean
    message: string
  } | null
}

export function GitHubAppRepoPicker({
  selectedRepoUrls,
  onSelectionChange,
  excludedRepoUrls = new Set<string>(),
  selectionMode = 'multiple',
  onInstallationChange,
  installResult = null,
}: GitHubAppRepoPickerProps) {
  const installationsQuery = useQuery({
    queryKey: ['github-app-installations'],
    queryFn: fetchGitHubAppInstallations,
  })
  const [selectedInstallationId, setSelectedInstallationId] = useState('')
  const [repositories, setRepositories] = useState<SCMRepository[]>([])
  const [reposLoading, setReposLoading] = useState(false)
  const [reposError, setReposError] = useState<string | null>(null)
  const [installPending, setInstallPending] = useState(false)
  const [installError, setInstallError] = useState<string | null>(null)

  useEffect(() => {
    onInstallationChange?.(selectedInstallationId ? Number(selectedInstallationId) : null)

    if (!selectedInstallationId) {
      setRepositories([])
      setReposError(null)
      onSelectionChange(new Set())
      return
    }

    let cancelled = false
    onSelectionChange(new Set())

    void (async () => {
      try {
        setReposLoading(true)
        setReposError(null)
        const data = await fetchGitHubAppRepositories(Number(selectedInstallationId))
        if (!cancelled) {
          setRepositories(data)
        }
      } catch (error) {
        if (!cancelled) {
          setRepositories([])
          setReposError(
            error instanceof Error
              ? error.message
              : 'Failed to load repositories for this GitHub App installation.',
          )
        }
      } finally {
        if (!cancelled) {
          setReposLoading(false)
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [onInstallationChange, onSelectionChange, selectedInstallationId])

  async function handleInstall(): Promise<void> {
    try {
      setInstallPending(true)
      setInstallError(null)
      const returnTo = `${window.location.pathname}${window.location.search}`
      const data = await fetchGitHubAppInstallUrlForReturnTo(returnTo)
      window.location.assign(data.install_url)
    } catch (error) {
      setInstallError(
        error instanceof Error
          ? error.message
          : 'Failed to start the GitHub App installation flow.',
      )
    } finally {
      setInstallPending(false)
    }
  }

  function toggleRepo(repoUrl: string): void {
    if (excludedRepoUrls.has(repoUrl)) {
      return
    }

    const next = new Set(selectedRepoUrls)
    if (selectionMode === 'single') {
      if (next.has(repoUrl)) {
        next.clear()
      } else {
        next.clear()
        next.add(repoUrl)
      }
    } else if (next.has(repoUrl)) {
      next.delete(repoUrl)
    } else {
      next.add(repoUrl)
    }

    onSelectionChange(next)
  }

  const installations = installationsQuery.data ?? []

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Label className="text-[11px] uppercase tracking-widest text-muted-foreground font-bold">
            GitHub App
          </Label>
          <p className="mt-1 text-sm text-muted-foreground">
            Select repositories from an installed GitHub App without storing PAT credentials.
          </p>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={() => void handleInstall()} disabled={installPending}>
          {installPending ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : <Github className="mr-2 h-3.5 w-3.5" />}
          Install GitHub App
        </Button>
      </div>

      {installResult ? (
        <p className={`text-sm ${installResult.connected ? 'text-success' : 'text-danger'}`}>
          {installResult.message}
        </p>
      ) : null}

      {installError ? <p className="text-sm text-danger">{installError}</p> : null}

      {installationsQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading GitHub App installations...</p>
      ) : installationsQuery.isError ? (
        <EmptyState
          title="GitHub App unavailable"
          body="Failed to load GitHub App installations for this tenant. Check the integration configuration and try again."
        />
      ) : installations.length === 0 ? (
        <EmptyState
          title="No GitHub App installations"
          body="Install the GitHub App for an account or organization, then return here to choose repositories."
        />
      ) : (
        <>
          <div className="space-y-1.5">
            <Label className="text-[11px] uppercase tracking-widest text-muted-foreground font-bold">
              Installation
            </Label>
            <Select value={selectedInstallationId} onValueChange={setSelectedInstallationId}>
              <SelectTrigger>
                <SelectValue placeholder="Select installation..." />
              </SelectTrigger>
              <SelectContent>
                {installations.map((installation) => (
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

          {reposLoading ? (
            <p className="text-sm text-muted-foreground">Loading repositories...</p>
          ) : reposError ? (
            <p className="text-sm text-danger">{reposError}</p>
          ) : selectedInstallationId && repositories.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No repositories are visible for this installation yet.
            </p>
          ) : repositories.length > 0 ? (
            <div className="border border-border rounded-sm max-h-56 overflow-y-auto divide-y divide-border/40">
              {repositories.map((repo) => {
                const isExcluded = excludedRepoUrls.has(repo.clone_url)
                return (
                  <label
                    key={repo.id}
                    className={`flex items-center gap-3 px-3 py-2 text-sm ${
                      isExcluded ? 'cursor-not-allowed opacity-60' : 'cursor-pointer hover:bg-muted/50'
                    }`}
                  >
                    <Checkbox
                      checked={isExcluded || selectedRepoUrls.has(repo.clone_url)}
                      disabled={isExcluded}
                      onCheckedChange={() => toggleRepo(repo.clone_url)}
                    />
                    <div className="flex-1 min-w-0">
                      <span className="font-medium truncate block">{repo.full_name}</span>
                      {repo.description ? (
                        <span className="text-[11px] text-muted-foreground truncate block">
                          {repo.description}
                        </span>
                      ) : null}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {isExcluded ? (
                        <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                          Added
                        </span>
                      ) : null}
                      {repo.language ? (
                        <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                          {repo.language}
                        </span>
                      ) : null}
                      {repo.is_private ? <Shield className="h-3 w-3 text-muted-foreground" /> : null}
                    </div>
                  </label>
                )
              })}
            </div>
          ) : null}

          {selectedRepoUrls.size > 0 ? (
            <p className="text-[11px] text-muted-foreground">
              {selectedRepoUrls.size} repositor{selectedRepoUrls.size === 1 ? 'y' : 'ies'} selected
            </p>
          ) : null}
        </>
      )}
    </div>
  )
}
