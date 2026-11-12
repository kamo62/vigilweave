import { useMemo, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ShieldCheck, Users } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import {
  deleteSaaSTenantLicense,
  fetchPlatformUsers,
  fetchSaaSTenantLicenses,
  updatePlatformUserRole,
  updateSaaSTenantLicense,
} from '@/lib/api'
import { useAuth } from '@/lib/useAuth'

type TenantTier = 'community' | 'pro' | 'enterprise'
type PlatformRole = 'none' | 'operator'

export function SaaSAdminTab() {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const [tenantDrafts, setTenantDrafts] = useState<Record<string, { tier: TenantTier; note: string }>>({})
  const [newTenantSlug, setNewTenantSlug] = useState('')
  const [newTenantTier, setNewTenantTier] = useState<TenantTier>('enterprise')
  const [newTenantNote, setNewTenantNote] = useState('')
  const [error, setError] = useState<string | null>(null)

  const tenantLicensesQuery = useQuery({
    queryKey: ['saas-tenant-licenses'],
    queryFn: fetchSaaSTenantLicenses,
  })
  const platformUsersQuery = useQuery({
    queryKey: ['saas-platform-users'],
    queryFn: fetchPlatformUsers,
  })

  const saveTenantMutation = useMutation({
    mutationFn: ({ tenantSlug, tier, note }: { tenantSlug: string; tier: TenantTier; note: string }) =>
      updateSaaSTenantLicense(tenantSlug, { tier, note: note.trim() || undefined }),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['saas-tenant-licenses'] })
      setTenantDrafts((current) => {
        const next = { ...current }
        delete next[variables.tenantSlug]
        return next
      })
      setNewTenantSlug('')
      setNewTenantTier('enterprise')
      setNewTenantNote('')
      setError(null)
    },
    onError: (err: Error) => setError(err.message),
  })

  const resetTenantMutation = useMutation({
    mutationFn: deleteSaaSTenantLicense,
    onSuccess: (__, tenantSlug) => {
      void queryClient.invalidateQueries({ queryKey: ['saas-tenant-licenses'] })
      setTenantDrafts((current) => {
        const next = { ...current }
        delete next[tenantSlug]
        return next
      })
      setError(null)
    },
    onError: (err: Error) => setError(err.message),
  })

  const platformRoleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: PlatformRole }) =>
      updatePlatformUserRole(userId, role),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['saas-platform-users'] })
      void queryClient.invalidateQueries({ queryKey: ['auth-user'] })
      setError(null)
    },
    onError: (err: Error) => setError(err.message),
  })

  const operatorCount = useMemo(
    () => (platformUsersQuery.data ?? []).filter((platformUser) => platformUser.platform_role === 'operator').length,
    [platformUsersQuery.data],
  )

  if (user?.platform_role !== 'operator') {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-muted-foreground">
          Platform operator access is required to manage hosted SaaS tenants.
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {error ? (
        <div className="rounded-sm border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      <Card>
        <CardHeader className="px-6 pt-5">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
              Hosted Plans
            </p>
            <h2 className="text-lg font-semibold">Tenant licensing</h2>
          </div>
        </CardHeader>
        <Separator />
        <CardContent className="space-y-4 p-6">
          {tenantLicensesQuery.isError ? (
            <div className="rounded-sm border border-warning/30 bg-warning/5 px-4 py-3 text-sm text-warning">
              Hosted tenant plans could not be loaded right now.
            </div>
          ) : null}

          <Card className="bg-card" key="new-tenant-override">
            <CardContent className="grid gap-4 p-4 md:grid-cols-[minmax(0,1.2fr)_180px_minmax(0,1fr)_140px]">
              <div className="space-y-2">
                <Label>Tenant slug</Label>
                <Input
                  placeholder="workos-org-acme"
                  value={newTenantSlug}
                  onChange={(event) => setNewTenantSlug(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Tier</Label>
                <Select value={newTenantTier} onValueChange={(value) => setNewTenantTier(value as TenantTier)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="community">Community</SelectItem>
                    <SelectItem value="pro">Pro</SelectItem>
                    <SelectItem value="enterprise">Enterprise</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Note</Label>
                <Input
                  placeholder="Paddle purchase, trial, or sales note"
                  value={newTenantNote}
                  onChange={(event) => setNewTenantNote(event.target.value)}
                />
              </div>
              <div className="flex items-end">
                <Button
                  className="w-full"
                  color="primary"
                  isLoading={saveTenantMutation.isPending}
                  disabled={!newTenantSlug.trim()}
                  onClick={() =>
                    saveTenantMutation.mutate({
                      tenantSlug: newTenantSlug.trim(),
                      tier: newTenantTier,
                      note: newTenantNote,
                    })
                  }
                >
                  Add tenant plan
                </Button>
              </div>
            </CardContent>
          </Card>

          {!tenantLicensesQuery.isLoading && !tenantLicensesQuery.isError && (tenantLicensesQuery.data ?? []).length === 0 ? (
            <EmptyState
              body="No hosted tenant plan records have been created yet. Add an override or wait for hosted tenants to appear."
              title="No tenant plans"
            />
          ) : (
            (tenantLicensesQuery.data ?? []).map((tenant) => {
              const draft = tenantDrafts[tenant.tenant_slug] ?? {
                tier: tenant.tier,
                note: tenant.note ?? '',
              }
              return (
                <Card className="bg-muted/40" key={tenant.tenant_slug}>
                  <CardContent className="space-y-4 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-semibold">{tenant.tenant_slug}</p>
                          <Badge variant="flat">{tenant.user_count} users</Badge>
                          <Badge color={tenant.source === 'override' ? 'primary' : 'default'} variant="flat">
                            {tenant.source === 'override' ? 'Override' : 'Default'}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          Effective tier: {tenant.tier}
                          {tenant.assigned_by ? ` · last assigned by ${tenant.assigned_by}` : ''}
                        </p>
                      </div>
                      <Button
                        disabled={tenant.source !== 'override' || resetTenantMutation.isPending}
                        size="sm"
                        variant="flat"
                        onClick={() => resetTenantMutation.mutate(tenant.tenant_slug)}
                      >
                        Reset to cloud default
                      </Button>
                    </div>

                    <div className="grid gap-4 md:grid-cols-[180px_minmax(0,1fr)_140px]">
                      <div className="space-y-2">
                        <Label>Tier</Label>
                        <Select
                          value={draft.tier}
                          onValueChange={(value) =>
                            setTenantDrafts((current) => ({
                              ...current,
                              [tenant.tenant_slug]: { ...draft, tier: value as TenantTier },
                            }))
                          }
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="community">Community</SelectItem>
                            <SelectItem value="pro">Pro</SelectItem>
                            <SelectItem value="enterprise">Enterprise</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label>Note</Label>
                        <Input
                          placeholder="Contract, trial, partner plan, or support note"
                          value={draft.note}
                          onChange={(event) =>
                            setTenantDrafts((current) => ({
                              ...current,
                              [tenant.tenant_slug]: { ...draft, note: event.target.value },
                            }))
                          }
                        />
                      </div>
                      <div className="flex items-end">
                        <Button
                          className="w-full"
                          color="primary"
                          isLoading={saveTenantMutation.isPending}
                          onClick={() =>
                            saveTenantMutation.mutate({
                              tenantSlug: tenant.tenant_slug,
                              tier: draft.tier,
                              note: draft.note,
                            })
                          }
                        >
                          Save plan
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )
            })
          )}
          {tenantLicensesQuery.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading hosted tenant plans...</p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="px-6 pt-5">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
              Platform Access
            </p>
            <h2 className="text-lg font-semibold">Platform operators</h2>
          </div>
        </CardHeader>
        <Separator />
        <CardContent className="space-y-3 p-6">
          {platformUsersQuery.isError ? (
            <div className="rounded-sm border border-warning/30 bg-warning/5 px-4 py-3 text-sm text-warning">
              Platform operator access records could not be loaded right now.
            </div>
          ) : null}

          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <ShieldCheck size={16} />
            <span>{operatorCount} persistent platform operators</span>
          </div>
          {!platformUsersQuery.isLoading && !platformUsersQuery.isError && (platformUsersQuery.data ?? []).length === 0 ? (
            <EmptyState body="No platform users are available to manage yet." title="No platform users" />
          ) : (
            (platformUsersQuery.data ?? []).map((platformUser) => {
              const isSelf = platformUser.id === user.id
              const isLastOperator =
                platformUser.platform_role === 'operator' && operatorCount <= 1
              return (
                <Card className="bg-muted/40" key={platformUser.id}>
                  <CardContent className="flex flex-wrap items-center gap-4 p-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-semibold">{platformUser.name || platformUser.email}</p>
                        <Badge variant="flat">{platformUser.tenant_slug}</Badge>
                        {platformUser.platform_role === 'operator' ? (
                          <Badge color="primary" variant="flat">
                            Operator
                          </Badge>
                        ) : null}
                      </div>
                      <p className="text-xs text-muted-foreground">{platformUser.email}</p>
                    </div>
                    <div className="w-[180px]">
                      <Select
                        value={platformUser.platform_role}
                        onValueChange={(value) =>
                          platformRoleMutation.mutate({
                            userId: platformUser.id,
                            role: value as PlatformRole,
                          })
                        }
                        disabled={platformRoleMutation.isPending || (isSelf && isLastOperator)}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">Tenant-only admin</SelectItem>
                          <SelectItem value="operator">Platform operator</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </CardContent>
                </Card>
              )
            })
          )}
          {platformUsersQuery.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading operator access...</p>
          ) : null}
          <div className="rounded-sm border border-border bg-card px-4 py-3 text-xs text-muted-foreground">
            <div className="flex items-start gap-2">
              <Users size={14} className="mt-0.5 shrink-0" />
              <p>
                Platform operators can manage tenant plans across the hosted VigilWeave cloud.
                Tenant admins remain scoped to their own organization and projects.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
