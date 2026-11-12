import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Shield, ShieldCheck, Trash2, UserCircle } from 'lucide-react'
import { useState } from 'react'

import { EmptyState } from '@/components/EmptyState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { buildApiUrl } from '@/lib/api-url'
import { getAuthHeaders, getCsrfToken } from '@/lib/auth'
import { useAuth } from '@/lib/useAuth'

interface UserRecord {
  id: number
  email: string
  name: string | null
  avatar_url: string | null
  role: 'admin' | 'member'
  auth_provider: 'local' | 'workos'
  tenant_slug: string
  created_at: string
  last_login_at: string | null
}

interface InvitationRecord {
  id: string
  email: string
  state: 'pending' | 'accepted' | 'expired' | 'revoked' | string
  expires_at: string
  accepted_at: string | null
  revoked_at: string | null
  organization_id: string | null
  inviter_user_id: string | null
  created_at: string
  updated_at: string
}

async function fetchUsers(): Promise<UserRecord[]> {
  const response = await fetch(buildApiUrl('/api/v1/auth/users'), {
    headers: getAuthHeaders(),
    credentials: 'include',
  })
  if (!response.ok) throw new Error(`Failed to fetch users (${response.status})`)
  return (await response.json()) as UserRecord[]
}

async function updateUserRole(userId: number, role: string): Promise<UserRecord> {
  const csrfToken = getCsrfToken()
  const headers: Record<string, string> = {
    ...getAuthHeaders(),
    'Content-Type': 'application/json',
  }
  if (csrfToken) {
    headers['X-CSRF-Token'] = csrfToken
  }
  const response = await fetch(buildApiUrl(`/api/v1/auth/users/${userId}/role`), {
    method: 'PATCH',
    headers,
    credentials: 'include',
    body: JSON.stringify({ role }),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error((body as { detail?: string }).detail || `Failed to update role (${response.status})`)
  }
  return (await response.json()) as UserRecord
}

async function deleteUser(userId: number): Promise<void> {
  const csrfToken = getCsrfToken()
  const headers: Record<string, string> = { ...getAuthHeaders() }
  if (csrfToken) {
    headers['X-CSRF-Token'] = csrfToken
  }
  const response = await fetch(buildApiUrl(`/api/v1/auth/users/${userId}`), {
    method: 'DELETE',
    headers,
    credentials: 'include',
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error((body as { detail?: string }).detail || `Failed to delete user (${response.status})`)
  }
}

async function fetchInvitations(): Promise<InvitationRecord[]> {
  const response = await fetch(buildApiUrl('/api/v1/auth/invitations'), {
    headers: getAuthHeaders(),
    credentials: 'include',
  })
  if (!response.ok) throw new Error(`Failed to fetch invitations (${response.status})`)
  return (await response.json()) as InvitationRecord[]
}

async function sendInvitation(email: string): Promise<InvitationRecord> {
  const csrfToken = getCsrfToken()
  const headers: Record<string, string> = {
    ...getAuthHeaders(),
    'Content-Type': 'application/json',
  }
  if (csrfToken) {
    headers['X-CSRF-Token'] = csrfToken
  }
  const response = await fetch(buildApiUrl('/api/v1/auth/invitations'), {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify({ email }),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error((body as { detail?: string }).detail || `Failed to send invitation (${response.status})`)
  }
  return (await response.json()) as InvitationRecord
}

async function resendInvitation(invitationId: string): Promise<InvitationRecord> {
  const csrfToken = getCsrfToken()
  const headers: Record<string, string> = { ...getAuthHeaders() }
  if (csrfToken) {
    headers['X-CSRF-Token'] = csrfToken
  }
  const response = await fetch(buildApiUrl(`/api/v1/auth/invitations/${invitationId}/resend`), {
    method: 'POST',
    headers,
    credentials: 'include',
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error((body as { detail?: string }).detail || `Failed to resend invitation (${response.status})`)
  }
  return (await response.json()) as InvitationRecord
}

async function revokeInvitation(invitationId: string): Promise<InvitationRecord> {
  const csrfToken = getCsrfToken()
  const headers: Record<string, string> = { ...getAuthHeaders() }
  if (csrfToken) {
    headers['X-CSRF-Token'] = csrfToken
  }
  const response = await fetch(buildApiUrl(`/api/v1/auth/invitations/${invitationId}/revoke`), {
    method: 'POST',
    headers,
    credentials: 'include',
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error((body as { detail?: string }).detail || `Failed to revoke invitation (${response.status})`)
  }
  return (await response.json()) as InvitationRecord
}

export function UsersTab() {
  const { user: currentUser, sessionAuthProvider } = useAuth()
  const queryClient = useQueryClient()
  const [deleteTarget, setDeleteTarget] = useState<UserRecord | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [inviteEmail, setInviteEmail] = useState('')
  const [rowFeedback, setRowFeedback] = useState<{ userId: number; message: string; tone: 'success' | 'danger' } | null>(null)

  const usersQuery = useQuery({
    queryKey: ['users'],
    queryFn: fetchUsers,
  })

  const invitationsQuery = useQuery({
    queryKey: ['user-invitations'],
    queryFn: fetchInvitations,
    enabled: sessionAuthProvider === 'workos',
  })

  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: string }) =>
      updateUserRole(userId, role),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setError(null)
      setRowFeedback({ userId: variables.userId, message: 'Role updated.', tone: 'success' })
    },
    onError: (err: Error, variables) => {
      setError(err.message)
      setRowFeedback({ userId: variables.userId, message: err.message, tone: 'danger' })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setDeleteTarget(null)
      setError(null)
      setRowFeedback(null)
    },
    onError: (err: Error) => setError(err.message),
  })

  const inviteMutation = useMutation({
    mutationFn: (email: string) => sendInvitation(email),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user-invitations'] })
      setInviteEmail('')
      setError(null)
    },
    onError: (err: Error) => setError(err.message),
  })

  const resendMutation = useMutation({
    mutationFn: (invitationId: string) => resendInvitation(invitationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user-invitations'] })
      setError(null)
    },
    onError: (err: Error) => setError(err.message),
  })

  const revokeMutation = useMutation({
    mutationFn: (invitationId: string) => revokeInvitation(invitationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user-invitations'] })
      setError(null)
    },
    onError: (err: Error) => setError(err.message),
  })

  const rolePendingUserId = roleMutation.isPending ? roleMutation.variables?.userId ?? null : null

  const users = usersQuery.data ?? []
  const invitations = invitationsQuery.data ?? []
  const pendingInvitations = invitations.filter((invitation) => invitation.state === 'pending')
  const admins = users.filter((u) => u.role === 'admin')
  const members = users.filter((u) => u.role === 'member')

  if (usersQuery.isLoading && !usersQuery.data) {
    return <div className="py-12 text-center text-sm text-muted-foreground">Loading users...</div>
  }

  if (usersQuery.isError) {
    return (
      <EmptyState
        title="Users unavailable"
        body="User records could not be loaded. Refresh the page and verify the API is reachable."
      />
    )
  }

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="pt-4 pb-4">
            <p className="text-2xl font-bold">{users.length}</p>
            <p className="text-xs text-muted-foreground">Total Users</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <p className="text-2xl font-bold">{admins.length}</p>
            <p className="text-xs text-muted-foreground">Admins</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <p className="text-2xl font-bold">{members.length}</p>
            <p className="text-xs text-muted-foreground">Members</p>
          </CardContent>
        </Card>
        {sessionAuthProvider === 'workos' ? (
          <Card>
            <CardContent className="pt-4 pb-4">
              <p className="text-2xl font-bold">{pendingInvitations.length}</p>
              <p className="text-xs text-muted-foreground">Pending Invites</p>
            </CardContent>
          </Card>
        ) : null}
      </div>

      {error && (
        <div className="rounded-sm border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="rounded-sm border border-border bg-muted/40 px-4 py-3 text-xs text-muted-foreground">
        You cannot demote or delete your own account from this tenant. Use another admin account if you need to transfer ownership.
      </div>

      {sessionAuthProvider === 'workos' ? (
        <Card>
          <CardContent className="space-y-4 p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className="text-sm font-semibold">Email invites</p>
                <p className="text-xs text-muted-foreground">
                  Send WorkOS invitation emails so teammates join this tenant directly.
                </p>
              </div>
              <div className="flex w-full max-w-xl gap-2">
                <Input
                  type="email"
                  placeholder="teammate@company.com"
                  value={inviteEmail}
                  onChange={(event) => setInviteEmail(event.target.value)}
                />
                <Button
                  onClick={() => inviteMutation.mutate(inviteEmail.trim())}
                  disabled={!inviteEmail.trim() || inviteMutation.isPending}
                >
                  {inviteMutation.isPending ? 'Sending...' : 'Send invite'}
                </Button>
              </div>
            </div>

            {invitationsQuery.isLoading && !invitationsQuery.data ? (
              <div className="text-sm text-muted-foreground">Loading invitations...</div>
            ) : invitations.length === 0 ? (
              <div className="rounded-sm border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                No invitations have been sent for this tenant yet.
              </div>
            ) : (
              <div className="space-y-3">
                {invitations.map((invitation) => {
                  const pending = invitation.state === 'pending'
                  return (
                    <div
                      key={invitation.id}
                      className="flex flex-col gap-3 rounded-sm border border-border px-4 py-3 lg:flex-row lg:items-center lg:justify-between"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium">{invitation.email}</span>
                          <Badge
                            color={
                              invitation.state === 'accepted'
                                ? 'success'
                                : invitation.state === 'revoked'
                                  ? 'danger'
                                  : invitation.state === 'expired'
                                    ? 'warning'
                                    : 'default'
                            }
                            variant="flat"
                          >
                            {invitation.state}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          Sent {new Date(invitation.created_at).toLocaleString()} · Expires{' '}
                          {new Date(invitation.expires_at).toLocaleString()}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        {pending ? (
                          <>
                            <Button
                              variant="flat"
                              size="sm"
                              disabled={resendMutation.isPending || revokeMutation.isPending}
                              onClick={() => resendMutation.mutate(invitation.id)}
                            >
                              Resend
                            </Button>
                            <Button
                              color="danger"
                              variant="flat"
                              size="sm"
                              disabled={resendMutation.isPending || revokeMutation.isPending}
                              onClick={() => revokeMutation.mutate(invitation.id)}
                            >
                              Revoke
                            </Button>
                          </>
                        ) : null}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="rounded-sm border border-border bg-muted/40 px-4 py-3 text-xs text-muted-foreground">
          Email invites are available when this workspace uses WorkOS authentication.
        </div>
      )}

      {/* User List */}
      <Card>
        <CardContent className="p-0">
          <div className="divide-y divide-border">
            {usersQuery.isLoading && (
              <div className="p-8 text-center text-sm text-muted-foreground">Loading users...</div>
            )}
            {!usersQuery.isLoading && users.length === 0 && (
              <div className="p-8 text-center text-sm text-muted-foreground">No users found.</div>
            )}
            {users.map((user) => (
              <div key={user.id} className="flex items-center gap-4 px-4 py-3">
                {/* Avatar */}
                <div className="shrink-0">
                  {user.avatar_url ? (
                    <img
                      src={user.avatar_url}
                      alt=""
                      className="w-9 h-9 rounded-sm object-cover"
                    />
                  ) : (
                    <div className="w-9 h-9 rounded-sm bg-muted flex items-center justify-center">
                      <UserCircle className="w-5 h-5 text-muted-foreground" />
                    </div>
                  )}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm truncate">
                      {user.name || user.email}
                    </span>
                    {user.id === currentUser?.id ? (
                      <Badge variant="flat" className="text-[10px]">
                        You
                      </Badge>
                    ) : null}
                    <Badge variant={user.auth_provider === 'workos' ? 'default' : 'flat'} className="text-[10px]">
                      {user.auth_provider === 'workos' ? 'SSO' : 'Local'}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground truncate">{user.email}</p>
                  <p className="text-[10px] text-muted-foreground">
                    Joined {new Date(user.created_at).toLocaleDateString()}
                    {user.last_login_at && (
                      <> · Last login {new Date(user.last_login_at).toLocaleDateString()}</>
                    )}
                  </p>
                  {rowFeedback?.userId === user.id ? (
                    <p className={`text-[10px] ${rowFeedback.tone === 'success' ? 'text-success' : 'text-destructive'}`}>
                      {rowFeedback.message}
                    </p>
                  ) : rolePendingUserId === user.id ? (
                    <p className="text-[10px] text-muted-foreground">Saving role change...</p>
                  ) : null}
                </div>

                {/* Role selector */}
                <div className="shrink-0 w-28">
                  <Select
                    value={user.role}
                    onValueChange={(role) =>
                      roleMutation.mutate({ userId: user.id, role })
                    }
                    disabled={roleMutation.isPending || user.id === currentUser?.id}
                  >
                    <SelectTrigger className="h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="admin">
                        <div className="flex items-center gap-1.5">
                          <ShieldCheck className="w-3 h-3" />
                          Admin
                        </div>
                      </SelectItem>
                      <SelectItem value="member">
                        <div className="flex items-center gap-1.5">
                          <Shield className="w-3 h-3" />
                          Member
                        </div>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Delete */}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="shrink-0 text-muted-foreground hover:text-destructive"
                    disabled={deleteMutation.isPending || user.id === currentUser?.id}
                    onClick={() => setDeleteTarget(user)}
                  >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Delete Confirmation */}
      <Dialog open={deleteTarget !== null} onOpenChange={() => setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove User</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to remove{' '}
            <strong>{deleteTarget?.email}</strong> from this organization? This
            action cannot be undone.
          </p>
          {deleteTarget?.role === 'admin' && (
            <div className="rounded-sm border border-yellow-500/30 bg-yellow-500/5 px-3 py-2 text-xs text-yellow-600">
              This user is an admin. Removing them will revoke their administrative access.
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Removing...' : 'Remove User'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
