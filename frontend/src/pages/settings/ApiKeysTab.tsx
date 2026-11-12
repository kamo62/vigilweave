import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, Key, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { EmptyState } from '@/components/EmptyState'
import { MetricCard } from '@/components/MetricCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { createApiKey, fetchApiKeys, revokeApiKey } from '@/lib/api'
import {
  clearRuntimeAuthConfig,
  getAuthHeaders,
  getRuntimeAuthConfig,
  setRuntimeAuthConfig,
} from '@/lib/auth'

export function ApiKeysTab() {
  const queryClient = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [newKeyScopes, setNewKeyScopes] = useState('scan:read, scan:write')
  const [createdSecret, setCreatedSecret] = useState<string | null>(null)
  const [runtimeApiKey, setRuntimeApiKeyState] = useState(() => getRuntimeAuthConfig().apiKey)
  const [runtimeTenant, setRuntimeTenantState] = useState(() => getRuntimeAuthConfig().tenant)
  const [authSavedMessage, setAuthSavedMessage] = useState<string | null>(null)

  const keysQuery = useQuery({
    queryKey: ['api-keys'],
    queryFn: fetchApiKeys,
  })

  const createMutation = useMutation({
    mutationFn: createApiKey,
    onSuccess: (response) => {
      setCreatedSecret(response.api_key)
      setNewKeyName('')
      setNewKeyScopes('scan:read, scan:write')
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
    },
  })

  const revokeMutation = useMutation({
    mutationFn: revokeApiKey,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['api-keys'] }),
  })

  const keys = keysQuery.data ?? []
  const activeKeys = keys.filter((k) => k.is_active)

  if (keysQuery.isLoading && !keysQuery.data) {
    return <div className="py-12 text-center text-sm text-muted-foreground">Loading API keys...</div>
  }

  if (keysQuery.isError) {
    return (
      <EmptyState
        title="API keys unavailable"
        body="API keys could not be loaded. Refresh the page and verify the API is reachable."
      />
    )
  }

  function handleCreate() {
    createMutation.mutate({
      name: newKeyName.trim(),
      scopes: newKeyScopes
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
    })
  }

  function handleCloseModal() {
    setCreatedSecret(null)
    setCreateOpen(false)
  }

  function handleSaveRuntimeAuth() {
    setRuntimeAuthConfig({ apiKey: runtimeApiKey, tenant: runtimeTenant })
    setAuthSavedMessage('Saved. New requests will use this key and tenant.')
  }

  function handleClearRuntimeAuth() {
    clearRuntimeAuthConfig()
    setRuntimeApiKeyState('')
    setRuntimeTenantState('')
    setAuthSavedMessage('Cleared. Falling back to environment auth values.')
  }

  function applyCreatedKeyToRuntimeAuth() {
    if (!createdSecret) {
      return
    }
    setRuntimeAuthConfig({ apiKey: createdSecret, tenant: runtimeTenant })
    setRuntimeApiKeyState(createdSecret)
    setAuthSavedMessage('Created key is now active for this browser.')
  }

  const activeAuthHeaders = getAuthHeaders()
  const activeAuthSummary = [
    activeAuthHeaders.Authorization ? 'authorization=present' : 'authorization=missing',
    activeAuthHeaders['X-VigilWeave-Tenant']
      ? `tenant=${activeAuthHeaders['X-VigilWeave-Tenant']}`
      : 'tenant=missing',
  ].join(' | ')

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">API Keys</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage API keys for CI, scripts, IDE integrations, and other programmatic access.
          </p>
        </div>
        <Button color="primary" onClick={() => setCreateOpen(true)}>
          <Plus size={16} />
          Create Key
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        <MetricCard
          detail="Total keys created"
          icon={<Key size={16} />}
          label="Total Keys"
          value={String(keys.length)}
        />
        <MetricCard
          detail="Currently active"
          icon={<Key size={16} />}
          label="Active"
          tone={activeKeys.length > 0 ? 'success' : 'default'}
          value={String(activeKeys.length)}
        />
      </div>

      <Card>
        <CardContent className="space-y-3 p-4">
          <div>
            <p className="text-sm font-semibold">Browser API Override</p>
            <p className="text-xs text-muted-foreground">
              Optionally attach an API key to requests from this browser when you want to test automation flows.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label>API Key</Label>
              <Input
                placeholder="vw_..."
                value={runtimeApiKey}
                onChange={(event) => setRuntimeApiKeyState(event.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label>Tenant</Label>
              <Input
                placeholder="default"
                value={runtimeTenant}
                onChange={(event) => setRuntimeTenantState(event.target.value)}
              />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" variant="flat" onClick={handleSaveRuntimeAuth}>
              Save Runtime Auth
            </Button>
            <Button size="sm" variant="light" onClick={handleClearRuntimeAuth}>
              Clear Runtime Auth
            </Button>
            <span className="text-xs text-muted-foreground">
              Active headers: {activeAuthSummary}
            </span>
          </div>
          {authSavedMessage ? <p className="text-xs text-success">{authSavedMessage}</p> : null}
        </CardContent>
      </Card>

      {revokeMutation.isError ? (
        <div className="rounded-sm border border-danger/30 bg-danger/[0.06] px-4 py-3 text-sm text-danger">
          {revokeMutation.error instanceof Error ? revokeMutation.error.message : 'Revoking the API key failed.'}
        </div>
      ) : null}

      {keys.length === 0 ? (
        <EmptyState
          body="Create an API key for programmatic access after signing in as an admin."
          title="No API keys"
        />
      ) : (
        <div className="space-y-3">
          {keys.map((apiKey) => (
            <Card className="bg-muted/50" key={apiKey.id}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-3">
                      <p className="text-sm font-semibold">{apiKey.name}</p>
                      <Badge
                        color={apiKey.is_active ? 'success' : 'default'}
                        variant="flat"
                      >
                        {apiKey.is_active ? 'Active' : 'Revoked'}
                      </Badge>
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                      <span className="font-mono">{apiKey.key_prefix}...</span>
                      <span>Created: {new Date(apiKey.created_at).toLocaleDateString()}</span>
                      {apiKey.last_used_at ? (
                        <span>
                          Last used: {new Date(apiKey.last_used_at).toLocaleDateString()}
                        </span>
                      ) : (
                        <span>Never used</span>
                      )}
                    </div>
                    {apiKey.scopes && apiKey.scopes.length > 0 ? (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {apiKey.scopes.map((scope) => (
                          <Badge key={scope} variant="flat">
                            {scope}
                          </Badge>
                        ))}
                      </div>
                    ) : null}
                  </div>
                  {apiKey.is_active ? (
                    <Button
                      color="danger"
                      isIconOnly
                      isLoading={revokeMutation.isPending}
                      size="sm"
                      variant="flat"
                      onClick={() => revokeMutation.mutate(apiKey.id)}
                    >
                      <Trash2 size={14} />
                    </Button>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create API key modal */}
      <Dialog open={createOpen} onOpenChange={handleCloseModal}>
        <DialogContent>
          {createdSecret ? (
            <>
              <DialogHeader>
                <DialogTitle>API Key Created</DialogTitle>
              </DialogHeader>
              <div>
                <p className="text-sm text-muted-foreground">
                  Copy your API key now. It will not be shown again.
                </p>
                <Card className="mt-3 border border-success/30 bg-success/[0.06]">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between gap-3">
                      <code className="break-all text-xs">{createdSecret}</code>
                      <Button
                        isIconOnly
                        size="sm"
                        variant="flat"
                        onClick={() => void navigator.clipboard.writeText(createdSecret)}
                      >
                        <Copy size={14} />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </div>
              <DialogFooter>
                <Button variant="flat" onClick={applyCreatedKeyToRuntimeAuth}>
                  Use In Browser
                </Button>
                <Button color="primary" onClick={handleCloseModal}>
                  Done
                </Button>
              </DialogFooter>
            </>
          ) : (
            <>
              <DialogHeader>
                <DialogTitle>Create API Key</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Name</Label>
                  <Input
                    placeholder="CI pipeline key"
                    value={newKeyName}
                    onChange={(e) => setNewKeyName(e.target.value)}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label>Scopes</Label>
                  <Input
                    placeholder="scan:read, scan:write"
                    value={newKeyScopes}
                    onChange={(e) => setNewKeyScopes(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Comma-separated scopes (e.g. scan:read, scan:write, admin)
                  </p>
                </div>
                {createMutation.isError ? (
                  <p className="text-sm text-danger">
                    {createMutation.error instanceof Error
                      ? createMutation.error.message
                      : 'Failed to create API key. Check permissions.'}
                  </p>
                ) : null}
              </div>
              <DialogFooter>
                <Button variant="flat" onClick={handleCloseModal}>
                  Cancel
                </Button>
                <Button
                  color="primary"
                  disabled={!newKeyName.trim()}
                  isLoading={createMutation.isPending}
                  onClick={handleCreate}
                >
                  Create
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
