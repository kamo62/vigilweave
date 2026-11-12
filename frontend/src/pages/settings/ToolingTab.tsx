import { useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, RotateCcw, Settings2, Trash2, Wrench } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Textarea } from '@/components/ui/textarea'
import {
  createTenantToolConfig,
  deleteTenantToolConfig,
  fetchTenantToolOverrides,
  fetchToolConfigSnapshot,
  patchToolConfig,
  type ToolConfigCreate,
  type ToolConfigItem,
} from '@/lib/api'

type ToolFormState = {
  toolId: string
  enabled: boolean
  category: string
  languages: string
  runner: string
  rules: string
  baseDefined: boolean
}

type SaveToolPayload = ToolFormState & {
  parsedRules?: Record<string, unknown>
}

const TOOL_DISPLAY_NAMES: Record<string, string> = {
  gitleaks: 'Secret Scanner',
  semgrep: 'Application Security Analyzer',
  bandit: 'Python Security Analyzer',
  ruff: 'Python Linter',
  eslint: 'JavaScript / TypeScript Linter',
  checkov: 'Infrastructure Policy Analyzer',
  tflint: 'Terraform Linter',
  'cfn-lint': 'CloudFormation Linter',
  trivy: 'Container & Dependency Analyzer',
  sqlfluff: 'SQL Linter',
  swiftlint: 'Swift Linter',
  detekt: 'Kotlin Linter',
  'android-lint': 'Android Linter',
  'dotnet-analyzers': '.NET Analyzer',
  grype: 'Dependency Analyzer',
}

const CATEGORY_DISPLAY_NAMES: Record<string, string> = {
  secrets: 'Secrets',
  security: 'Security',
  quality: 'Code Quality',
  iac: 'Infrastructure as Code',
  container: 'Container Security',
  sca: 'Dependency Risk',
}

function displayToolName(toolId: string): string {
  return TOOL_DISPLAY_NAMES[toolId] ?? toolId.replace(/[-_]/g, ' ')
}

function displayCategory(category: string): string {
  return CATEGORY_DISPLAY_NAMES[category] ?? category
}

const EMPTY_FORM: ToolFormState = {
  toolId: '',
  enabled: true,
  category: '',
  languages: '',
  runner: '',
  rules: '{}',
  baseDefined: false,
}

function formFromTool(tool: ToolConfigItem): ToolFormState {
  const raw = tool.raw ?? {}
  return {
    toolId: tool.tool,
    enabled: tool.enabled,
    category: tool.category,
    languages: tool.languages.join(', '),
    runner: String(raw.runner ?? ''),
    rules: JSON.stringify(raw.rules ?? {}, null, 2),
    baseDefined: tool.base_defined,
  }
}

