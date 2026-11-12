import type { ReactNode } from 'react'

import { EmptyState } from '@/components/EmptyState'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { SCMConnectionPublic, SCMOrganization, SCMRepository } from '@/lib/api'

type SCMRepoPickerProps = {
  connections: SCMConnectionPublic[]
  selectedConnectionId: string
  onConnectionChange: (connectionId: string) => void | Promise<void>
  selectedOrg: string
  onOrgChange: (org: string) => void | Promise<void>
  orgs: SCMOrganization[]
  repositories: SCMRepository[]
  selectedRepoUrls: Set<string>
  onSelectionChange: (next: Set<string>) => void
  selectionMode?: 'single' | 'multiple'
  connectionsLoading?: boolean
  connectionsError?: string | null
  organizationsLoading?: boolean
  repositoriesLoading?: boolean
  repositoriesError?: string | null
  emptyConnectionsContent?: ReactNode
}

export function SCMRepoPicker({
  connections,
  selectedConnectionId,
  onConnectionChange,
  selectedOrg,
  onOrgChange,
  orgs,
  repositories,
  selectedRepoUrls,
  onSelectionChange,
  selectionMode = 'multiple',
  connectionsLoading = false,
  connectionsError = null,
  organizationsLoading = false,
  repositoriesLoading = false,
  repositoriesError = null,
  emptyConnectionsContent,
}: SCMRepoPickerProps) {
  const selectedConnection = connections.find((connection) => String(connection.id) === selectedConnectionId)
  const supportsMyRepos = selectedConnection && ['github', 'gitlab'].includes(selectedConnection.provider)

  function toggleRepo(repoUrl: string): void {
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

  if (connectionsLoading) {
    return <p className="text-sm text-muted-foreground">Loading SCM connections...</p>
  }

  if (connectionsError) {
    return <p className="text-sm text-destructive">{connectionsError}</p>
  }

  if (connections.length === 0) {
    return (
      <>
        {emptyConnectionsContent ?? (
          <EmptyState
            title="No SCM connections"
            body="Add an SCM connection to browse private repositories without manually entering clone URLs."
          />
        )}
      </>
    )
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground">Connection</Label>
          <Select value={selectedConnectionId} onValueChange={(value) => void onConnectionChange(value)}>
            <SelectTrigger>
              <SelectValue placeholder="Select connection..." />
            </SelectTrigger>
            <SelectContent>
              {connections.map((connection) => (
                <SelectItem key={connection.id} value={String(connection.id)}>
                  {connection.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground">Organization</Label>
          <Select
            value={selectedOrg}
            onValueChange={(value) => void onOrgChange(value)}
            disabled={!selectedConnectionId || organizationsLoading}
          >
            <SelectTrigger>
              <SelectValue placeholder={organizationsLoading ? 'Loading organizations...' : 'Select org...'} />
            </SelectTrigger>
            <SelectContent>
              {supportsMyRepos ? <SelectItem value="_user">My Repositories</SelectItem> : null}
              {orgs.map((org) => (
                <SelectItem key={org.id} value={org.name}>
                  {org.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {repositoriesError ? <p className="text-sm text-destructive">{repositoriesError}</p> : null}

      {repositoriesLoading ? <p className="text-sm text-muted-foreground">Loading repositories...</p> : null}

      {selectedConnectionId && selectedOrg && repositories.length === 0 && !repositoriesLoading ? (
        <p className="text-sm text-muted-foreground">No repositories found for this selection.</p>
      ) : null}

      {repositories.length > 0 ? (
        <div className="max-h-64 space-y-2 overflow-y-auto">
          {repositories.map((repo) => {
            const isSelected = selectedRepoUrls.has(repo.clone_url)
            return (
              <label
                key={repo.id}
                className={`flex items-start gap-3 rounded-sm border px-3 py-3 text-sm transition-colors ${
                  isSelected ? 'border-primary bg-primary/5' : 'border-border hover:bg-muted/50'
                }`}
              >
                <Checkbox checked={isSelected} onCheckedChange={() => toggleRepo(repo.clone_url)} />
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{repo.full_name}</p>
                  {repo.description ? <p className="mt-1 text-xs text-muted-foreground">{repo.description}</p> : null}
                </div>
                <div className="text-right text-xs text-muted-foreground">
                  <p>{repo.is_private ? 'Private' : 'Public'}</p>
                  <p>{repo.default_branch || 'main'}</p>
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
    </div>
  )
}
