import { useEffect, useMemo, useState, type ReactNode } from 'react'

type Operator = {
  id: number
  email: string
  name: string
  role: 'admin' | 'viewer'
  auth_provider: 'local' | 'ldap'
  is_active: boolean
  created_at: string
  last_login_at: string | null
}

type LicenseKeyRecord = {
  id: number
  key_prefix: string
  license_type: string
  organization: string
  status: string
  created_at: string
  updated_at: string
  expires_at: string | null
  max_seats: number | null
  notes: string | null
  customer_metadata: Record<string, unknown>
  revoked_reason: string | null
  replaced_by_license_id: number | null
  last_verified_at: string | null
  verification_count: number
}

type VerificationLog = {
  id: number
  attempted_prefix: string
  instance_id: string | null
  ip_address: string | null
  verified_at: string
  success: boolean
  error_message: string | null
}

type DirectoryConfig = {
  enabled: boolean
  server_uri: string | null
  bind_dn: string | null
  user_base_dn: string | null
  user_filter: string
  group_base_dn: string | null
  admin_group_dn: string | null
  viewer_group_dn: string | null
  use_ssl: boolean
  start_tls: boolean
  bind_password_configured: boolean
  updated_at: string | null
}

type StatsResponse = {
  total_keys: number
  operators: number
  by_type_and_status: Array<{ type: string; status: string; count: number }>
  recent_verifications: { total: number; successful: number; failed: number }
}

type KeysResponse = {
  items: LicenseKeyRecord[]
  page: number
  page_size: number
  total: number
}

type AuditLogRecord = {
  id: number
  actor_user_id: number | null
  actor_email: string | null
  action: string
  entity_type: string
  entity_id: string
  details_json: Record<string, unknown>
  created_at: string
}

type AuditLogsResponse = {
  items: AuditLogRecord[]
  page: number
  page_size: number
  total: number
}

type TabId = 'dashboard' | 'audit' | 'operators' | 'directory'

function formatDate(value: string | null) {
  if (!value) return 'Never'
  return new Date(value).toLocaleString()
}

function toDateTimeLocalValue(value: string | null) {
  if (!value) return ''
  const date = new Date(value)
  const offset = date.getTimezoneOffset()
  const local = new Date(date.getTime() - offset * 60_000)
  return local.toISOString().slice(0, 16)
}

function parseErrorMessage(body: unknown, fallbackStatus: number) {
  if (typeof body === 'string' && body.trim()) return body
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = body.detail
    if (typeof detail === 'string' && detail.trim()) return detail
  }
  return `Request failed (${fallbackStatus})`
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  })
  if (!response.ok) {
    const rawBody = await response.text()
    let body: unknown = rawBody
    try {
      body = rawBody ? JSON.parse(rawBody) : rawBody
    } catch {
      // Preserve raw text bodies from non-JSON error responses.
    }
    throw new Error(parseErrorMessage(body, response.status))
  }
  if (response.status === 204) {
    return undefined as T
  }
  return response.json() as Promise<T>
}

function SectionTitle({
  eyebrow,
  title,
  body,
}: {
  eyebrow: string
  title: string
  body: string
}) {
  return (
    <div>
      <p
        style={{
          margin: 0,
          color: '#475569',
          fontSize: 12,
          fontWeight: 700,
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
        }}
      >
        {eyebrow}
      </p>
      <h2 style={{ margin: '0.4rem 0 0', fontSize: '1.6rem' }}>{title}</h2>
      <p style={{ margin: '0.35rem 0 0', color: '#475569', maxWidth: 680 }}>{body}</p>
    </div>
  )
}

function Panel({ children }: { children: ReactNode }) {
  return (
    <section
      style={{
        background: 'rgba(255,255,255,0.84)',
        borderRadius: 24,
        padding: 20,
        border: '1px solid rgba(25,28,30,0.08)',
      }}
    >
      {children}
    </section>
  )
}

function StatCard({
  label,
  value,
  hint,
}: {
  label: string
  value: string | number
  hint: string
}) {
  return (
    <div
      style={{
        background: 'rgba(255,255,255,0.82)',
        border: '1px solid rgba(25,28,30,0.08)',
        borderRadius: 24,
        padding: 20,
      }}
    >
      <p
        style={{
          margin: 0,
          color: '#64748b',
          fontSize: 12,
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
        }}
      >
        {label}
      </p>
      <p style={{ margin: '0.6rem 0 0', fontSize: 32, fontWeight: 700 }}>{value}</p>
      <p style={{ margin: '0.4rem 0 0', color: '#64748b' }}>{hint}</p>
    </div>
  )
}

function AppShell({
  currentUser,
  children,
  onLogout,
}: {
  currentUser: Operator
  children: ReactNode
  onLogout: () => void
}) {
  return (
    <div style={{ maxWidth: 1320, margin: '0 auto', padding: '2.4rem 1.4rem 3rem' }}>
      <header
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 16,
          marginBottom: '1.75rem',
          flexWrap: 'wrap',
        }}
      >
        <div>
          <p
            style={{
              margin: 0,
              color: '#1e40af',
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
            }}
          >
            VigilWeave
          </p>
          <h1 style={{ margin: '0.4rem 0 0', fontSize: '2.5rem' }}>License Console</h1>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontWeight: 700 }}>{currentUser.name}</div>
            <div style={{ color: '#64748b', fontSize: 14 }}>{currentUser.email}</div>
            <div style={{ color: '#64748b', fontSize: 14 }}>
              {currentUser.role} · {currentUser.auth_provider}
            </div>
          </div>
          <button style={{ background: '#1e3a5f', color: '#f8fafc' }} onClick={onLogout}>
            Log out
          </button>
        </div>
      </header>
      {children}
    </div>
  )
}

