import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, GitBranch, Loader2, Plus, PlugZap, Trash2, XCircle } from 'lucide-react'
import { useState } from 'react'

import { EmptyState } from '@/components/EmptyState'
import { SCMConnectionForm } from '@/components/SCMConnectionForm'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
  createSCMConnection,
  deleteSCMConnection,
  fetchSCMConnections,
  testSCMConnection,
  type SCMConnectionPublic,
  type SCMProvider,
} from '@/lib/api'

const PROVIDER_LABELS: Record<SCMProvider, string> = {
  github: 'GitHub',
  gitlab: 'GitLab',
  bitbucket: 'Bitbucket',
  azure_devops: 'Azure DevOps',
}

export function ConnectionsTab() {
  const queryClient = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<SCMConnectionPublic | null>(null)
  const [testingId, setTestingId] = useState<number | null>(null)
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null)

  const connectionsQuery = useQuery({
    queryKey: ['scm-connections'],
    queryFn: fetchSCMConnections,
  })

  const createMutation = useMutation({
    mutationFn: createSCMConnection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scm-connections'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteSCMConnection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scm-connections'] })
      setDeleteTarget(null)
    },
  })

  const testMutation = useMutation({
    mutationFn: testSCMConnection,
    onSuccess: (result) => {
      setTestResult(result)
      queryClient.invalidateQueries({ queryKey: ['scm-connections'] })
    },
    onSettled: () => setTestingId(null),
  })

  function handleTest(id: number) {
    setTestingId(id)
    setTestResult(null)
    testMutation.mutate(id)
  }

  const connections = connectionsQuery.data ?? []

  if (connectionsQuery.isLoading && !connectionsQuery.data) {
    return <div className="py-12 text-center text-sm text-muted-foreground">Loading connections...</div>
  }

  if (connectionsQuery.isError) {
    return (
      <EmptyState
        title="Connections unavailable"
        body="SCM connections could not be loaded. Refresh the page and verify the API is reachable."
      />
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold tracking-tight">SCM Connections</h2>
          <p className="text-sm text-muted-foreground">
            Connect your source code management accounts to import and scan private repositories.
          </p>
        </div>
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Connection
        </Button>
      </div>

      {connections.length === 0 ? (
        <EmptyState
          title="No connections yet"
          body="Add a connection to your GitHub, GitLab, Bitbucket, or Azure DevOps account to import repositories."
        />
      ) : (
        <div className="space-y-3">
          {connections.map((conn) => (
            <ConnectionRow
              key={conn.id}
              conn={conn}
              testing={testingId === conn.id}
              onTest={() => handleTest(conn.id)}
              onDelete={() => setDeleteTarget(conn)}
            />
          ))}
        </div>
      )}

      {testResult && (
        <Card>
          <CardContent className="flex items-center gap-3 py-3">
            {testResult.ok ? (
              <CheckCircle2 className="h-5 w-5 text-success shrink-0" />
            ) : (
              <XCircle className="h-5 w-5 text-destructive shrink-0" />
            )}
            <span className="text-sm">{testResult.message}</span>
          </CardContent>
        </Card>
      )}

      {testMutation.isError ? (
        <div className="rounded-sm border border-danger/30 bg-danger/[0.06] px-4 py-3 text-sm text-danger">
          {testMutation.error instanceof Error ? testMutation.error.message : 'Testing the connection failed.'}
        </div>
      ) : null}

      {deleteMutation.isError ? (
        <div className="rounded-sm border border-danger/30 bg-danger/[0.06] px-4 py-3 text-sm text-danger">
          {deleteMutation.error instanceof Error ? deleteMutation.error.message : 'Deleting the connection failed.'}
        </div>
      ) : null}

      <Dialog open={deleteTarget !== null} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete SCM Connection</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Delete <span className="font-semibold text-foreground">{deleteTarget?.name}</span>?
            </p>
            <p className="text-xs text-muted-foreground">
              Connections that are still linked to project repositories must be reassigned before they can be deleted.
            </p>
          </div>
          <DialogFooter>
            <Button variant="flat" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              color="danger"
              isLoading={deleteMutation.isPending}
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
            >
              Delete connection
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add SCM Connection</DialogTitle>
          </DialogHeader>
          <SCMConnectionForm
            key={createOpen ? 'connections-open' : 'connections-closed'}
            onSubmit={async (payload) => {
              await createMutation.mutateAsync(payload)
            }}
            onSuccess={() => setCreateOpen(false)}
            onCancel={() => setCreateOpen(false)}
            submitLabel="Create"
          />
        </DialogContent>
      </Dialog>
    </div>
  )
}

function ConnectionRow({
  conn,
  testing,
  onTest,
  onDelete,
}: {
  conn: SCMConnectionPublic
  testing: boolean
  onTest: () => void
  onDelete: () => void
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 py-3">
        <GitBranch className="h-5 w-5 text-muted-foreground shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm truncate">{conn.name}</span>
            <Badge variant="bordered" className="text-[10px] font-bold uppercase tracking-widest">
              {PROVIDER_LABELS[conn.provider]}
            </Badge>
            {conn.last_test_ok === true && (
              <CheckCircle2 className="h-3.5 w-3.5 text-success" />
            )}
            {conn.last_test_ok === false && (
              <XCircle className="h-3.5 w-3.5 text-destructive" />
            )}
            {!conn.is_active && (
              <Badge variant="bordered" className="text-[10px] text-muted-foreground">
                Inactive
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-3 text-[11px] text-muted-foreground mt-0.5">
            <span className="truncate">{conn.base_url}</span>
            <span>·</span>
            <span>{conn.token_masked}</span>
            {conn.last_tested_at && (
              <>
                <span>·</span>
                <span>Tested {new Date(conn.last_tested_at).toLocaleDateString()}</span>
              </>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <Button variant="outline" size="sm" onClick={onTest} disabled={testing}>
            {testing ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <PlugZap className="h-3.5 w-3.5" />
            )}
            <span className="ml-1.5">Test</span>
          </Button>
          <Button variant="outline" size="sm" onClick={onDelete}>
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
