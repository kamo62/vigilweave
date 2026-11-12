import { useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FolderTree, Layers, Pencil, Plus, Trash2, Users } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { MetricCard } from '@/components/MetricCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  addPortfolioProjects,
  createPortfolio,
  deletePortfolio,
  fetchPortfolioDetail,
  fetchPortfolios,
  fetchProjects,
  removePortfolioProject,
  updatePortfolio,
  type PortfolioCreate,
  type PortfolioDetail,
  type PortfolioPublic,
  type PortfolioUpdate,
  type ProjectPublic,
} from '@/lib/api'

type PortfolioFormState = {
  key: string
  name: string
  description: string
  selectionMode: 'manual' | 'tags' | 'regex' | 'all'
  selectionValue: string
  azureDevOpsOrg: string
  parentId: string
}

const EMPTY_FORM: PortfolioFormState = {
  key: '',
  name: '',
  description: '',
  selectionMode: 'manual',
  selectionValue: '',
  azureDevOpsOrg: '',
  parentId: 'none',
}

function collectBlockedParentIds(
  portfolios: PortfolioPublic[],
  rootPortfolioId: number | null,
): Set<number> {
  if (rootPortfolioId == null) {
    return new Set()
  }

  const blocked = new Set<number>([rootPortfolioId])
  const queue = [rootPortfolioId]

  while (queue.length > 0) {
    const currentId = queue.shift()
    if (currentId == null) {
      continue
    }
    for (const portfolio of portfolios) {
      if (portfolio.parent_id === currentId && !blocked.has(portfolio.id)) {
        blocked.add(portfolio.id)
        queue.push(portfolio.id)
      }
    }
  }

  return blocked
}