function LoginScreen({
  bootstrapRequired,
  onAuthenticated,
}: {
  bootstrapRequired: boolean
  onAuthenticated: (user: Operator) => void
}) {
  const [form, setForm] = useState({ email: '', password: '', name: '' })
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function submit() {
    setSubmitting(true)
    setError(null)
    try {
      const user = await api<Operator>(
        bootstrapRequired ? '/api/auth/bootstrap' : '/api/auth/login',
        {
          method: 'POST',
          body: JSON.stringify(
            bootstrapRequired
              ? { email: form.email, password: form.password, name: form.name }
              : { email: form.email, password: form.password },
          ),
        },
      )
      onAuthenticated(user)
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Authentication failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: 24 }}>
      <div
        style={{
          width: 'min(560px, 100%)',
          background: 'rgba(255,255,255,0.88)',
          borderRadius: 28,
          border: '1px solid rgba(25,28,30,0.08)',
          padding: 32,
          boxShadow: '0 30px 60px rgba(30, 41, 59, 0.08)',
        }}
      >
        <SectionTitle
          eyebrow={bootstrapRequired ? 'First Run' : 'Operator Login'}
          title={
            bootstrapRequired ? 'Create the first console admin' : 'Sign in to the license console'
          }
          body={
            bootstrapRequired
              ? 'Bootstrap creates the first local operator account. LDAP remains optional and can be enabled later from settings.'
              : 'Use a local operator account or an LDAP/AD-mapped login if directory auth is enabled.'
          }
        />
        <div style={{ display: 'grid', gap: 14, marginTop: 24 }}>
          {bootstrapRequired ? (
            <label>
              <div style={{ marginBottom: 6, fontWeight: 600 }}>Name</div>
              <input
                value={form.name}
                onChange={(event) =>
                  setForm((current) => ({ ...current, name: event.target.value }))
                }
              />
            </label>
          ) : null}
          <label>
            <div style={{ marginBottom: 6, fontWeight: 600 }}>Email</div>
            <input
              type="email"
              value={form.email}
              onChange={(event) =>
                setForm((current) => ({ ...current, email: event.target.value }))
              }
            />
          </label>
          <label>
            <div style={{ marginBottom: 6, fontWeight: 600 }}>Password</div>
            <input
              type="password"
              value={form.password}
              onChange={(event) =>
                setForm((current) => ({ ...current, password: event.target.value }))
              }
            />
          </label>
        </div>
        {error ? <p style={{ color: '#b43d32', marginTop: 16 }}>{error}</p> : null}
        <button
          style={{
            marginTop: 20,
            width: '100%',
            background: '#1e3a5f',
            color: '#f8fafc',
            padding: '0.92rem 1.2rem',
          }}
          disabled={submitting}
          onClick={() => void submit()}
        >
          {submitting ? 'Submitting...' : bootstrapRequired ? 'Create Admin Account' : 'Sign In'}
        </button>
      </div>
    </div>
  )
}

