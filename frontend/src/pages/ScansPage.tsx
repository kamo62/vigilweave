import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { ArrowRight, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { EmptyState } from '@/components/EmptyState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Separator } from '@/components/ui/separator'
import { Spinner } from '@/components/ui/spinner'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { deleteScan, fetchScans } from '@/lib/api'
import { useAuth } from '@/lib/useAuth'
import { qualityTone } from '@/lib/utils'

const statusColor: Record<string, 'success' | 'warning' | 'danger' | 'primary' | 'default'> = {
  completed: 'success',
  running: 'primary',
  pending: 'warning',
  failed: 'danger',
}

export function ScansPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; repo: string } | null>(null)
  const isTenantAdmin = user?.role === 'admin'

  const scansQuery = useQuery({
    queryKey: ['scans'],
    queryFn: fetchScans,
  })

  const deleteMutation = useMutation({
    mutationFn: (scanId: number) => deleteScan(scanId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scans'] })
      setDeleteTarget(null)
    },
  })

  const scans = scansQuery.data ?? []

  if (scansQuery.isLoading && !scansQuery.data) {
    return (
      <div className="flex justify-center py-20">
        <Spinner label="Loading scans..." />
      </div>
    )
  }

  if (scansQuery.isError) {
    return (
      <EmptyState
        title="Scans unavailable"
        body="The scan list could not be loaded. Refresh the page and verify the API is reachable."
      />
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
            Analysis
          </p>
          <h1 className="text-2xl font-bold tracking-tight">Scans</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            All persisted scans with execution results.
          </p>
        </div>
        <Button asChild color="primary">
          <Link to="/scans/new" search={{ repo: '', projectKey: '' }}>
            <Plus size={16} />
            New Scan
          </Link>
        </Button>
      </div>

      {scans.length === 0 ? (
        <EmptyState
          body="Create the first scan to populate this list. Data appears once the backend stores results."
          title="No scans recorded"
        />
      ) : (
        <Card>
          <CardHeader className="px-6 pt-5">
            <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
              {scans.length} scan{scans.length !== 1 ? 's' : ''} recorded
            </p>
          </CardHeader>
          <Separator />
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Repository</TableHead>
                  <TableHead>Project</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Findings</TableHead>
                  <TableHead>Quality</TableHead>
                  <TableHead className="w-[100px]">{''}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {scans.map((scan) => (
                  <TableRow key={scan.id}>
                    <TableCell>
                      <span className="text-sm font-medium">{scan.repo}</span>
                    </TableCell>
                    <TableCell>
                      <Badge color={scan.project_key ? 'primary' : 'default'} variant="flat">
                        {scan.project_key ?? 'Unassigned'}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge color={statusColor[scan.status] ?? 'default'} variant="flat">
                        {scan.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm text-muted-foreground">{scan.scan_type}</span>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm font-semibold">{scan.total_findings}</span>
                    </TableCell>
                    <TableCell>
                      <span
                        className={`text-sm font-semibold ${
                          qualityTone(scan.quality_score) === 'success'
                            ? 'text-success'
                            : qualityTone(scan.quality_score) === 'danger'
                              ? 'text-danger'
                              : ''
                        }`}
                      >
                        {scan.quality_score?.toFixed(1) ?? 'N/A'}
                      </span>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        {isTenantAdmin ? (
                          <Button
                            isIconOnly
                            size="sm"
                            variant="light"
                            className="text-danger/60 hover:text-danger hover:bg-danger/10"
                            onClick={() => setDeleteTarget({ id: scan.id, repo: scan.repo })}
                          >
                            <Trash2 size={14} />
                          </Button>
                        ) : null}
                        <Button asChild isIconOnly size="sm" variant="light">
                          <Link to="/scans/$scanId" params={{ scanId: String(scan.id) }}>
                            <ArrowRight size={14} />
                          </Link>
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <Dialog open={isTenantAdmin && deleteTarget !== null} onOpenChange={() => setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Scan #{deleteTarget?.id}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            This will permanently delete the scan for{' '}
            <span className="font-medium text-foreground">{deleteTarget?.repo}</span> and all its
            findings. This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="flat" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              color="danger"
              isLoading={deleteMutation.isPending}
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
            >
              Delete Scan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
