import { useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileCheck, History, Plus, Shield, Trash2 } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { FeatureGate } from '@/components/FeatureGate'
import { MetricCard } from '@/components/MetricCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import {
  activatePolicy,
  createPolicy,
  createWaiver,
  deactivateWaiver,
  deletePolicy,
  fetchAuditEvents,
  fetchPolicies,
  fetchWaivers,
  updatePolicy,
  type PolicyProfile,
  type PolicyProfileCreate,
  type PolicyProfileUpdate,
  type WaiverCreate,
} from '@/lib/api'
import { useAuth } from '@/lib/useAuth'
import { useLicense } from '@/lib/hooks/useLicense'

type PolicyDialogState = {
  open: boolean
  mode: 'create' | 'edit'
  policy: PolicyProfile | null
}

type PolicyFormState = {
  name: string
  description: string
  repo_pattern: string
  branch_pattern: string
  max_critical_findings: string
  max_high_findings: string
  min_quality_score: string
  is_default: boolean
}

type WaiverFormState = {
  repo_pattern: string
  branch_pattern: string
  category: string
  rule_id: string
  fingerprint: string
  file_path: string
  reason: string
  expires_at: string
}

const EMPTY_POLICY_FORM: PolicyFormState = {
  name: '',
  description: '',
  repo_pattern: '',
  branch_pattern: '',
  max_critical_findings: '0',
  max_high_findings: '5',
  min_quality_score: '70',
  is_default: false,
}

const EMPTY_WAIVER_FORM: WaiverFormState = {
  repo_pattern: '',
  branch_pattern: '',
  category: '',
  rule_id: '',
  fingerprint: '',
  file_path: '',
  reason: '',
  expires_at: '',
}

function policyFormFromProfile(policy: PolicyProfile): PolicyFormState {
  return {
    name: policy.name,
    description: policy.description ?? '',
    repo_pattern: policy.repo_pattern ?? '',
    branch_pattern: policy.branch_pattern ?? '',
    max_critical_findings: String(policy.max_critical_findings),
    max_high_findings: String(policy.max_high_findings),
    min_quality_score: String(policy.min_quality_score),
    is_default: policy.is_default,
  }
}

function policyKindTone(kind: string): 'default' | 'primary' {
  return kind === 'preset' ? 'default' : 'primary'
}

