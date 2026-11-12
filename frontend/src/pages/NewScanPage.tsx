import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate, useSearch } from '@tanstack/react-router'
import { Rocket } from 'lucide-react'
import { useEffect, useMemo } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { createScan, fetchProjects } from '@/lib/api'

const scanSchema = z
  .object({
    repo: z.string().trim().min(1, 'Repository is required'),
    project_key: z.string().trim().optional(),
    branch: z.string().trim().optional(),
    commit: z.string().trim().optional(),
    scan_type: z.enum(['comprehensive', 'fast', 'security-only', 'custom']),
    include_quality_metrics: z.boolean(),
    tools: z.string().trim().optional(),
  })
  .superRefine((value, context) => {
    if (value.scan_type === 'custom' && !value.tools) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Custom scans require at least one analyzer name.',
        path: ['tools'],
      })
    }
  })

type ScanFormValues = z.infer<typeof scanSchema>

export function NewScanPage() {
  const navigate = useNavigate()
  const { repo: repoFromUrl, projectKey } = useSearch({ from: '/scans/new' })
  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: fetchProjects,
  })
  const form = useForm<ScanFormValues>({
    resolver: zodResolver(scanSchema),
    defaultValues: {
      repo: repoFromUrl || '',
      project_key: projectKey || '',
      branch: '',
      commit: '',
      scan_type: 'comprehensive',
      include_quality_metrics: true,
      tools: '',
    },
  })
  const scanType = useWatch({ control: form.control, name: 'scan_type' })
  const includeQualityMetrics = useWatch({ control: form.control, name: 'include_quality_metrics' })
  const selectedProjectKey = useWatch({ control: form.control, name: 'project_key' })
  const selectedRepo = useWatch({ control: form.control, name: 'repo' })
  const projects = useMemo(() => projectsQuery.data ?? [], [projectsQuery.data])
  const assignableProjects = useMemo(
    () => projects.filter((project) => project.key.trim().length > 0),
    [projects],
  )
  const selectedProject = projects.find((project) => project.key === selectedProjectKey)
  const projectHint = useMemo(() => {
    if (!projectKey || projects.length === 0) {
      return null
    }

    const matchedProject = projects.find((project) => project.key === projectKey)
    if (!matchedProject) {
      return `Project "${projectKey}" was not found, so this scan will run unassigned.`
    }
    const projectRepos = matchedProject.repos ?? []
    if (repoFromUrl && !projectRepos.includes(repoFromUrl)) {
      return `Repository is not linked to project "${matchedProject.name}" yet, so this scan will run unassigned until the repo is added to that project.`
    }
    return null
  }, [projectKey, projects, repoFromUrl])

  useEffect(() => {
    if (!projectKey || projects.length === 0) {
      return
    }
    const matchedProject = projects.find((project) => project.key === projectKey)
    if (!matchedProject) {
      form.setValue('project_key', '')
      return
    }
    const projectRepos = matchedProject.repos ?? []
    if (repoFromUrl && !projectRepos.includes(repoFromUrl)) {
      form.setValue('project_key', '')
      return
    }
  }, [form, projectKey, projects, repoFromUrl])

  useEffect(() => {
    if (!selectedProjectKey) {
      form.clearErrors('project_key')
      return
    }

    const matchedProject = projects.find((project) => project.key === selectedProjectKey)
    if (!matchedProject) {
      form.setError('project_key', {
        type: 'manual',
        message: 'Selected project was not found.',
      })
      return
    }

    const projectRepos = matchedProject.repos ?? []
    if (selectedRepo && !projectRepos.includes(selectedRepo)) {
      form.setError('project_key', {
        type: 'manual',
        message:
          'Repository is not linked to the selected project. Add the repository to that project first, or run the scan unassigned.',
      })
      return
    }

    form.clearErrors('project_key')
  }, [form, projects, selectedProjectKey, selectedRepo])

  const mutation = useMutation({
    mutationFn: createScan,
    onSuccess: (scan) => {
      void navigate({ to: '/scans/$scanId', params: { scanId: String(scan.id) } })
    },
  })

  function handleSubmit(values: ScanFormValues) {
    const selected = projects.find((project) => project.key === values.project_key)
    const projectRepos = selected?.repos ?? []
    if (selected && !projectRepos.includes(values.repo)) {
      form.setError('project_key', {
        type: 'manual',
        message: 'Repository is not linked to the selected project. Add the repository to that project first, or run the scan unassigned.',
      })
      return
    }
    form.clearErrors('project_key')
    mutation.mutate({
      repo: values.repo,
      project_key: values.project_key || undefined,
      branch: values.branch || undefined,
      commit: values.commit || undefined,
      scan_type: values.scan_type,
      include_quality_metrics: values.include_quality_metrics,
      tools:
        values.scan_type === 'custom'
          ? (values.tools ?? '').split(',').map((t) => t.trim()).filter(Boolean)
          : undefined,
    })
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">Analysis</p>
        <h1 className="text-2xl font-bold tracking-tight">New Scan</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Submit a repository for security and quality analysis.
        </p>
      </div>

      <Card className="max-w-2xl">
        <CardHeader className="px-6 pt-5">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
              Configuration
            </p>
            <h2 className="text-lg font-semibold">Scan parameters</h2>
          </div>
        </CardHeader>
        <Separator />
        <CardContent className="p-6">
          <form className="space-y-5" onSubmit={form.handleSubmit(handleSubmit)}>
            <div className="space-y-2">
              <Label>Repository *</Label>
              <Input
                {...form.register('repo')}
                placeholder="file:///path/to/repo or https://..."
              />
              <p className="text-xs text-muted-foreground">Local file path or cloneable remote URL</p>
              {form.formState.errors.repo ? (
                <p className="text-xs text-danger">{form.formState.errors.repo.message}</p>
              ) : null}
            </div>

            <div className="space-y-2">
              <Label>Project</Label>
              <Select
                value={selectedProjectKey || '__unassigned__'}
                onValueChange={(value) =>
                  form.setValue('project_key', value === '__unassigned__' ? '' : value)
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Unassigned" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__unassigned__">Unassigned</SelectItem>
                  {assignableProjects.map((project) => (
                    <SelectItem key={project.key} value={project.key}>
                      {project.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Assigned scans contribute to project rollups and use linked SCM credentials.
              </p>
              {projectHint ? (
                <p className="text-xs text-amber-700">{projectHint}</p>
              ) : null}
              {selectedProject && selectedRepo && !(selectedProject.repos ?? []).includes(selectedRepo) ? (
                <p className="text-xs text-amber-700">
                  The current repository is not linked to {selectedProject.name}. Launching with that project selected will fail until the repository is added to the project.
                </p>
              ) : null}
              {form.formState.errors.project_key ? (
                <p className="text-xs text-danger">{form.formState.errors.project_key.message}</p>
              ) : null}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Branch</Label>
                <Input {...form.register('branch')} placeholder="main" />
              </div>
              <div className="space-y-2">
                <Label>Commit</Label>
                <Input {...form.register('commit')} placeholder="Optional SHA" />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Scan type</Label>
              <Select
                defaultValue="comprehensive"
                onValueChange={(val) => form.setValue('scan_type', val as ScanFormValues['scan_type'])}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="comprehensive">Comprehensive</SelectItem>
                  <SelectItem value="fast">Fast</SelectItem>
                  <SelectItem value="security-only">Security Only</SelectItem>
                  <SelectItem value="custom">Custom</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {scanType === 'custom' ? (
              <div className="space-y-2">
                <Label>Analyzers</Label>
                <Input
                  {...form.register('tools')}
                  placeholder="sast, secrets, sca, iac"
                />
                <p className="text-xs text-muted-foreground">
                  Comma-separated analyzer categories or IDs, e.g. sast, secrets, sca, iac (see Settings → Tooling)
                </p>
                {form.formState.errors.tools ? (
                  <p className="text-xs text-danger">{form.formState.errors.tools.message}</p>
                ) : null}
              </div>
            ) : null}

            <div className="flex items-center gap-2">
              <Checkbox
                checked={includeQualityMetrics}
                onCheckedChange={(v) => form.setValue('include_quality_metrics', v === true)}
                id="include-quality"
              />
              <Label htmlFor="include-quality">
                Include quality metrics and file-level analysis
              </Label>
            </div>

            {mutation.error ? (
              <p className="text-sm text-danger">
                {mutation.error instanceof Error
                  ? mutation.error.message
                  : 'Failed to create scan. Check the backend and repository path.'}
              </p>
            ) : null}

            <Button
              className="w-full"
              color="primary"
              isLoading={mutation.isPending}
              type="submit"
            >
              <Rocket size={16} />
              {mutation.isPending ? 'Launching...' : 'Launch Scan'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