function KeysPanel({
  currentUser,
  selectedKey,
  onSelectKey,
}: {
  currentUser: Operator
  selectedKey: LicenseKeyRecord | null
  onSelectKey: (record: LicenseKeyRecord | null) => void
}) {
  const [keys, setKeys] = useState<LicenseKeyRecord[]>([])
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [verificationLogs, setVerificationLogs] = useState<VerificationLog[]>([])
  const [search, setSearch] = useState('')
  const [licenseType, setLicenseType] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [organization, setOrganization] = useState('')
  const [bulkSelection, setBulkSelection] = useState<Set<number>>(new Set())
  const [generateForm, setGenerateForm] = useState({
    organization: '',
    license_type: 'pro',
    expires_days: '',
    max_seats: '',
    notes: '',
  })
  const [detailForm, setDetailForm] = useState({
    notes: '',
    expires_at: '',
    max_seats: '',
    customer_metadata: '{}',
  })
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const selectedIds = useMemo(() => Array.from(bulkSelection), [bulkSelection])

  async function loadKeyDetails(id: number) {
    setError(null)
    try {
      const [record, logs] = await Promise.all([
        api<LicenseKeyRecord>(`/api/admin/keys/${id}`),
        api<VerificationLog[]>(`/api/admin/keys/${id}/verifications`),
      ])
      onSelectKey(record)
      setVerificationLogs(logs)
      setDetailForm({
        notes: record.notes ?? '',
        expires_at: toDateTimeLocalValue(record.expires_at),
        max_seats: record.max_seats ? String(record.max_seats) : '',
        customer_metadata: JSON.stringify(record.customer_metadata ?? {}, null, 2),
      })
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load key details')
    }
  }

  useEffect(() => {
    let active = true
    void (async () => {
      const params = new URLSearchParams()
      if (search) params.set('search', search)
      if (licenseType) params.set('license_type', licenseType)
      if (statusFilter) params.set('status', statusFilter)
      if (organization) params.set('organization', organization)
      try {
        const [keysResponse, statsResponse] = await Promise.all([
          api<KeysResponse>(`/api/admin/keys?${params.toString()}`),
          api<StatsResponse>('/api/admin/stats'),
        ])
        if (!active) return
        setError(null)
        setKeys(keysResponse.items)
        setStats(statsResponse)
      } catch (loadError) {
        if (!active) return
        setError(loadError instanceof Error ? loadError.message : 'Failed to load license data')
      }
    })()
    return () => {
      active = false
    }
  }, [search, licenseType, statusFilter, organization])

  async function generateKey() {
    setMessage(null)
    setError(null)
    try {
      const result = await api<{ license_key: string; record: LicenseKeyRecord }>(
        '/api/admin/keys/generate',
        {
          method: 'POST',
          body: JSON.stringify({
            organization: generateForm.organization,
            license_type: generateForm.license_type,
            expires_days: generateForm.expires_days ? Number(generateForm.expires_days) : null,
            max_seats: generateForm.max_seats ? Number(generateForm.max_seats) : null,
            notes: generateForm.notes || null,
          }),
        },
      )
      setMessage(`Issued key: ${result.license_key}`)
      setGenerateForm({
        organization: '',
        license_type: 'pro',
        expires_days: '',
        max_seats: '',
        notes: '',
      })
      const params = new URLSearchParams()
      if (search) params.set('search', search)
      if (licenseType) params.set('license_type', licenseType)
      if (statusFilter) params.set('status', statusFilter)
      if (organization) params.set('organization', organization)
      const [keysResponse, statsResponse] = await Promise.all([
        api<KeysResponse>(`/api/admin/keys?${params.toString()}`),
        api<StatsResponse>('/api/admin/stats'),
      ])
      setKeys(keysResponse.items)
      setStats(statsResponse)
      await loadKeyDetails(result.record.id)
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Failed to issue key')
    }
  }

  async function saveDetails() {
    if (!selectedKey) return
    setMessage(null)
    setError(null)
    try {
      const metadata = JSON.parse(detailForm.customer_metadata || '{}') as Record<string, unknown>
      await api<LicenseKeyRecord>(`/api/admin/keys/${selectedKey.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          notes: detailForm.notes || null,
          expires_at: detailForm.expires_at ? new Date(detailForm.expires_at).toISOString() : null,
          max_seats: detailForm.max_seats ? Number(detailForm.max_seats) : null,
          customer_metadata: metadata,
        }),
      })
      setMessage('Key metadata updated')
      const params = new URLSearchParams()
      if (search) params.set('search', search)
      if (licenseType) params.set('license_type', licenseType)
      if (statusFilter) params.set('status', statusFilter)
      if (organization) params.set('organization', organization)
      const [keysResponse, statsResponse] = await Promise.all([
        api<KeysResponse>(`/api/admin/keys?${params.toString()}`),
        api<StatsResponse>('/api/admin/stats'),
      ])
      setKeys(keysResponse.items)
      setStats(statsResponse)
      await loadKeyDetails(selectedKey.id)
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Failed to update key')
    }
  }

  async function runKeyAction(
    path: string,
    body: Record<string, unknown> = {},
    successMessage?: string,
  ) {
    if (!selectedKey) return
    setMessage(null)
    setError(null)
    try {
      await api(`/api/admin/keys/${selectedKey.id}${path}`, {
        method: 'POST',
        body: JSON.stringify(body),
      })
      if (successMessage) setMessage(successMessage)
      const params = new URLSearchParams()
      if (search) params.set('search', search)
      if (licenseType) params.set('license_type', licenseType)
      if (statusFilter) params.set('status', statusFilter)
      if (organization) params.set('organization', organization)
      const [keysResponse, statsResponse] = await Promise.all([
        api<KeysResponse>(`/api/admin/keys?${params.toString()}`),
        api<StatsResponse>('/api/admin/stats'),
      ])
      setKeys(keysResponse.items)
      setStats(statsResponse)
      await loadKeyDetails(selectedKey.id)
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Key action failed')
    }
  }

  async function reissueSelectedKey() {
    if (!selectedKey) return
    setMessage(null)
    setError(null)
    try {
      const result = await api<{ license_key: string; record: LicenseKeyRecord }>(
        `/api/admin/keys/${selectedKey.id}/reissue`,
        {
          method: 'POST',
          body: JSON.stringify({}),
        },
      )
      setMessage(`Replacement key: ${result.license_key}`)
      const params = new URLSearchParams()
      if (search) params.set('search', search)
      if (licenseType) params.set('license_type', licenseType)
      if (statusFilter) params.set('status', statusFilter)
      if (organization) params.set('organization', organization)
      const [keysResponse, statsResponse] = await Promise.all([
        api<KeysResponse>(`/api/admin/keys?${params.toString()}`),
        api<StatsResponse>('/api/admin/stats'),
      ])
      setKeys(keysResponse.items)
      setStats(statsResponse)
      await loadKeyDetails(result.record.id)
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Failed to reissue key')
    }
  }

  async function bulkAction(action: 'revoke' | 'reactivate') {
    if (selectedIds.length === 0) return
    setMessage(null)
    setError(null)
    try {
      const result = await api<{ updated: number }>('/api/admin/keys/bulk', {
        method: 'POST',
        body: JSON.stringify({ action, key_ids: selectedIds }),
      })
      setMessage(`${result.updated} keys updated`)
      setBulkSelection(new Set())
      const params = new URLSearchParams()
      if (search) params.set('search', search)
      if (licenseType) params.set('license_type', licenseType)
      if (statusFilter) params.set('status', statusFilter)
      if (organization) params.set('organization', organization)
      const [keysResponse, statsResponse] = await Promise.all([
        api<KeysResponse>(`/api/admin/keys?${params.toString()}`),
        api<StatsResponse>('/api/admin/stats'),
      ])
      setKeys(keysResponse.items)
      setStats(statsResponse)
      if (selectedKey) await loadKeyDetails(selectedKey.id)
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Bulk action failed')
    }
  }

  return (
    <div style={{ display: 'grid', gap: 24 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 16 }}>
        <StatCard label="Issued Keys" value={stats?.total_keys ?? '...'} hint="All currently tracked keys" />
        <StatCard label="Operators" value={stats?.operators ?? '...'} hint="Local plus LDAP shadow users" />
        <StatCard
          label="24h Verifications"
          value={stats?.recent_verifications.total ?? '...'}
          hint="Recent public verify traffic"
        />
        <StatCard
          label="24h Failures"
          value={stats?.recent_verifications.failed ?? '...'}
          hint="Revoked, expired, or invalid requests"
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 2fr 1.3fr', gap: 20 }}>
        <Panel>
          <SectionTitle
            eyebrow="Generate"
            title="Issue a new key"
            body="Keys are shown once at issue time and then only their hashes remain in storage."
          />
          <div style={{ display: 'grid', gap: 12, marginTop: 18 }}>
            <input
              placeholder="Organization"
              value={generateForm.organization}
              onChange={(event) =>
                setGenerateForm((current) => ({ ...current, organization: event.target.value }))
              }
            />
            <select
              value={generateForm.license_type}
              onChange={(event) =>
                setGenerateForm((current) => ({ ...current, license_type: event.target.value }))
              }
            >
              <option value="pro">Pro</option>
              <option value="enterprise_standard">Enterprise (Online)</option>
              <option value="enterprise_offline">Enterprise (Offline)</option>
            </select>
            <input
              placeholder="Expires in days"
              value={generateForm.expires_days}
              onChange={(event) =>
                setGenerateForm((current) => ({ ...current, expires_days: event.target.value }))
              }
            />
            <input
              placeholder="Max seats"
              value={generateForm.max_seats}
              onChange={(event) =>
                setGenerateForm((current) => ({ ...current, max_seats: event.target.value }))
              }
            />
            <textarea
              placeholder="Notes"
              rows={4}
              value={generateForm.notes}
              onChange={(event) =>
                setGenerateForm((current) => ({ ...current, notes: event.target.value }))
              }
            />
            {currentUser.role === 'admin' ? (
              <button style={{ background: '#1e3a5f', color: '#fff' }} onClick={() => void generateKey()}>
                Issue Key
              </button>
            ) : (
              <p style={{ margin: 0, color: '#64748b' }}>
                Viewer accounts can inspect keys but cannot issue or change them.
              </p>
            )}
            <a href="/api/admin/keys/export.csv" style={{ color: '#1e40af', fontWeight: 700 }}>
              Export CSV
            </a>
            <div style={{ display: 'grid', gap: 8 }}>
              {(stats?.by_type_and_status ?? []).map((row) => (
                <div
                  key={`${row.type}-${row.status}`}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: 12,
                    padding: 10,
                    borderRadius: 16,
                    background: '#eff6ff',
                  }}
                >
                  <span>
                    {row.type} · {row.status}
                  </span>
                  <strong>{row.count}</strong>
                </div>
              ))}
            </div>
            {message ? <p style={{ color: '#1e40af', margin: 0, wordBreak: 'break-word' }}>{message}</p> : null}
            {error ? <p style={{ color: '#b43d32', margin: 0 }}>{error}</p> : null}
          </div>
        </Panel>

        <Panel>
          <SectionTitle
            eyebrow="Inventory"
            title="Issued license keys"
            body="Search by org or prefix, then inspect the selected key for lifecycle actions and history."
          />
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', gap: 10, marginTop: 18 }}>
            <input placeholder="Search" value={search} onChange={(event) => setSearch(event.target.value)} />
            <input
              placeholder="Organization"
              value={organization}
              onChange={(event) => setOrganization(event.target.value)}
            />
            <select value={licenseType} onChange={(event) => setLicenseType(event.target.value)}>
              <option value="">All types</option>
              <option value="pro">Pro</option>
              <option value="enterprise_standard">Enterprise (Online)</option>
              <option value="enterprise_offline">Enterprise (Offline)</option>
            </select>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">All statuses</option>
              <option value="active">Active</option>
              <option value="expired">Expired</option>
              <option value="revoked">Revoked</option>
              <option value="replaced">Replaced</option>
            </select>
          </div>
          {currentUser.role === 'admin' ? (
            <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
              <button
                style={{ background: '#a24036', color: '#fff' }}
                disabled={selectedIds.length === 0}
                onClick={() => void bulkAction('revoke')}
              >
                Bulk Revoke ({selectedIds.length})
              </button>
              <button
                style={{ background: '#dbeafe', color: '#1e3a5f' }}
                disabled={selectedIds.length === 0}
                onClick={() => void bulkAction('reactivate')}
              >
                Bulk Reactivate ({selectedIds.length})
              </button>
            </div>
          ) : null}
          <div style={{ marginTop: 16, overflow: 'auto', maxHeight: 540 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ textAlign: 'left', color: '#64748b' }}>
                  <th />
                  <th style={{ paddingBottom: 10 }}>Prefix</th>
                  <th>Org</th>
                  <th>Type</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {keys.map((key) => (
                  <tr
                    key={key.id}
                    style={{
                      cursor: 'pointer',
                      borderTop: '1px solid rgba(25,28,30,0.06)',
                      background: selectedKey?.id === key.id ? '#eff6ff' : 'transparent',
                    }}
                    onClick={() => void loadKeyDetails(key.id)}
                  >
                    <td style={{ padding: '12px 6px 12px 0' }}>
                      <input
                        type="checkbox"
                        checked={bulkSelection.has(key.id)}
                        onChange={(event) => {
                          event.stopPropagation()
                          setBulkSelection((current) => {
                            const next = new Set(current)
                            if (next.has(key.id)) next.delete(key.id)
                            else next.add(key.id)
                            return next
                          })
                        }}
                      />
                    </td>
                    <td style={{ padding: '12px 0', fontWeight: 700 }}>{key.key_prefix}</td>
                    <td>{key.organization}</td>
                    <td>{key.license_type}</td>
                    <td>{key.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p style={{ margin: '12px 0 0', color: '#64748b' }}>{keys.length} visible keys</p>
        </Panel>

        <Panel>
          <SectionTitle
            eyebrow="Detail"
            title={selectedKey ? selectedKey.key_prefix : 'Select a key'}
            body={
              selectedKey
                ? 'Edit operational metadata, inspect status, and review verification history.'
                : 'Choose a key from the inventory table to inspect its details.'
            }
          />
          {selectedKey ? (
            <div style={{ display: 'grid', gap: 12, marginTop: 18 }}>
              <div style={{ color: '#64748b', display: 'grid', gap: 4 }}>
                <div>
                  <strong>Org:</strong> {selectedKey.organization}
                </div>
                <div>
                  <strong>Status:</strong> {selectedKey.status}
                </div>
                <div>
                  <strong>Verifications:</strong> {selectedKey.verification_count}
                </div>
                <div>
                  <strong>Last verified:</strong> {formatDate(selectedKey.last_verified_at)}
                </div>
                <div>
                  <strong>Expires:</strong> {selectedKey.expires_at ? formatDate(selectedKey.expires_at) : 'No expiry'}
                </div>
                <div>
                  <strong>Revocation reason:</strong> {selectedKey.revoked_reason ?? 'N/A'}
                </div>
              </div>
              <label>
                <div style={{ marginBottom: 6, fontWeight: 600 }}>Expires At</div>
                <input
                  type="datetime-local"
                  value={detailForm.expires_at}
                  onChange={(event) =>
                    setDetailForm((current) => ({ ...current, expires_at: event.target.value }))
                  }
                />
              </label>
              <label>
                <div style={{ marginBottom: 6, fontWeight: 600 }}>Max Seats</div>
                <input
                  value={detailForm.max_seats}
                  onChange={(event) =>
                    setDetailForm((current) => ({ ...current, max_seats: event.target.value }))
                  }
                />
              </label>
              <label>
                <div style={{ marginBottom: 6, fontWeight: 600 }}>Notes</div>
                <textarea
                  rows={4}
                  value={detailForm.notes}
                  onChange={(event) =>
                    setDetailForm((current) => ({ ...current, notes: event.target.value }))
                  }
                />
              </label>
              <label>
                <div style={{ marginBottom: 6, fontWeight: 600 }}>Customer Metadata (JSON)</div>
                <textarea
                  rows={6}
                  value={detailForm.customer_metadata}
                  onChange={(event) =>
                    setDetailForm((current) => ({
                      ...current,
                      customer_metadata: event.target.value,
                    }))
                  }
                />
              </label>
              {currentUser.role === 'admin' ? (
                <div style={{ display: 'grid', gap: 8 }}>
                  <button style={{ background: '#dbeafe', color: '#1e3a5f' }} onClick={() => void saveDetails()}>
                    Save Detail Changes
                  </button>
                  <button
                    style={{ background: '#a24036', color: '#fff' }}
                    onClick={() => void runKeyAction('/revoke', { reason: 'Revoked from console' }, 'Key revoked')}
                  >
                    Revoke Key
                  </button>
                  <button
                    style={{ background: '#dbeafe', color: '#1e3a5f' }}
                    onClick={() => void runKeyAction('/reactivate', {}, 'Key reactivated')}
                  >
                    Reactivate Key
                  </button>
                  <button style={{ background: '#1e3a5f', color: '#fff' }} onClick={() => void reissueSelectedKey()}>
                    Reissue Key
                  </button>
                </div>
              ) : null}
              <div>
                <h3 style={{ marginBottom: 10 }}>Verification History</h3>
                <div style={{ display: 'grid', gap: 8, maxHeight: 220, overflow: 'auto' }}>
                  {verificationLogs.map((entry) => (
                    <div
                      key={entry.id}
                      style={{
                        padding: 12,
                        borderRadius: 18,
                        background: '#f1f5f9',
                        border: '1px solid rgba(25,28,30,0.06)',
                      }}
                    >
                      <div style={{ fontWeight: 700 }}>{entry.success ? 'Success' : 'Failure'}</div>
                      <div style={{ color: '#64748b', fontSize: 14 }}>{formatDate(entry.verified_at)}</div>
                      {entry.instance_id ? (
                        <div style={{ color: '#64748b', fontSize: 14 }}>
                          Instance: {entry.instance_id}
                        </div>
                      ) : null}
                      {entry.ip_address ? (
                        <div style={{ color: '#64748b', fontSize: 14 }}>IP: {entry.ip_address}</div>
                      ) : null}
                      {entry.error_message ? (
                        <div style={{ color: '#aa493f', fontSize: 14 }}>{entry.error_message}</div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : null}
        </Panel>
      </div>
    </div>
  )
}

function OperatorsPanel() {
  const [operators, setOperators] = useState<Operator[]>([])
  const [createForm, setCreateForm] = useState({
    email: '',
    name: '',
    password: '',
    role: 'viewer',
  })
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    void (async () => {
      try {
        const data = await api<Operator[]>('/api/admin/operators')
        if (!active) return
        setError(null)
        setOperators(data)
      } catch (loadError) {
        if (!active) return
        setError(loadError instanceof Error ? loadError.message : 'Failed to load operators')
      }
    })()
    return () => {
      active = false
    }
  }, [])

  async function createOperator() {
    setMessage(null)
    setError(null)
    try {
      await api<Operator>('/api/admin/operators', {
        method: 'POST',
        body: JSON.stringify(createForm),
      })
      setCreateForm({ email: '', name: '', password: '', role: 'viewer' })
      setMessage('Operator created')
      const data = await api<Operator[]>('/api/admin/operators')
      setOperators(data)
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Failed to create operator')
    }
  }

  async function updateOperator(operatorId: number, body: Record<string, unknown>) {
    setMessage(null)
    setError(null)
    try {
      await api(`/api/admin/operators/${operatorId}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      })
      setMessage('Operator updated')
      const data = await api<Operator[]>('/api/admin/operators')
      setOperators(data)
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : 'Failed to update operator')
    }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.4fr', gap: 20 }}>
      <Panel>
        <SectionTitle
          eyebrow="Access"
          title="Operators"
          body="Local operators remain the break-glass path even when LDAP is enabled."
        />
        <div style={{ display: 'grid', gap: 12, marginTop: 18 }}>
          <input
            placeholder="Email"
            value={createForm.email}
            onChange={(event) =>
              setCreateForm((current) => ({ ...current, email: event.target.value }))
            }
          />
          <input
            placeholder="Name"
            value={createForm.name}
            onChange={(event) =>
              setCreateForm((current) => ({ ...current, name: event.target.value }))
            }
          />
          <input
            type="password"
            placeholder="Password"
            value={createForm.password}
            onChange={(event) =>
              setCreateForm((current) => ({ ...current, password: event.target.value }))
            }
          />
          <select
            value={createForm.role}
            onChange={(event) =>
              setCreateForm((current) => ({ ...current, role: event.target.value }))
            }
          >
            <option value="viewer">Viewer</option>
            <option value="admin">Admin</option>
          </select>
          <button style={{ background: '#1e3a5f', color: '#fff' }} onClick={() => void createOperator()}>
            Create Operator
          </button>
          {message ? <p style={{ margin: 0, color: '#1e40af' }}>{message}</p> : null}
          {error ? <p style={{ margin: 0, color: '#b43d32' }}>{error}</p> : null}
        </div>
      </Panel>
      <Panel>
        <SectionTitle
          eyebrow="Roster"
          title="Current operators"
          body="Promote, demote, or disable operators without removing the final active admin."
        />
        <div style={{ display: 'grid', gap: 12, marginTop: 18 }}>
          {operators.map((operator) => (
            <div
              key={operator.id}
              style={{
                padding: 16,
                borderRadius: 20,
                background: '#f1f5f9',
                border: '1px solid rgba(25,28,30,0.06)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 12,
                  alignItems: 'center',
                  flexWrap: 'wrap',
                }}
              >
                <div>
                  <div style={{ fontWeight: 700 }}>{operator.name}</div>
                  <div style={{ color: '#64748b', fontSize: 14 }}>{operator.email}</div>
                  <div style={{ color: '#64748b', fontSize: 14 }}>
                    {operator.auth_provider} · {operator.role} ·{' '}
                    {operator.is_active ? 'active' : 'disabled'}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    style={{ background: '#dbeafe', color: '#1e3a5f' }}
                    onClick={() =>
                      void updateOperator(operator.id, {
                        role: operator.role === 'admin' ? 'viewer' : 'admin',
                      })
                    }
                  >
                    Toggle Role
                  </button>
                  <button
                    style={{ background: operator.is_active ? '#a24036' : '#1e3a5f', color: '#fff' }}
                    onClick={() =>
                      void updateOperator(operator.id, { is_active: !operator.is_active })
                    }
                  >
                    {operator.is_active ? 'Disable' : 'Enable'}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  )
}

function DirectoryPanel() {
  const [config, setConfig] = useState<DirectoryConfig | null>(null)
  const [form, setForm] = useState({
    enabled: false,
    server_uri: '',
    bind_dn: '',
    bind_password: '',
    user_base_dn: '',
    user_filter: '(mail={email})',
    group_base_dn: '',
    admin_group_dn: '',
    viewer_group_dn: '',
    use_ssl: true,
    start_tls: false,
  })
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [testLogin, setTestLogin] = useState({ email: '', password: '' })

  useEffect(() => {
    let active = true
    void (async () => {
      try {
        const current = await api<DirectoryConfig>('/api/admin/directory-config')
        if (!active) return
        setError(null)
        setConfig(current)
        setForm({
          enabled: current.enabled,
          server_uri: current.server_uri ?? '',
          bind_dn: current.bind_dn ?? '',
          bind_password: '',
          user_base_dn: current.user_base_dn ?? '',
          user_filter: current.user_filter,
          group_base_dn: current.group_base_dn ?? '',
          admin_group_dn: current.admin_group_dn ?? '',
          viewer_group_dn: current.viewer_group_dn ?? '',
          use_ssl: current.use_ssl,
          start_tls: current.start_tls,
        })
      } catch (loadError) {
        if (!active) return
        setError(loadError instanceof Error ? loadError.message : 'Failed to load directory config')
      }
    })()
    return () => {
      active = false
    }
  }, [])

  async function save() {
    setMessage(null)
    setError(null)
    try {
      const updated = await api<DirectoryConfig>('/api/admin/directory-config', {
        method: 'PUT',
        body: JSON.stringify(form),
      })
      setConfig(updated)
      setMessage('Directory configuration saved')
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Failed to save directory config')
    }
  }

  async function testConnection() {
    setMessage(null)
    setError(null)
    try {
      await api('/api/admin/directory-config/test-connection', { method: 'POST' })
      setMessage('Connection test succeeded')
    } catch (testError) {
      setError(testError instanceof Error ? testError.message : 'Directory test failed')
    }
  }

  async function testDirectoryLogin() {
    setMessage(null)
    setError(null)
    try {
      const result = await api<{ status: string; name: string; role: string }>(
        '/api/admin/directory-config/test-login',
        {
          method: 'POST',
          body: JSON.stringify(testLogin),
        },
      )
      setMessage(`Directory login ok: ${result.name} (${result.role})`)
    } catch (testError) {
      setError(testError instanceof Error ? testError.message : 'Directory login test failed')
    }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 0.9fr', gap: 20 }}>
      <Panel>
        <SectionTitle
          eyebrow="Directory"
          title="LDAP / Active Directory"
          body="This release supports one directory profile with login-time auth and group-based role mapping."
        />
        <div style={{ display: 'grid', gap: 12, marginTop: 18 }}>
          <label>
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(event) =>
                setForm((current) => ({ ...current, enabled: event.target.checked }))
              }
            />{' '}
            Enable directory auth
          </label>
          <input
            placeholder="ldaps://dc.example.com"
            value={form.server_uri}
            onChange={(event) =>
              setForm((current) => ({ ...current, server_uri: event.target.value }))
            }
          />
          <input
            placeholder="Bind DN"
            value={form.bind_dn}
            onChange={(event) =>
              setForm((current) => ({ ...current, bind_dn: event.target.value }))
            }
          />
          <input
            type="password"
            placeholder={config?.bind_password_configured ? 'Bind password configured' : 'Bind password'}
            value={form.bind_password}
            onChange={(event) =>
              setForm((current) => ({ ...current, bind_password: event.target.value }))
            }
          />
          <input
            placeholder="User base DN"
            value={form.user_base_dn}
            onChange={(event) =>
              setForm((current) => ({ ...current, user_base_dn: event.target.value }))
            }
          />
          <input
            placeholder="User filter"
            value={form.user_filter}
            onChange={(event) =>
              setForm((current) => ({ ...current, user_filter: event.target.value }))
            }
          />
          <input
            placeholder="Group base DN"
            value={form.group_base_dn}
            onChange={(event) =>
              setForm((current) => ({ ...current, group_base_dn: event.target.value }))
            }
          />
          <input
            placeholder="Admin group DN"
            value={form.admin_group_dn}
            onChange={(event) =>
              setForm((current) => ({ ...current, admin_group_dn: event.target.value }))
            }
          />
          <input
            placeholder="Viewer group DN"
            value={form.viewer_group_dn}
            onChange={(event) =>
              setForm((current) => ({ ...current, viewer_group_dn: event.target.value }))
            }
          />
          <label>
            <input
              type="checkbox"
              checked={form.use_ssl}
              onChange={(event) =>
                setForm((current) => ({ ...current, use_ssl: event.target.checked }))
              }
            />{' '}
            Use SSL
          </label>
          <label>
            <input
              type="checkbox"
              checked={form.start_tls}
              onChange={(event) =>
                setForm((current) => ({ ...current, start_tls: event.target.checked }))
              }
            />{' '}
            Start TLS
          </label>
          <div style={{ display: 'flex', gap: 8 }}>
            <button style={{ background: '#1e3a5f', color: '#fff' }} onClick={() => void save()}>
              Save
            </button>
            <button
              style={{ background: '#dbeafe', color: '#1e3a5f' }}
              onClick={() => void testConnection()}
            >
              Test Connection
            </button>
          </div>
          {message ? <p style={{ margin: 0, color: '#1e40af' }}>{message}</p> : null}
          {error ? <p style={{ margin: 0, color: '#b43d32' }}>{error}</p> : null}
        </div>
      </Panel>
      <Panel>
        <SectionTitle
          eyebrow="Validation"
          title="Test a mapped login"
          body="Validate role mapping before enabling directory sign-in for operators."
        />
        <div style={{ display: 'grid', gap: 12, marginTop: 18 }}>
          <input
            placeholder="Email"
            value={testLogin.email}
            onChange={(event) =>
              setTestLogin((current) => ({ ...current, email: event.target.value }))
            }
          />
          <input
            type="password"
            placeholder="Password"
            value={testLogin.password}
            onChange={(event) =>
              setTestLogin((current) => ({ ...current, password: event.target.value }))
            }
          />
          <button style={{ background: '#1e3a5f', color: '#fff' }} onClick={() => void testDirectoryLogin()}>
            Test Login
          </button>
          <p style={{ color: '#64748b' }}>
            Bind credentials stay encrypted at rest. Local operators remain available for break-glass access.
          </p>
        </div>
      </Panel>
    </div>
  )
}