function PortfolioCard({
  portfolio,
  onEdit,
  onManage,
  onDelete,
}: {
  portfolio: PortfolioPublic
  onEdit: (portfolio: PortfolioPublic) => void
  onManage: (portfolio: PortfolioPublic) => void
  onDelete: (portfolio: PortfolioPublic) => void
}) {
  const detailQuery = useQuery({
    queryKey: ['portfolio-detail', portfolio.key],
    queryFn: () => fetchPortfolioDetail(portfolio.key),
  })
  const detail = detailQuery.data
  const gatePct = detail?.quality_gate_passed_pct
  const gateColor =
    gatePct == null ? 'default' : gatePct >= 90 ? 'success' : gatePct >= 70 ? 'warning' : 'danger'

  return (
    <Card className="bg-muted/50">
      <CardContent className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="truncate text-sm font-semibold">{portfolio.name}</p>
              <Badge variant="flat">{portfolio.selection_mode}</Badge>
            </div>
            <p className="font-mono text-xs text-muted-foreground">{portfolio.key}</p>
          </div>
          <Badge color={gateColor as 'success' | 'warning' | 'danger' | 'default'} variant="flat">
            {gatePct != null ? `${gatePct.toFixed(0)}% pass` : 'N/A'}
          </Badge>
        </div>

        {portfolio.description ? (
          <p className="text-xs text-muted-foreground">{portfolio.description}</p>
        ) : null}

        <div className="grid grid-cols-3 gap-2">
          <div>
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Projects</p>
            <p className="text-lg font-bold">{portfolio.project_count ?? 0}</p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Findings</p>
            <p className="text-lg font-bold">{detail?.total_findings ?? 0}</p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Critical</p>
            <p className={`text-lg font-bold ${(detail?.critical_findings ?? 0) > 0 ? 'text-danger' : ''}`}>
              {detail?.critical_findings ?? 0}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="flat" onClick={() => onEdit(portfolio)}>
            <Pencil size={14} />
            Edit
          </Button>
          <Button size="sm" variant="flat" onClick={() => onManage(portfolio)}>
            <Users size={14} />
            Manage
          </Button>
          <Button color="danger" size="sm" variant="flat" onClick={() => onDelete(portfolio)}>
            <Trash2 size={14} />
            Delete
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function formFromPortfolio(portfolio: PortfolioPublic): PortfolioFormState {
  return {
    key: portfolio.key,
    name: portfolio.name,
    description: portfolio.description ?? '',
    selectionMode: portfolio.selection_mode,
    selectionValue: portfolio.selection_value ?? '',
    azureDevOpsOrg: portfolio.azure_devops_org ?? '',
    parentId: portfolio.parent_id != null ? String(portfolio.parent_id) : 'none',
  }
}

export function PortfoliosTab() {
  const queryClient = useQueryClient()
  const [formOpen, setFormOpen] = useState(false)
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create')
  const [formState, setFormState] = useState<PortfolioFormState>(EMPTY_FORM)
  const [editingPortfolio, setEditingPortfolio] = useState<PortfolioPublic | null>(null)
  const [managePortfolio, setManagePortfolio] = useState<PortfolioPublic | null>(null)
  const [deleteCandidate, setDeleteCandidate] = useState<PortfolioPublic | null>(null)
  const [selectedProjectKeys, setSelectedProjectKeys] = useState<Set<string>>(new Set())
  const [formError, setFormError] = useState<string | null>(null)

  const portfoliosQuery = useQuery({
    queryKey: ['portfolios'],
    queryFn: fetchPortfolios,
  })
  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: fetchProjects,
  })
  const manageDetailQuery = useQuery({
    queryKey: ['portfolio-detail', managePortfolio?.key],
    queryFn: () => fetchPortfolioDetail(managePortfolio!.key),
    enabled: Boolean(managePortfolio),
  })

  const invalidatePortfolios = () => {
    queryClient.invalidateQueries({ queryKey: ['portfolios'] })
    queryClient.invalidateQueries({ queryKey: ['portfolio-detail'] })
  }

  const createMutation = useMutation({
    mutationFn: (payload: PortfolioCreate) => createPortfolio(payload),
    onSuccess: () => {
      invalidatePortfolios()
      closeForm()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ key, payload }: { key: string; payload: PortfolioUpdate }) =>
      updatePortfolio(key, payload),
    onSuccess: () => {
      invalidatePortfolios()
      closeForm()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (portfolioKey: string) => deletePortfolio(portfolioKey),
    onSuccess: () => {
      invalidatePortfolios()
      setDeleteCandidate(null)
    },
  })

  const addProjectsMutation = useMutation({
    mutationFn: ({ portfolioKey, projectKeys }: { portfolioKey: string; projectKeys: string[] }) =>
      addPortfolioProjects(portfolioKey, projectKeys),
  })

  const removeProjectsMutation = useMutation({
    mutationFn: ({ portfolioKey, projectKey }: { portfolioKey: string; projectKey: string }) =>
      removePortfolioProject(portfolioKey, projectKey),
  })

  const portfolios = portfoliosQuery.data ?? []
  const projects = projectsQuery.data ?? []
  const totalProjects = portfolios.reduce((sum, portfolio) => sum + (portfolio.project_count ?? 0), 0)
  const topLevel = portfolios.filter((portfolio) => !portfolio.parent_id)
  const blockedParentIds = collectBlockedParentIds(portfolios, editingPortfolio?.id ?? null)
  const selectableParents = portfolios.filter((portfolio) => !blockedParentIds.has(portfolio.id))

  const managedDetail = manageDetailQuery.data
  const managedProjectKeys = new Set<string>(
    (managedDetail?.projects ?? []).map((project) => project.project_key),
  )

  function closeForm() {
    setFormOpen(false)
    setFormMode('create')
    setEditingPortfolio(null)
    setFormState(EMPTY_FORM)
    setFormError(null)
  }

  function openCreateForm() {
    setFormMode('create')
    setEditingPortfolio(null)
    setFormState(EMPTY_FORM)
    setFormError(null)
    setFormOpen(true)
  }

  function openEditForm(portfolio: PortfolioPublic) {
    setFormMode('edit')
    setEditingPortfolio(portfolio)
    setFormState(formFromPortfolio(portfolio))
    setFormError(null)
    setFormOpen(true)
  }

  function openManage(portfolio: PortfolioPublic) {
    setManagePortfolio(portfolio)
    void fetchPortfolioDetail(portfolio.key).then((detail: PortfolioDetail) => {
      setSelectedProjectKeys(new Set((detail.projects ?? []).map((project) => project.project_key)))
    })
  }

  function submitForm() {
    setFormError(null)
    if (formState.parentId !== 'none') {
      const parentId = Number(formState.parentId)
      if (!Number.isInteger(parentId)) {
        setFormError('Selected parent portfolio is invalid.')
        return
      }
      if (blockedParentIds.has(parentId)) {
        setFormError('Selected parent would create a circular portfolio hierarchy.')
        return
      }
    }

    const shared = {
      name: formState.name.trim(),
      description: formState.description.trim() || undefined,
      parent_id: formState.parentId !== 'none' ? Number(formState.parentId) : null,
      selection_mode: formState.selectionMode,
      selection_value:
        formState.selectionMode === 'manual' || formState.selectionMode === 'all'
          ? undefined
          : formState.selectionValue.trim() || undefined,
      azure_devops_org: formState.azureDevOpsOrg.trim() || undefined,
    }

    if (formMode === 'edit' && editingPortfolio) {
      updateMutation.mutate({
        key: editingPortfolio.key,
        payload: shared,
      })
      return
    }

    createMutation.mutate({
      key: formState.key.trim(),
      ...shared,
    })
  }

  async function saveManagedProjects() {
    if (!managePortfolio) return
    try {
      const toAdd = Array.from(selectedProjectKeys).filter((key) => !managedProjectKeys.has(key))
      const toRemove = Array.from(managedProjectKeys).filter((key) => !selectedProjectKeys.has(key))

      if (toAdd.length > 0) {
        await addProjectsMutation.mutateAsync({
          portfolioKey: managePortfolio.key,
          projectKeys: toAdd,
        })
      }
      if (toRemove.length > 0) {
        await Promise.all(
          toRemove.map((projectKey) =>
            removeProjectsMutation.mutateAsync({
              portfolioKey: managePortfolio.key,
              projectKey,
            }),
          ),
        )
      }
      invalidatePortfolios()
      setManagePortfolio(null)
    } catch (err) {
      console.error('Failed to save managed projects:', err)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Portfolios</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Roll up project health for executive and organizational views.
          </p>
        </div>
        <Button color="primary" onClick={openCreateForm}>
          <Plus size={16} />
          New Portfolio
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <MetricCard
          detail="Defined portfolios"
          icon={<FolderTree size={16} />}
          label="Portfolios"
          value={String(portfolios.length)}
        />
        <MetricCard
          detail="Across all portfolios"
          icon={<Layers size={16} />}
          label="Projects"
          value={String(totalProjects)}
        />
      </div>

      {topLevel.length === 0 ? (
        <EmptyState
          body="Create a portfolio to aggregate project metrics for executive visibility."
          title="No portfolios defined"
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {topLevel.map((portfolio) => (
            <PortfolioCard
              key={portfolio.id}
              portfolio={portfolio}
              onDelete={setDeleteCandidate}
              onEdit={openEditForm}
              onManage={openManage}
            />
          ))}
        </div>
      )}

      <Dialog open={formOpen} onOpenChange={(open) => !open && closeForm()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{formMode === 'create' ? 'Create Portfolio' : 'Edit Portfolio'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {formMode === 'create' ? (
              <div className="space-y-2">
                <Label>Key</Label>
                <Input
                  placeholder="engineering"
                  value={formState.key}
                  onChange={(event) => setFormState((current) => ({ ...current, key: event.target.value }))}
                />
              </div>
            ) : (
              <div className="space-y-2">
                <Label>Key</Label>
                <Input disabled value={formState.key} />
              </div>
            )}
            <div className="space-y-2">
              <Label>Name</Label>
              <Input
                placeholder="Engineering"
                value={formState.name}
                onChange={(event) => setFormState((current) => ({ ...current, name: event.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Input
                placeholder="Optional description"
                value={formState.description}
                onChange={(event) =>
                  setFormState((current) => ({ ...current, description: event.target.value }))
                }
              />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Parent portfolio</Label>
                <Select
                  value={formState.parentId}
                  onValueChange={(value) => setFormState((current) => ({ ...current, parentId: value }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">No parent</SelectItem>
                    {selectableParents.map((portfolio) => (
                      <SelectItem key={portfolio.id} value={String(portfolio.id)}>
                        {portfolio.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Selection mode</Label>
                <Select
                  value={formState.selectionMode}
                  onValueChange={(value) =>
                    setFormState((current) => ({
                      ...current,
                      selectionMode: value as PortfolioFormState['selectionMode'],
                    }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="manual">Manual</SelectItem>
                    <SelectItem value="tags">By tags</SelectItem>
                    <SelectItem value="regex">By regex</SelectItem>
                    <SelectItem value="all">All projects</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            {formState.selectionMode !== 'manual' && formState.selectionMode !== 'all' ? (
              <div className="space-y-2">
                <Label>{formState.selectionMode === 'tags' ? 'Tags (comma separated)' : 'Regex pattern'}</Label>
                <Input
                  placeholder={formState.selectionMode === 'tags' ? 'backend, platform' : '^platform-.*'}
                  value={formState.selectionValue}
                  onChange={(event) =>
                    setFormState((current) => ({ ...current, selectionValue: event.target.value }))
                  }
                />
              </div>
            ) : null}
            <div className="space-y-2">
              <Label>Azure DevOps Organization</Label>
              <Input
                placeholder="my-org"
                value={formState.azureDevOpsOrg}
                onChange={(event) =>
                  setFormState((current) => ({ ...current, azureDevOpsOrg: event.target.value }))
                }
              />
            </div>
            {formError ? <p className="text-sm text-danger">{formError}</p> : null}
            {createMutation.isError || updateMutation.isError ? (
              <p className="text-sm text-danger">
                {createMutation.error instanceof Error
                  ? createMutation.error.message
                  : updateMutation.error instanceof Error
                    ? updateMutation.error.message
                    : 'Saving the portfolio failed.'}
              </p>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="flat" onClick={closeForm}>
              Cancel
            </Button>
            <Button
              color="primary"
              isLoading={createMutation.isPending || updateMutation.isPending}
              onClick={submitForm}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={managePortfolio !== null} onOpenChange={(open) => !open && setManagePortfolio(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Manage Portfolio Membership</DialogTitle>
          </DialogHeader>
          {managePortfolio ? (
            managePortfolio.selection_mode !== 'manual' ? (
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">
                  <span className="font-semibold">{managePortfolio.name}</span> is currently driven by the{' '}
                  <span className="font-semibold">{managePortfolio.selection_mode}</span> selection mode.
                </p>
                <p className="text-xs text-muted-foreground">
                  Update the portfolio rules if you want to change membership for this portfolio.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="space-y-1">
                  <p className="text-sm font-medium">{managePortfolio.name}</p>
                  <p className="text-xs text-muted-foreground">
                    Select which projects belong to this manual portfolio.
                  </p>
                </div>
                <div className="max-h-[320px] space-y-2 overflow-y-auto">
                  {projects.map((project: ProjectPublic) => {
                    const checked = selectedProjectKeys.has(project.key)
                    return (
                      <label
                        className="flex items-start gap-3 rounded-sm border border-border bg-muted/40 px-3 py-3"
                        key={project.id}
                      >
                        <Checkbox
                          checked={checked}
                          onCheckedChange={(next) => {
                            setSelectedProjectKeys((current) => {
                              const updated = new Set(current)
                              if (next === true) {
                                updated.add(project.key)
                              } else {
                                updated.delete(project.key)
                              }
                              return updated
                            })
                          }}
                        />
                        <span className="min-w-0 flex-1">
                          <span className="block text-sm font-medium">{project.name}</span>
                          <span className="block font-mono text-xs text-muted-foreground">
                            {project.key}
                          </span>
                        </span>
                      </label>
                    )
                  })}
                </div>
                {addProjectsMutation.isError || removeProjectsMutation.isError ? (
                  <p className="text-sm text-danger">
                    {addProjectsMutation.error instanceof Error
                      ? addProjectsMutation.error.message
                      : removeProjectsMutation.error instanceof Error
                        ? removeProjectsMutation.error.message
                        : 'Updating portfolio membership failed.'}
                  </p>
                ) : null}
              </div>
            )
          ) : null}
          <DialogFooter>
            <Button variant="flat" onClick={() => setManagePortfolio(null)}>
              Close
            </Button>
            {managePortfolio?.selection_mode === 'manual' ? (
              <Button
                color="primary"
                isLoading={addProjectsMutation.isPending || removeProjectsMutation.isPending}
                onClick={() => void saveManagedProjects()}
              >
                Save membership
              </Button>
            ) : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteCandidate !== null} onOpenChange={(open) => !open && setDeleteCandidate(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Portfolio</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              Delete <span className="font-semibold">{deleteCandidate?.name}</span> and remove its manual membership links?
            </p>
            {deleteMutation.isError ? (
              <p className="text-sm text-danger">
                {deleteMutation.error instanceof Error
                  ? deleteMutation.error.message
                  : 'Deleting the portfolio failed.'}
              </p>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="flat" onClick={() => setDeleteCandidate(null)}>
              Cancel
            </Button>
            <Button
              color="danger"
              isLoading={deleteMutation.isPending}
              onClick={() => {
                if (deleteCandidate) {
                  deleteMutation.mutate(deleteCandidate.key)
                }
              }}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