export function ToolingTab() {
  const queryClient = useQueryClient()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [formState, setFormState] = useState<ToolFormState>(EMPTY_FORM)
  const [editingTool, setEditingTool] = useState<ToolConfigItem | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ToolConfigItem | null>(null)
  const [rulesError, setRulesError] = useState<string | null>(null)

  const snapshotQuery = useQuery({
    queryKey: ['tool-configs'],
    queryFn: fetchToolConfigSnapshot,
  })
  const overridesQuery = useQuery({
    queryKey: ['tool-config-overrides'],
    queryFn: fetchTenantToolOverrides,
  })

  const invalidateTooling = () => {
    queryClient.invalidateQueries({ queryKey: ['tool-configs'] })
    queryClient.invalidateQueries({ queryKey: ['tool-config-overrides'] })
  }

  const saveMutation = useMutation({
    mutationFn: async (payload: SaveToolPayload) => {
      const languages = payload.languages
        .split(',')
        .map((language) => language.trim())
        .filter(Boolean)

      if (payload.baseDefined) {
        return patchToolConfig(payload.toolId, {
          enabled: payload.enabled,
          category: payload.category,
          languages,
          runner: payload.runner.trim() || undefined,
          rules: payload.parsedRules,
        })
      }

      const body: ToolConfigCreate = {
        enabled: payload.enabled,
        category: payload.category,
        languages,
        runner: payload.runner.trim() || undefined,
        rules: payload.parsedRules,
      }
      return createTenantToolConfig(payload.toolId, body)
    },
    onSuccess: () => {
      invalidateTooling()
      closeDialog()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (toolId: string) => deleteTenantToolConfig(toolId),
    onSuccess: () => {
      invalidateTooling()
      setDeleteTarget(null)
    },
  })

  const snapshot = snapshotQuery.data
  const tools = snapshot?.tools ?? []
  const scanTypes = snapshot?.scan_types ?? []
  const overrides = overridesQuery.data ?? []

  if (snapshotQuery.isLoading && !snapshot) {
    return <div className="py-12 text-center text-sm text-muted-foreground">Loading tooling configuration...</div>
  }

  if (snapshotQuery.isError) {
    return (
      <EmptyState
        title="Tooling unavailable"
        body="Analyzer configuration could not be loaded. Refresh the page and verify the API is reachable."
      />
    )
  }

  function closeDialog() {
    setDialogOpen(false)
    setEditingTool(null)
    setFormState(EMPTY_FORM)
    setRulesError(null)
    saveMutation.reset()
  }

  function openCreateDialog() {
    setEditingTool(null)
    setFormState(EMPTY_FORM)
    setRulesError(null)
    saveMutation.reset()
    setDialogOpen(true)
  }

  function openEditDialog(tool: ToolConfigItem) {
    setEditingTool(tool)
    setFormState(formFromTool(tool))
    setRulesError(null)
    saveMutation.reset()
    setDialogOpen(true)
  }

  function submitDialog() {
    setRulesError(null)
    let parsedRules: Record<string, unknown> | undefined
    const rawRules = formState.rules.trim()

    if (rawRules) {
      try {
        const parsed = JSON.parse(rawRules)
        if (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object') {
          setRulesError('Rules JSON must be an object.')
          return
        }
        parsedRules = parsed as Record<string, unknown>
      } catch {
        setRulesError('Rules JSON must be valid JSON.')
        return
      }
    }

    saveMutation.reset()
    saveMutation.mutate({
      ...formState,
      parsedRules,
    })
  }

  return (
    <div className="space-y-6">
      {overridesQuery.isError ? (
        <div className="rounded-sm border border-warning/30 bg-warning/5 px-4 py-3 text-sm text-warning">
          Tenant-specific analyzer overrides could not be loaded. Base tooling configuration is still shown.
        </div>
      ) : null}

      <Card>
        <CardHeader className="flex items-center justify-between px-6 pt-5">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
              Tooling
            </p>
            <h2 className="text-lg font-semibold">Configured analyzers</h2>
          </div>
          <Button color="primary" size="sm" onClick={openCreateDialog}>
            <Plus size={14} />
            Add custom analyzer
          </Button>
        </CardHeader>
        <Separator />
        <CardContent className="space-y-3 p-6">
          {tools.length === 0 ? (
            <EmptyState body="No analyzers are currently configured." title="No analyzer config" />
          ) : (
            tools.map((tool) => {
              const raw = tool.raw ?? {}
              const overrideRecord = overrides.find((item) => item.tool === tool.tool)
              return (
                <Card className="bg-muted/50" key={tool.tool}>
                  <CardContent className="space-y-3 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-semibold">{displayToolName(tool.tool)}</p>
                          <Badge variant="flat">{displayCategory(tool.category)}</Badge>
                          <Badge variant="flat">{tool.base_defined ? 'built-in' : 'custom'}</Badge>
                          {tool.overridden ? (
                            <Badge color="primary" variant="dot">
                              Override
                            </Badge>
                          ) : null}
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge color={tool.runtime_available ? 'success' : 'warning'} variant="flat">
                            {tool.runtime_available
                              ? 'Ready'
                              : tool.tool === 'android-lint' || tool.tool === 'dotnet-analyzers'
                                ? 'Repo-dependent'
                                : 'Unavailable'}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            Languages: {tool.languages.join(', ')}
                          </span>
                        </div>
                        {tool.tool === 'android-lint' || tool.tool === 'dotnet-analyzers' ? (
                          <p className="text-xs text-muted-foreground">
                            Requires repository build files at scan time. Managed infrastructure handles the analyzer runtime.
                          </p>
                        ) : null}
                        {overrideRecord ? (
                          <p className="text-xs text-muted-foreground">
                            Override updated {new Date(overrideRecord.updated_at).toLocaleString()}
                          </p>
                        ) : null}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" variant="flat" onClick={() => openEditDialog(tool)}>
                          <Wrench size={14} />
                          Edit override
                        </Button>
                        {tool.overridden ? (
                          <Button
                            color="danger"
                            size="sm"
                            variant="flat"
                            onClick={() => setDeleteTarget(tool)}
                          >
                            {tool.base_defined ? (
                              <>
                                <RotateCcw size={14} />
                                Reset override
                              </>
                            ) : (
                              <>
                                <Trash2 size={14} />
                                Delete analyzer
                              </>
                            )}
                          </Button>
                        ) : null}
                      </div>
                    </div>

                    {raw.rules ? (
                      <details className="rounded-sm border border-border bg-card px-3 py-2">
                        <summary className="cursor-pointer text-xs font-medium">Analyzer rules override</summary>
                        <pre className="mt-2 overflow-x-auto text-[11px] text-muted-foreground">
                          {JSON.stringify(raw.rules, null, 2)}
                        </pre>
                      </details>
                    ) : null}
                  </CardContent>
                </Card>
              )
            })
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="px-6 pt-5">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
              Scan Policy
            </p>
            <h2 className="text-lg font-semibold">Scan type routing</h2>
          </div>
        </CardHeader>
        <Separator />
        <CardContent className="space-y-3 p-6">
          {scanTypes.length === 0 ? (
            <EmptyState body="No scan types are configured." title="No scan types" />
          ) : (
            scanTypes.map((scanType) => (
                <Card className="bg-muted/50" key={scanType.name}>
                  <CardContent className="gap-2 p-4">
                    <div className="flex items-center gap-2">
                      <Wrench size={14} />
                    <p className="font-medium">{scanType.name}</p>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Categories: {(scanType.categories ?? []).map(displayCategory).join(', ') || 'none'}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {(scanType.tools ?? []).length > 0
                      ? `Managed analyzers: ${(scanType.tools ?? []).length}`
                      : 'Managed analyzers are selected automatically by category.'}
                  </p>
                </CardContent>
              </Card>
            ))
          )}
          <Button color="primary" disabled size="sm" variant="flat">
            <Settings2 size={14} />
            Scan type editing remains read-only in this increment
          </Button>
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={(open) => !open && closeDialog()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingTool ? `Edit ${displayToolName(editingTool.tool)}` : 'Add custom analyzer'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {editingTool === null || !editingTool.base_defined ? (
              <div className="space-y-2">
                <Label>Analyzer ID</Label>
                <Input
                  disabled={editingTool !== null}
                  value={formState.toolId}
                  onChange={(event) =>
                    setFormState((current) => ({ ...current, toolId: event.target.value }))
                  }
                />
              </div>
            ) : null}
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
              <Label>Category</Label>
                <Input
                  value={formState.category}
                  onChange={(event) =>
                    setFormState((current) => ({ ...current, category: event.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
              <Label>Execution profile</Label>
              <Input
                placeholder="managed-analyzer"
                value={formState.runner}
                onChange={(event) =>
                  setFormState((current) => ({ ...current, runner: event.target.value }))
                }
              />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Languages</Label>
              <Input
                placeholder="python, typescript"
                value={formState.languages}
                onChange={(event) =>
                  setFormState((current) => ({ ...current, languages: event.target.value }))
                }
              />
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                checked={formState.enabled}
                id="tool-enabled"
                onCheckedChange={(checked) =>
                  setFormState((current) => ({ ...current, enabled: checked === true }))
                }
              />
              <Label htmlFor="tool-enabled">Analyzer enabled</Label>
            </div>
            <div className="space-y-2">
              <Label>Rules JSON</Label>
              <Textarea
                rows={8}
                className="font-mono text-xs"
                value={formState.rules}
                onChange={(event) =>
                  setFormState((current) => ({ ...current, rules: event.target.value }))
                }
              />
            </div>
            {rulesError ? <p className="text-sm text-danger">{rulesError}</p> : null}
            {saveMutation.isError ? (
              <p className="text-sm text-danger">
                {saveMutation.error instanceof Error
                  ? saveMutation.error.message
                  : 'Saving the analyzer override failed. Check the analyzer id, languages, and rules JSON.'}
              </p>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="flat" onClick={closeDialog}>
              Cancel
            </Button>
            <Button color="primary" isLoading={saveMutation.isPending} onClick={submitDialog}>
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteTarget !== null} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{deleteTarget?.base_defined ? 'Reset analyzer override' : 'Delete custom analyzer'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              {deleteTarget?.base_defined
                ? `Remove the tenant override for ${displayToolName(deleteTarget?.tool ?? '')} and fall back to the base config?`
                : `Delete the tenant-defined analyzer ${displayToolName(deleteTarget?.tool ?? '')}?`}
            </p>
            {deleteMutation.isError ? (
              <p className="text-sm text-danger">
                {deleteMutation.error instanceof Error
                  ? deleteMutation.error.message
                  : 'Updating the analyzer configuration failed.'}
              </p>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="flat" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              color="danger"
              isLoading={deleteMutation.isPending}
              onClick={() => {
                if (deleteTarget) {
                  deleteMutation.mutate(deleteTarget.tool)
                }
              }}
            >
              {deleteTarget?.base_defined ? 'Reset override' : 'Delete analyzer'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