export function PoliciesPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const { hasFeature } = useLicense()
  const isTenantAdmin = user?.role === 'admin'
  const [policyDialog, setPolicyDialog] = useState<PolicyDialogState>({
    open: false,
    mode: 'create',
    policy: null,
  })
  const [policyForm, setPolicyForm] = useState<PolicyFormState>(EMPTY_POLICY_FORM)
  const [policyToDelete, setPolicyToDelete] = useState<PolicyProfile | null>(null)
  const [waiverOpen, setWaiverOpen] = useState(false)
  const [waiverForm, setWaiverForm] = useState<WaiverFormState>(EMPTY_WAIVER_FORM)

  const policiesQuery = useQuery({ queryKey: ['policies'], queryFn: fetchPolicies })
  const waiversQuery = useQuery({ queryKey: ['waivers'], queryFn: fetchWaivers })
  const auditQuery = useQuery({
    queryKey: ['audit-events'],
    queryFn: fetchAuditEvents,
    enabled: hasFeature('audit_extended') && isTenantAdmin,
  })

  const invalidateGovernance = () => {
    queryClient.invalidateQueries({ queryKey: ['policies'] })
    queryClient.invalidateQueries({ queryKey: ['waivers'] })
    queryClient.invalidateQueries({ queryKey: ['audit-events'] })
  }

  const createPolicyMutation = useMutation({
    mutationFn: (payload: PolicyProfileCreate) => createPolicy(payload),
    onSuccess: () => {
      invalidateGovernance()
      closePolicyDialog()
    },
  })

  const updatePolicyMutation = useMutation({
    mutationFn: ({ policyId, payload }: { policyId: number; payload: PolicyProfileUpdate }) =>
      updatePolicy(policyId, payload),
    onSuccess: () => {
      invalidateGovernance()
      closePolicyDialog()
    },
  })

  const activatePolicyMutation = useMutation({
    mutationFn: (policyId: number) => activatePolicy(policyId),
    onSuccess: invalidateGovernance,
  })

  const deletePolicyMutation = useMutation({
    mutationFn: (policyId: number) => deletePolicy(policyId),
    onSuccess: () => {
      invalidateGovernance()
      setPolicyToDelete(null)
    },
  })

  const createWaiverMutation = useMutation({
    mutationFn: (payload: WaiverCreate) => createWaiver(payload),
    onSuccess: () => {
      invalidateGovernance()
      setWaiverOpen(false)
      setWaiverForm(EMPTY_WAIVER_FORM)
    },
  })

  const deactivateWaiverMutation = useMutation({
    mutationFn: (waiverId: number) => deactivateWaiver(waiverId),
    onSuccess: invalidateGovernance,
  })

  const policies = policiesQuery.data ?? []
  const waivers = waiversQuery.data ?? []
  const auditEvents = auditQuery.data ?? []
  const presetPolicies = policies.filter((policy) => policy.kind === 'preset')
  const customPolicies = policies.filter((policy) => policy.kind === 'custom')

  if ((policiesQuery.isLoading && !policiesQuery.data) || (waiversQuery.isLoading && !waiversQuery.data)) {
    return (
      <div className="flex justify-center py-20">
        <p className="text-sm text-muted-foreground">Loading policies...</p>
      </div>
    )
  }

  if (policiesQuery.isError) {
    return (
      <EmptyState
        body="Policy profiles could not be loaded. Refresh the page and verify the API is reachable."
        title="Policies unavailable"
      />
    )
  }

  function openCreatePolicyDialog() {
    setPolicyDialog({ open: true, mode: 'create', policy: null })
    setPolicyForm(EMPTY_POLICY_FORM)
  }

  function openEditPolicyDialog(policy: PolicyProfile) {
    setPolicyDialog({ open: true, mode: 'edit', policy })
    setPolicyForm(policyFormFromProfile(policy))
  }

  function closePolicyDialog() {
    setPolicyDialog({ open: false, mode: 'create', policy: null })
    setPolicyForm(EMPTY_POLICY_FORM)
  }

  function submitPolicy() {
    const payload = {
      name: policyForm.name.trim(),
      description: policyForm.description.trim() || undefined,
      repo_pattern: policyForm.repo_pattern.trim() || undefined,
      branch_pattern: policyForm.branch_pattern.trim() || undefined,
      max_critical_findings: Number(policyForm.max_critical_findings || '0'),
      max_high_findings: Number(policyForm.max_high_findings || '0'),
      min_quality_score: Number(policyForm.min_quality_score || '0'),
      is_default: policyForm.is_default,
    }

    if (policyDialog.mode === 'edit' && policyDialog.policy) {
      updatePolicyMutation.mutate({
        policyId: policyDialog.policy.id,
        payload,
      })
      return
    }

    createPolicyMutation.mutate({
      ...payload,
      kind: 'custom',
    })
  }

  function submitWaiver() {
    createWaiverMutation.mutate({
      tenant_slug: 'current',
      repo_pattern: waiverForm.repo_pattern.trim() || undefined,
      branch_pattern: waiverForm.branch_pattern.trim() || undefined,
      category: waiverForm.category.trim() || undefined,
      rule_id: waiverForm.rule_id.trim() || undefined,
      fingerprint: waiverForm.fingerprint.trim() || undefined,
      file_path: waiverForm.file_path.trim() || undefined,
      reason: waiverForm.reason.trim(),
      expires_at: waiverForm.expires_at ? new Date(waiverForm.expires_at).toISOString() : undefined,
      is_active: true,
    })
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">Governance</p>
        <h1 className="text-2xl font-bold tracking-tight">Policies</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Preset quality gates, custom policy rules, waivers, and tenant audit history.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <MetricCard
          detail="Built-in and custom gate profiles"
          icon={<Shield size={16} />}
          label="Profiles"
          value={String(policies.length)}
        />
        <MetricCard
          detail="Active suppression rules"
          icon={<FileCheck size={16} />}
          label="Waivers"
          value={String(waivers.filter((waiver) => waiver.is_active).length)}
        />
        <MetricCard
          detail="Mutation history"
          icon={<History size={16} />}
          label="Audit events"
          value={hasFeature('audit_extended') ? (isTenantAdmin ? String(auditEvents.length) : 'Admin') : 'Pro'}
        />
      </div>

      {waiversQuery.isError ? (
        <div className="rounded-sm border border-warning/30 bg-warning/5 px-4 py-3 text-sm text-warning">
          Waivers could not be loaded. Policy profiles are still available, but suppression history is incomplete.
        </div>
      ) : null}

      {auditQuery.isError ? (
        <div className="rounded-sm border border-warning/30 bg-warning/5 px-4 py-3 text-sm text-warning">
          Audit history could not be loaded right now.
        </div>
      ) : null}

      <Card>
        <CardHeader className="flex items-center justify-between px-6 pt-5">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
              Enforcement
            </p>
            <h2 className="text-lg font-semibold">Policy profiles</h2>
          </div>
          {hasFeature('custom_policies') && isTenantAdmin ? (
            <Button color="primary" size="sm" onClick={openCreatePolicyDialog}>
              <Plus size={14} />
              New custom policy
            </Button>
          ) : isTenantAdmin ? (
            <Badge variant="flat">Presets only on Community</Badge>
          ) : (
            <Badge variant="flat">Tenant admin required</Badge>
          )}
        </CardHeader>
        <Separator />
        <CardContent className="space-y-4 p-6">
          {policies.length === 0 ? (
            <EmptyState body="No policy profiles stored for this tenant." title="No policies" />
          ) : (
            <>
              <div className="grid gap-3 lg:grid-cols-3">
                {presetPolicies.map((policy) => (
                  <Card className="bg-muted/50" key={policy.id}>
                    <CardContent className="space-y-3 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-semibold">{policy.name}</p>
                            <Badge color={policyKindTone(policy.kind)} variant="flat">
                              {policy.preset_key ?? policy.kind}
                            </Badge>
                          </div>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {policy.description ?? 'Preset policy'}
                          </p>
                        </div>
                        {policy.is_default ? (
                          <Badge color="success" variant="dot">
                            Active
                          </Badge>
                        ) : isTenantAdmin ? (
                          <Button
                            size="sm"
                            variant="flat"
                            onClick={() => activatePolicyMutation.mutate(policy.id)}
                          >
                            Activate
                          </Button>
                        ) : (
                          <Badge variant="flat">Admin only</Badge>
                        )}
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-center">
                        <div className="rounded-sm border border-border bg-card px-3 py-2">
                          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Critical</p>
                          <p className="text-lg font-bold">{policy.max_critical_findings}</p>
                        </div>
                        <div className="rounded-sm border border-border bg-card px-3 py-2">
                          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">High</p>
                          <p className="text-lg font-bold">{policy.max_high_findings}</p>
                        </div>
                        <div className="rounded-sm border border-border bg-card px-3 py-2">
                          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Min Quality</p>
                          <p className="text-lg font-bold">{policy.min_quality_score}</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              <Card className="bg-muted/40">
                <CardHeader className="px-6 pt-5">
                  <div>
                    <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
                      Pro+
                    </p>
                    <h3 className="text-base font-semibold">Custom policies</h3>
                  </div>
                </CardHeader>
                <Separator />
                <CardContent className="p-0">
                  {customPolicies.length === 0 ? (
                    <div className="p-6">
                      <EmptyState
                        body={
                          isTenantAdmin
                            ? 'Custom policy creation is available on Pro and Enterprise plans.'
                            : 'Tenant admins can create custom policy profiles on Pro and Enterprise plans.'
                        }
                        title="No custom policies"
                      />
                    </div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Name</TableHead>
                          <TableHead>Scope</TableHead>
                          <TableHead>Thresholds</TableHead>
                          <TableHead>Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {customPolicies.map((policy) => (
                          <TableRow key={policy.id}>
                            <TableCell>
                              <div className="space-y-1">
                                <div className="flex items-center gap-2">
                                  <span className="text-sm font-medium">{policy.name}</span>
                                  <Badge color="primary" variant="flat">
                                    custom
                                  </Badge>
                                  {policy.is_default ? (
                                    <Badge color="success" variant="dot">
                                      Active
                                    </Badge>
                                  ) : null}
                                </div>
                                <p className="text-xs text-muted-foreground">{policy.description ?? 'No description'}</p>
                              </div>
                            </TableCell>
                            <TableCell className="space-y-1 text-xs text-muted-foreground">
                              <div>Repo: <span className="font-mono">{policy.repo_pattern ?? '*'}</span></div>
                              <div>Branch: <span className="font-mono">{policy.branch_pattern ?? '*'}</span></div>
                            </TableCell>
                            <TableCell className="text-xs text-muted-foreground">
                              C:{policy.max_critical_findings} / H:{policy.max_high_findings} / Q:{policy.min_quality_score}
                            </TableCell>
                            <TableCell>
                              <div className="flex flex-wrap gap-2">
                                 {!policy.is_default && isTenantAdmin ? (
                                   <Button
                                     size="sm"
                                     variant="flat"
                                    onClick={() => activatePolicyMutation.mutate(policy.id)}
                                  >
                                    Activate
                                  </Button>
                                ) : null}
                                 {isTenantAdmin ? (
                                   <>
                                     <Button size="sm" variant="flat" onClick={() => openEditPolicyDialog(policy)}>
                                       Edit
                                     </Button>
                                     <Button
                                       color="danger"
                                       size="sm"
                                       variant="flat"
                                       onClick={() => setPolicyToDelete(policy)}
                                     >
                                       <Trash2 size={14} />
                                       Delete
                                     </Button>
                                   </>
                                 ) : (
                                   <span className="text-xs text-muted-foreground">Tenant admin required</span>
                                 )}
                               </div>
                             </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex items-center justify-between px-6 pt-5">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
              Suppression
            </p>
            <h2 className="text-lg font-semibold">Waivers</h2>
          </div>
          {!isTenantAdmin ? (
            <Badge variant="flat">Tenant admin required</Badge>
          ) : (
            <FeatureGate
              feature="advanced_policies"
              fallback={<Badge variant="flat">Enterprise for waiver management</Badge>}
            >
              <Button color="primary" size="sm" onClick={() => setWaiverOpen(true)}>
                <Plus size={14} />
                Create waiver
              </Button>
            </FeatureGate>
          )}
        </CardHeader>
        <Separator />
        <CardContent className="p-0">
          {waiversQuery.isError ? (
            <div className="p-6">
              <EmptyState body="Waiver data is unavailable right now." title="Waivers unavailable" />
            </div>
          ) : waivers.length === 0 ? (
            <div className="p-6">
              <EmptyState body="No waivers stored for this tenant." title="No waivers" />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Reason</TableHead>
                  <TableHead>Match</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {waivers.map((waiver) => (
                  <TableRow key={waiver.id}>
                    <TableCell>
                      <div className="space-y-1">
                        <p className="text-sm font-medium">{waiver.reason}</p>
                        <p className="text-xs text-muted-foreground">
                          Created {new Date(waiver.created_at).toLocaleString()}
                        </p>
                      </div>
                    </TableCell>
                    <TableCell className="space-y-1 text-xs text-muted-foreground">
                      <div>Repo: <span className="font-mono">{waiver.repo_pattern ?? '*'}</span></div>
                      <div>Branch: <span className="font-mono">{waiver.branch_pattern ?? '*'}</span></div>
                      <div>Rule: <span className="font-mono">{waiver.rule_id ?? waiver.fingerprint ?? 'Any'}</span></div>
                    </TableCell>
                    <TableCell>
                      <Badge color={waiver.is_active ? 'success' : 'default'} variant="flat">
                        {waiver.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <FeatureGate feature="advanced_policies" fallback={null}>
                        {waiver.is_active && isTenantAdmin ? (
                          <Button
                            color="danger"
                            size="sm"
                            variant="flat"
                            onClick={() => deactivateWaiverMutation.mutate(waiver.id)}
                          >
                            Deactivate
                          </Button>
                        ) : waiver.is_active ? (
                          <span className="text-xs text-muted-foreground">Tenant admin required</span>
                        ) : null}
                      </FeatureGate>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <FeatureGate feature="audit_extended">
        <Card>
          <CardHeader className="px-6 pt-5">
            <div>
              <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
                Audit
              </p>
              <h2 className="text-lg font-semibold">Governance events</h2>
            </div>
          </CardHeader>
          <Separator />
          <CardContent className="p-0">
            {!isTenantAdmin ? (
              <div className="p-6">
                <EmptyState body="Tenant admin access is required to view governance audit history." title="Admin only" />
              </div>
            ) : auditEvents.length === 0 ? (
              <div className="p-6">
                <EmptyState body="No audit events recorded yet." title="No audit history" />
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>When</TableHead>
                    <TableHead>Actor</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Entity</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {auditEvents.map((event) => (
                    <TableRow key={event.id}>
                      <TableCell className="text-xs text-muted-foreground">
                        {new Date(event.created_at).toLocaleString()}
                      </TableCell>
                      <TableCell>{event.actor}</TableCell>
                      <TableCell>
                        <span className="font-mono text-xs">{event.action}</span>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {event.entity_type}
                        {event.entity_id ? `:${event.entity_id}` : ''}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </FeatureGate>

      <Dialog open={policyDialog.open} onOpenChange={(open) => !open && closePolicyDialog()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {policyDialog.mode === 'create' ? 'Create Custom Policy' : 'Edit Custom Policy'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Name</Label>
                <Input
                  value={policyForm.name}
                  onChange={(event) => setPolicyForm((current) => ({ ...current, name: event.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label>Minimum quality score</Label>
                <Input
                  type="number"
                  value={policyForm.min_quality_score}
                  onChange={(event) =>
                    setPolicyForm((current) => ({ ...current, min_quality_score: event.target.value }))
                  }
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Textarea
                rows={3}
                value={policyForm.description}
                onChange={(event) =>
                  setPolicyForm((current) => ({ ...current, description: event.target.value }))
                }
              />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Repo pattern</Label>
                <Input
                  placeholder="https://example.com/*"
                  value={policyForm.repo_pattern}
                  onChange={(event) =>
                    setPolicyForm((current) => ({ ...current, repo_pattern: event.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Branch pattern</Label>
                <Input
                  placeholder="main"
                  value={policyForm.branch_pattern}
                  onChange={(event) =>
                    setPolicyForm((current) => ({ ...current, branch_pattern: event.target.value }))
                  }
                />
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Max critical findings</Label>
                <Input
                  type="number"
                  value={policyForm.max_critical_findings}
                  onChange={(event) =>
                    setPolicyForm((current) => ({ ...current, max_critical_findings: event.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Max high findings</Label>
                <Input
                  type="number"
                  value={policyForm.max_high_findings}
                  onChange={(event) =>
                    setPolicyForm((current) => ({ ...current, max_high_findings: event.target.value }))
                  }
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                checked={policyForm.is_default}
                id="policy-default"
                onCheckedChange={(checked) =>
                  setPolicyForm((current) => ({ ...current, is_default: checked === true }))
                }
              />
              <Label htmlFor="policy-default">Make this the default policy</Label>
            </div>
            {createPolicyMutation.isError || updatePolicyMutation.isError ? (
              <p className="text-sm text-danger">
                {createPolicyMutation.error instanceof Error
                  ? createPolicyMutation.error.message
                  : updatePolicyMutation.error instanceof Error
                    ? updatePolicyMutation.error.message
                    : 'Saving the policy failed.'}
              </p>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="flat" onClick={closePolicyDialog}>
              Cancel
            </Button>
            <Button
              color="primary"
              isLoading={createPolicyMutation.isPending || updatePolicyMutation.isPending}
              onClick={submitPolicy}
            >
              Save policy
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={policyToDelete !== null} onOpenChange={(open) => !open && setPolicyToDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete custom policy</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              Delete <span className="font-semibold">{policyToDelete?.name}</span>? This only removes the policy profile and does not touch historical scan data.
            </p>
            {deletePolicyMutation.isError ? (
              <p className="text-sm text-danger">
                {deletePolicyMutation.error instanceof Error
                  ? deletePolicyMutation.error.message
                  : 'Deleting the policy failed.'}
              </p>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="flat" onClick={() => setPolicyToDelete(null)}>
              Cancel
            </Button>
            <Button
              color="danger"
              isLoading={deletePolicyMutation.isPending}
              onClick={() => {
                if (policyToDelete) {
                  deletePolicyMutation.mutate(policyToDelete.id)
                }
              }}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isTenantAdmin && waiverOpen} onOpenChange={(open) => !open && setWaiverOpen(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create waiver</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Reason</Label>
              <Textarea
                rows={3}
                value={waiverForm.reason}
                onChange={(event) =>
                  setWaiverForm((current) => ({ ...current, reason: event.target.value }))
                }
              />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Repo pattern</Label>
                <Input
                  value={waiverForm.repo_pattern}
                  onChange={(event) =>
                    setWaiverForm((current) => ({ ...current, repo_pattern: event.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Branch pattern</Label>
                <Input
                  value={waiverForm.branch_pattern}
                  onChange={(event) =>
                    setWaiverForm((current) => ({ ...current, branch_pattern: event.target.value }))
                  }
                />
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Category</Label>
                <Input
                  value={waiverForm.category}
                  onChange={(event) =>
                    setWaiverForm((current) => ({ ...current, category: event.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Rule ID</Label>
                <Input
                  value={waiverForm.rule_id}
                  onChange={(event) =>
                    setWaiverForm((current) => ({ ...current, rule_id: event.target.value }))
                  }
                />
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Fingerprint</Label>
                <Input
                  value={waiverForm.fingerprint}
                  onChange={(event) =>
                    setWaiverForm((current) => ({ ...current, fingerprint: event.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>File path</Label>
                <Input
                  value={waiverForm.file_path}
                  onChange={(event) =>
                    setWaiverForm((current) => ({ ...current, file_path: event.target.value }))
                  }
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Expires at</Label>
              <Input
                type="datetime-local"
                value={waiverForm.expires_at}
                onChange={(event) =>
                  setWaiverForm((current) => ({ ...current, expires_at: event.target.value }))
                }
              />
            </div>
            {createWaiverMutation.isError ? (
              <p className="text-sm text-danger">
                {createWaiverMutation.error instanceof Error
                  ? createWaiverMutation.error.message
                  : 'Creating the waiver failed.'}
              </p>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="flat" onClick={() => setWaiverOpen(false)}>
              Cancel
            </Button>
            <Button
              color="primary"
              isLoading={createWaiverMutation.isPending}
              onClick={submitWaiver}
            >
              Create waiver
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
