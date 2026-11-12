import { useState } from 'react'
import { Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { SCMConnectionCreate, SCMProvider } from '@/lib/api'

const PROVIDER_LABELS: Record<SCMProvider, string> = {
  github: 'GitHub',
  gitlab: 'GitLab',
  bitbucket: 'Bitbucket',
  azure_devops: 'Azure DevOps',
}

const PROVIDER_DEFAULTS: Record<SCMProvider, string> = {
  github: 'https://api.github.com',
  gitlab: 'https://gitlab.com',
  bitbucket: 'https://api.bitbucket.org',
  azure_devops: 'https://dev.azure.com',
}

type SCMConnectionFormProps = {
  onSubmit: (payload: SCMConnectionCreate) => Promise<void>
  onCancel?: () => void
  onSuccess?: () => void
  submitLabel?: string
  pendingLabel?: string
}

export function SCMConnectionForm({
  onSubmit,
  onCancel,
  onSuccess,
  submitLabel = 'Create connection',
  pendingLabel = 'Creating...',
}: SCMConnectionFormProps) {
  const [name, setName] = useState('')
  const [provider, setProvider] = useState<SCMProvider>('github')
  const [baseUrl, setBaseUrl] = useState(PROVIDER_DEFAULTS.github)
  const [token, setToken] = useState('')
  const [username, setUsername] = useState('')
  const [organization, setOrganization] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function handleProviderChange(nextProvider: SCMProvider) {
    setProvider(nextProvider)
    setBaseUrl(PROVIDER_DEFAULTS[nextProvider])
    setUsername('')
    setOrganization('')
  }

  function resetForm() {
    setName('')
    setProvider('github')
    setBaseUrl(PROVIDER_DEFAULTS.github)
    setToken('')
    setUsername('')
    setOrganization('')
    setError(null)
  }

  async function handleSubmit(): Promise<void> {
    if (!name.trim() || !token.trim()) {
      return
    }

    const extraConfig: Record<string, string> = {}
    if (provider === 'bitbucket' && username.trim()) {
      extraConfig.username = username.trim()
    }
    if (provider === 'azure_devops' && organization.trim()) {
      extraConfig.organization = organization.trim()
    }

    setPending(true)
    setError(null)
    try {
      await onSubmit({
        name: name.trim(),
        provider,
        base_url: baseUrl.trim(),
        token: token.trim(),
        extra_config: Object.keys(extraConfig).length > 0 ? extraConfig : null,
      })
      resetForm()
      onSuccess?.()
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Failed to create connection.')
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Provider</Label>
        <Select value={provider} onValueChange={(value) => handleProviderChange(value as SCMProvider)}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(PROVIDER_LABELS).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>Connection Name</Label>
        <Input placeholder="e.g. Acme GitHub" value={name} onChange={(event) => setName(event.target.value)} />
      </div>
      <div className="space-y-2">
        <Label>Base URL</Label>
        <Input placeholder={PROVIDER_DEFAULTS[provider]} value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} />
        <p className="text-[11px] text-muted-foreground">Change this for self-hosted instances.</p>
      </div>
      <div className="space-y-2">
        <Label>Personal Access Token</Label>
        <Input
          type="password"
          placeholder="Paste a token with repository read access"
          value={token}
          onChange={(event) => setToken(event.target.value)}
        />
      </div>
      {provider === 'bitbucket' ? (
        <div className="space-y-2">
          <Label>Username</Label>
          <Input placeholder="Bitbucket username" value={username} onChange={(event) => setUsername(event.target.value)} />
          <p className="text-[11px] text-muted-foreground">Required for Bitbucket app passwords and API tokens.</p>
        </div>
      ) : null}
      {provider === 'azure_devops' ? (
        <div className="space-y-2">
          <Label>Organization</Label>
          <Input placeholder="e.g. fabrikam" value={organization} onChange={(event) => setOrganization(event.target.value)} />
          <p className="text-[11px] text-muted-foreground">Your Azure DevOps organization name.</p>
        </div>
      ) : null}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <div className="flex gap-3">
        <Button type="button" onClick={() => void handleSubmit()} disabled={!name.trim() || !token.trim() || pending}>
          {pending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          {pending ? pendingLabel : submitLabel}
        </Button>
        {onCancel ? (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
      </div>
    </div>
  )
}