function AuditPanel() {
  const [logs, setLogs] = useState<AuditLogRecord[]>([])
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    void (async () => {
      try {
        const result = await api<AuditLogsResponse>('/api/admin/audit-logs?page_size=50')
        if (!active) return
        setLogs(result.items)
        setMessage(null)
      } catch (loadError) {
        if (!active) return
        setMessage(loadError instanceof Error ? loadError.message : 'Failed to load audit logs')
      }
    })()
    return () => {
      active = false
    }
  }, [])

  return (
    <Panel>
      <SectionTitle
        eyebrow="Audit"
        title="Operator activity"
        body="Review key lifecycle, directory, bootstrap, and operator auth events recorded by the console."
      />
      {message ? <p style={{ color: '#b43d32' }}>{message}</p> : null}
      <div style={{ display: 'grid', gap: 10, marginTop: 18 }}>
        {logs.map((entry) => (
          <div
            key={entry.id}
            style={{
              padding: 14,
              borderRadius: 18,
              background: '#f1f5f9',
              border: '1px solid rgba(25,28,30,0.06)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
              <strong>{entry.action}</strong>
              <span style={{ color: '#64748b' }}>{formatDate(entry.created_at)}</span>
            </div>
            <div style={{ color: '#64748b', marginTop: 6 }}>
              {entry.actor_email ?? 'system'} · {entry.entity_type} · {entry.entity_id}
            </div>
            <pre
              style={{
                margin: '10px 0 0',
                padding: 12,
                borderRadius: 14,
                background: '#eff6ff',
                overflowX: 'auto',
                whiteSpace: 'pre-wrap',
              }}
            >
              {JSON.stringify(entry.details_json, null, 2)}
            </pre>
          </div>
        ))}
      </div>
    </Panel>
  )
}

export function App() {
  const [currentUser, setCurrentUser] = useState<Operator | null>(null)
  const [bootstrapRequired, setBootstrapRequired] = useState(false)
  const [activeTab, setActiveTab] = useState<TabId>('dashboard')
  const [selectedKey, setSelectedKey] = useState<LicenseKeyRecord | null>(null)

  useEffect(() => {
    void (async () => {
      const bootstrap = await api<{ bootstrap_required: boolean }>('/api/auth/bootstrap-required')
      setBootstrapRequired(bootstrap.bootstrap_required)
      if (!bootstrap.bootstrap_required) {
        try {
          setCurrentUser(await api<Operator>('/api/auth/me'))
        } catch {
          setCurrentUser(null)
        }
      }
    })()
  }, [])

  async function logout() {
    await api('/api/auth/logout', { method: 'POST' })
    setCurrentUser(null)
    setActiveTab('dashboard')
    setSelectedKey(null)
    setBootstrapRequired(false)
  }

  function handleAuthenticated(user: Operator) {
    setCurrentUser(user)
    setBootstrapRequired(false)
  }

  if (!currentUser) {
    return <LoginScreen bootstrapRequired={bootstrapRequired} onAuthenticated={handleAuthenticated} />
  }

  const tabs: Array<{ id: TabId; label: string }> = [
    { id: 'dashboard', label: 'Keys & Dashboard' },
    { id: 'audit', label: 'Audit' },
  ]
  if (currentUser.role === 'admin') {
    tabs.push({ id: 'operators', label: 'Operators' }, { id: 'directory', label: 'Directory' })
  }

  return (
    <AppShell currentUser={currentUser} onLogout={() => void logout()}>
      <nav style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            style={{
              background: activeTab === tab.id ? '#1e3a5f' : 'rgba(255,255,255,0.7)',
              color: activeTab === tab.id ? '#fff' : '#1e3a5f',
            }}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {activeTab === 'dashboard' ? (
        <KeysPanel currentUser={currentUser} selectedKey={selectedKey} onSelectKey={setSelectedKey} />
      ) : null}
      {activeTab === 'audit' ? <AuditPanel /> : null}
      {activeTab === 'operators' && currentUser.role === 'admin' ? <OperatorsPanel /> : null}
      {activeTab === 'directory' && currentUser.role === 'admin' ? <DirectoryPanel /> : null}
    </AppShell>
  )
}
