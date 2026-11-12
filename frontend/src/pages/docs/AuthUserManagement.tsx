export function AuthUserManagement() {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-foreground mb-2">
          Authentication & User Management
        </h2>
        <p className="text-muted-foreground">
          VigilWeave supports multiple authentication modes depending on your
          deployment model. This guide covers local auth for self-hosted
          Community deployments, WorkOS-powered SSO for SaaS and Enterprise, and
          directory sync for Active Directory / Okta / SCIM providers.
        </p>
      </div>

      {/* Auth Modes Overview */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">
          Authentication Modes
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border border-border rounded-sm overflow-hidden">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-4 py-2 font-semibold text-foreground">
                  Mode
                </th>
                <th className="text-left px-4 py-2 font-semibold text-foreground">
                  Tier
                </th>
                <th className="text-left px-4 py-2 font-semibold text-foreground">
                  How It Works
                </th>
                <th className="text-left px-4 py-2 font-semibold text-foreground">
                  Configuration
                </th>
              </tr>
            </thead>
            <tbody className="text-muted-foreground divide-y divide-border">
              <tr>
                <td className="px-4 py-2 font-medium text-foreground">
                  Local Auth
                </td>
                <td className="px-4 py-2">Community</td>
                <td className="px-4 py-2">
                  Built-in email/password accounts. First user becomes admin.
                  Session cookies signed with{" "}
                  <code className="bg-muted px-1 rounded font-mono text-xs">
                    SESSION_SECRET
                  </code>
                  .
                </td>
                <td className="px-4 py-2 font-mono text-xs">
                  SESSION_AUTH_PROVIDER=local
                </td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-medium text-foreground">
                  WorkOS AuthKit
                </td>
                <td className="px-4 py-2">Pro / Enterprise</td>
                <td className="px-4 py-2">
                  OAuth 2.0 via WorkOS. Supports email/password, social login
                  (GitHub, Google, Microsoft, Apple), MFA (TOTP), and
                  enterprise SSO (SAML/OIDC).
                </td>
                <td className="px-4 py-2 font-mono text-xs">
                  SESSION_AUTH_PROVIDER=workos
                </td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-medium text-foreground">
                  API Key Only
                </td>
                <td className="px-4 py-2">All</td>
                <td className="px-4 py-2">
                  No browser sessions. Headless mode for CI/CD-only
                  deployments. API keys authenticate all requests.
                </td>
                <td className="px-4 py-2 font-mono text-xs">
                  SESSION_AUTH_PROVIDER=none
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="text-sm text-muted-foreground">
          API keys can be enabled alongside any session provider by setting{" "}
          <code className="bg-muted px-1.5 py-0.5 rounded font-mono text-xs">
            API_KEYS_ENABLED=true
          </code>
          . This is the recommended setup — WorkOS handles browser sessions
          while API keys handle CI/CD and automation.
        </p>
      </section>

      {/* Local Auth Setup */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">
          Local Auth (Community)
        </h3>
        <p className="text-muted-foreground">
          The Community edition uses built-in local authentication. No external
          identity provider is required.
        </p>
        <ol className="list-decimal list-inside space-y-2 text-muted-foreground">
          <li>
            <strong>First-run admin setup</strong> &mdash; On first visit,
            VigilWeave prompts you to create an admin account with an email and
            password. This account gets the <strong>admin</strong> role
            automatically.
          </li>
          <li>
            <strong>Additional users</strong> &mdash; In Community, additional
            users can be created via the setup flow or directly via API key
            access. Each user gets a password-based local account.
          </li>
          <li>
            <strong>Sessions</strong> &mdash; Signed cookies with the{" "}
            <code className="bg-muted px-1 rounded font-mono text-xs">
              SESSION_SECRET
            </code>{" "}
            value. Set this to a strong random string in production.
          </li>
        </ol>
      </section>

      {/* WorkOS SSO Setup */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">
          WorkOS SSO (Pro & Enterprise)
        </h3>
        <p className="text-muted-foreground">
          VigilWeave uses{" "}
          <a
            href="https://workos.com/docs/user-management"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary underline underline-offset-2"
          >
            WorkOS AuthKit
          </a>{" "}
          for managed authentication on SaaS and Enterprise deployments. WorkOS
          provides the hosted login UI, session management, and identity
          provider integrations.
        </p>

        <div className="space-y-2">
          <h4 className="font-semibold text-foreground text-sm">
            What&apos;s included by tier
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border border-border rounded-sm overflow-hidden">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-4 py-2 font-semibold text-foreground">
                    Capability
                  </th>
                  <th className="text-left px-4 py-2 font-semibold text-foreground">
                    Pro
                  </th>
                  <th className="text-left px-4 py-2 font-semibold text-foreground">
                    Enterprise
                  </th>
                </tr>
              </thead>
              <tbody className="text-muted-foreground divide-y divide-border">
                <tr>
                  <td className="px-4 py-2">Email/password login</td>
                  <td className="px-4 py-2 text-emerald-500">&#10003;</td>
                  <td className="px-4 py-2 text-emerald-500">&#10003;</td>
                </tr>
                <tr>
                  <td className="px-4 py-2">
                    Social login (GitHub, Google, Microsoft, Apple)
                  </td>
                  <td className="px-4 py-2 text-emerald-500">&#10003;</td>
                  <td className="px-4 py-2 text-emerald-500">&#10003;</td>
                </tr>
                <tr>
                  <td className="px-4 py-2">MFA (TOTP authenticator apps)</td>
                  <td className="px-4 py-2 text-emerald-500">&#10003;</td>
                  <td className="px-4 py-2 text-emerald-500">&#10003;</td>
                </tr>
                <tr>
                  <td className="px-4 py-2">
                    SSO / SAML 2.0 / OIDC connections
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">&mdash;</td>
                  <td className="px-4 py-2 text-emerald-500">&#10003;</td>
                </tr>
                <tr>
                  <td className="px-4 py-2">
                    Directory Sync (SCIM — AD, Okta, Azure AD, OneLogin)
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">&mdash;</td>
                  <td className="px-4 py-2 text-emerald-500">&#10003;</td>
                </tr>
                <tr>
                  <td className="px-4 py-2">Custom domain for login UI</td>
                  <td className="px-4 py-2 text-muted-foreground">&mdash;</td>
                  <td className="px-4 py-2 text-emerald-500">&#10003;</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Enterprise SSO Connections */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">
          Enterprise SSO Setup (SAML / OIDC)
        </h3>
        <div className="rounded-sm border border-primary/20 bg-primary/5 p-4 space-y-2">
          <p className="text-sm font-semibold text-primary">
            Self-Service for Enterprise Admins
          </p>
          <p className="text-sm text-muted-foreground">
            Enterprise customers configure their own SSO connections directly.
            No support ticket required. VigilWeave provides a WorkOS Admin
            Portal link that your IT team uses to set up and manage identity
            provider connections.
          </p>
        </div>
        <p className="text-muted-foreground">
          VigilWeave supports all major identity providers through WorkOS SSO
          connections:
        </p>
        <ul className="list-disc list-inside space-y-1 text-muted-foreground">
          <li>
            <strong>Azure Active Directory (Entra ID)</strong> &mdash; SAML 2.0
            or OIDC
          </li>
          <li>
            <strong>Okta</strong> &mdash; SAML 2.0 or OIDC
          </li>
          <li>
            <strong>Google Workspace</strong> &mdash; SAML 2.0 or OIDC
          </li>
          <li>
            <strong>OneLogin</strong> &mdash; SAML 2.0
          </li>
          <li>
            <strong>PingFederate / PingOne</strong> &mdash; SAML 2.0
          </li>
          <li>
            <strong>JumpCloud</strong> &mdash; SAML 2.0
          </li>
          <li>
            <strong>Any SAML 2.0 or OIDC compliant provider</strong>
          </li>
        </ul>

        <div className="space-y-2">
          <h4 className="font-semibold text-foreground text-sm">
            Setup Process
          </h4>
          <ol className="list-decimal list-inside space-y-2 text-muted-foreground">
            <li>
              <strong>Access the Admin Portal</strong> &mdash; Your VigilWeave
              org admin navigates to{" "}
              <strong>Settings &rarr; Organization &rarr; SSO</strong> (or
              receives the Admin Portal link from your account provisioning
              email).
            </li>
            <li>
              <strong>Select your identity provider</strong> &mdash; Choose from
              the list of supported providers (Azure AD, Okta, Google Workspace,
              etc.) or configure a generic SAML/OIDC connection.
            </li>
            <li>
              <strong>Exchange metadata</strong> &mdash; The Admin Portal
              provides the VigilWeave ACS URL and Entity ID. Enter these in your
              identity provider. Then paste your IdP metadata URL or XML back
              into the Admin Portal.
            </li>
            <li>
              <strong>Test the connection</strong> &mdash; Use the test button
              to verify SSO login works. Once verified, the connection is active
              for all users in your organization.
            </li>
            <li>
              <strong>Enforce SSO</strong> &mdash; Optionally require all users
              in your organization to authenticate via SSO (disabling
              email/password fallback).
            </li>
          </ol>
        </div>

        <div className="rounded-sm border border-yellow-500/30 bg-yellow-500/5 p-4 space-y-1">
          <p className="text-sm font-semibold text-yellow-500">
            No IT support ticket needed
          </p>
          <p className="text-sm text-muted-foreground">
            Enterprise admins configure SSO connections entirely self-service
            through the Admin Portal. Your IT team does <strong>not</strong>{" "}
            need to contact VigilWeave support to set up or modify SSO
            connections. If you need assistance, our support team is available
            but the tooling is designed for self-service operation.
          </p>
        </div>
      </section>

      {/* Directory Sync / SCIM */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">
          Directory Sync (SCIM)
        </h3>
        <p className="text-muted-foreground">
          Enterprise customers can synchronize user accounts from their
          corporate directory to VigilWeave automatically. When a user is added,
          updated, or deactivated in your directory (Active Directory, Okta,
          Azure AD, etc.), those changes are reflected in VigilWeave within
          minutes.
        </p>

        <div className="space-y-2">
          <h4 className="font-semibold text-foreground text-sm">
            Supported Directories
          </h4>
          <ul className="list-disc list-inside space-y-1 text-muted-foreground">
            <li>
              <strong>Azure Active Directory (Entra ID)</strong> &mdash; SCIM
              2.0 provisioning
            </li>
            <li>
              <strong>Okta</strong> &mdash; SCIM 2.0 provisioning
            </li>
            <li>
              <strong>OneLogin</strong> &mdash; SCIM 2.0 provisioning
            </li>
            <li>
              <strong>Google Workspace</strong> &mdash; Directory API
            </li>
            <li>
              <strong>JumpCloud</strong> &mdash; SCIM 2.0 provisioning
            </li>
            <li>
              <strong>Any SCIM 2.0 compliant provider</strong>
            </li>
          </ul>
        </div>

        <div className="space-y-2">
          <h4 className="font-semibold text-foreground text-sm">
            What Syncs
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border border-border rounded-sm overflow-hidden">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-4 py-2 font-semibold text-foreground">
                    Directory Event
                  </th>
                  <th className="text-left px-4 py-2 font-semibold text-foreground">
                    VigilWeave Action
                  </th>
                </tr>
              </thead>
              <tbody className="text-muted-foreground divide-y divide-border">
                <tr>
                  <td className="px-4 py-2">User created in directory</td>
                  <td className="px-4 py-2">
                    User account created in VigilWeave with{" "}
                    <strong>member</strong> role
                  </td>
                </tr>
                <tr>
                  <td className="px-4 py-2">User updated (name, email)</td>
                  <td className="px-4 py-2">
                    Profile updated on next login
                  </td>
                </tr>
                <tr>
                  <td className="px-4 py-2">
                    User deactivated / removed from group
                  </td>
                  <td className="px-4 py-2">
                    User session invalidated, access revoked
                  </td>
                </tr>
                <tr>
                  <td className="px-4 py-2">
                    Group membership changed
                  </td>
                  <td className="px-4 py-2">
                    Organization membership updated (when org-level sync is
                    configured)
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div className="space-y-2">
          <h4 className="font-semibold text-foreground text-sm">
            Setup Process
          </h4>
          <ol className="list-decimal list-inside space-y-2 text-muted-foreground">
            <li>
              <strong>Access the Admin Portal</strong> &mdash; Navigate to{" "}
              <strong>Settings &rarr; Organization &rarr; Directory Sync</strong>.
            </li>
            <li>
              <strong>Select your directory provider</strong> &mdash; Choose
              Azure AD, Okta, Google Workspace, etc.
            </li>
            <li>
              <strong>Configure SCIM endpoint</strong> &mdash; The Admin Portal
              provides a SCIM endpoint URL and Bearer token. Enter these in your
              directory provider&apos;s provisioning settings.
            </li>
            <li>
              <strong>Map groups (optional)</strong> &mdash; Map directory groups
              to VigilWeave organizations for automatic team assignment.
            </li>
            <li>
              <strong>Enable provisioning</strong> &mdash; Activate the
              connection. Initial sync runs immediately, subsequent changes sync
              within minutes.
            </li>
          </ol>
        </div>
      </section>

      {/* Roles & Permissions */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">
          Roles & Permissions
        </h3>
        <p className="text-muted-foreground">
          VigilWeave uses a role-based access model with two roles:
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border border-border rounded-sm overflow-hidden">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-4 py-2 font-semibold text-foreground">
                  Role
                </th>
                <th className="text-left px-4 py-2 font-semibold text-foreground">
                  Assignment
                </th>
                <th className="text-left px-4 py-2 font-semibold text-foreground">
                  Permissions
                </th>
              </tr>
            </thead>
            <tbody className="text-muted-foreground divide-y divide-border">
              <tr>
                <td className="px-4 py-2 font-medium text-foreground">
                  Admin
                </td>
                <td className="px-4 py-2">
                  First user in the organization automatically. Additional
                  admins promoted manually.
                </td>
                <td className="px-4 py-2">
                  Full access: create/delete projects, manage policies, configure
                  integrations, manage API keys, view metrics, tool
                  configuration, user management
                </td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-medium text-foreground">
                  Member
                </td>
                <td className="px-4 py-2">
                  All subsequent users (via SSO, directory sync, or local
                  invite).
                </td>
                <td className="px-4 py-2">
                  Read access to projects, scans, and findings. Can trigger
                  scans, triage findings, and view reports. Cannot modify
                  settings, policies, or integrations.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="text-sm text-muted-foreground">
          Role assignment works automatically:
        </p>
        <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
          <li>
            <strong>Local auth:</strong> The first user to complete setup
            becomes admin. Additional users are members.
          </li>
          <li>
            <strong>WorkOS / SSO:</strong> The first user in each tenant
            (organization) becomes admin. Subsequent SSO users become members.
          </li>
          <li>
            <strong>Directory sync:</strong> Provisioned users start as members.
            Admin promotion is manual.
          </li>
        </ul>
      </section>

      {/* Admin User Management */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">
          Admin User Management
        </h3>
        <p className="text-muted-foreground">
          Admins can manage their organization&apos;s users directly from the
          dashboard. Navigate to{" "}
          <strong>Settings &rarr; Users</strong> to view, promote, or remove
          team members.
        </p>

        <div className="space-y-2">
          <h4 className="font-semibold text-foreground text-sm">
            Available Actions
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border border-border rounded-sm overflow-hidden">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-4 py-2 font-semibold text-foreground">
                    Action
                  </th>
                  <th className="text-left px-4 py-2 font-semibold text-foreground">
                    How
                  </th>
                  <th className="text-left px-4 py-2 font-semibold text-foreground">
                    Notes
                  </th>
                </tr>
              </thead>
              <tbody className="text-muted-foreground divide-y divide-border">
                <tr>
                  <td className="px-4 py-2 font-medium text-foreground">
                    View all users
                  </td>
                  <td className="px-4 py-2">
                    Settings &rarr; Users tab shows every user in your tenant
                    with their role, auth provider (SSO or Local), join date,
                    and last login.
                  </td>
                  <td className="px-4 py-2">Admin-only view</td>
                </tr>
                <tr>
                  <td className="px-4 py-2 font-medium text-foreground">
                    Change role
                  </td>
                  <td className="px-4 py-2">
                    Use the role dropdown next to any user to switch between{" "}
                    <strong>Admin</strong> and <strong>Member</strong>.
                  </td>
                  <td className="px-4 py-2">
                    You cannot demote your own account. At least one admin must
                    remain.
                  </td>
                </tr>
                <tr>
                  <td className="px-4 py-2 font-medium text-foreground">
                    Remove user
                  </td>
                  <td className="px-4 py-2">
                    Click the delete icon next to any user. A confirmation
                    dialog appears before removal.
                  </td>
                  <td className="px-4 py-2">
                    You cannot delete your own account. Removal is permanent
                    &mdash; SSO users can re-join by signing in again but start
                    as a member.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div className="rounded-sm border border-primary/20 bg-primary/5 p-4 space-y-1">
          <p className="text-sm font-semibold text-primary">
            Audit Trail
          </p>
          <p className="text-sm text-muted-foreground">
            All user management actions (role changes, user removals) are
            recorded in the audit log with the acting admin&apos;s identity,
            timestamp, and details of the change. Access audit events from{" "}
            <strong>Settings &rarr; Platform &rarr; Audit Log</strong> or via
            the{" "}
            <code className="bg-muted px-1 rounded font-mono text-xs">
              GET /api/v1/audit-events
            </code>{" "}
            endpoint.
          </p>
        </div>

        <div className="space-y-2">
          <h4 className="font-semibold text-foreground text-sm">
            API Endpoints
          </h4>
          <p className="text-sm text-muted-foreground">
            User management is also available via the REST API for automation:
          </p>
          <div className="code-block">
            <pre>{`# List all users in your tenant
curl -H "Authorization: Bearer vw_your_api_key" \\
  https://app.vigilweave.com/api/v1/auth/users

# Promote a user to admin
curl -X PATCH https://app.vigilweave.com/api/v1/auth/users/42/role \\
  -H "Authorization: Bearer vw_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{"role": "admin"}'

# Remove a user
curl -X DELETE https://app.vigilweave.com/api/v1/auth/users/42 \\
  -H "Authorization: Bearer vw_your_api_key"`}</pre>
          </div>
        </div>
      </section>

      {/* Tenant Isolation */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">
          Tenant Isolation
        </h3>
        <p className="text-muted-foreground">
          Every entity in VigilWeave (projects, scans, findings, policies, API
          keys) is scoped to a{" "}
          <code className="bg-muted px-1 rounded font-mono text-xs">
            tenant_slug
          </code>
          . Users within one tenant cannot access data from another tenant.
        </p>
        <ul className="list-disc list-inside space-y-1 text-muted-foreground">
          <li>
            <strong>Self-hosted:</strong> Typically a single tenant (
            <code className="bg-muted px-1 rounded font-mono text-xs">
              default
            </code>
            ).
          </li>
          <li>
            <strong>SaaS with WorkOS:</strong> Tenants are derived from WorkOS
            organization IDs. Users in the same WorkOS organization share a
            tenant.
          </li>
          <li>
            <strong>API key auth:</strong> The tenant is set via the{" "}
            <code className="bg-muted px-1 rounded font-mono text-xs">
              X-VigilWeave-Tenant
            </code>{" "}
            header.
          </li>
        </ul>
      </section>

      {/* API Keys */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">API Keys</h3>
        <p className="text-muted-foreground">
          API keys provide authentication for CI/CD pipelines, automation
          scripts, and headless integrations. They work alongside browser
          sessions — you can use both simultaneously.
        </p>
        <ul className="list-disc list-inside space-y-1 text-muted-foreground">
          <li>
            Generated from <strong>Settings &rarr; API Keys</strong>.
          </li>
          <li>
            Prefixed with{" "}
            <code className="bg-muted px-1 rounded font-mono text-xs">
              vw_
            </code>{" "}
            for identification.
          </li>
          <li>Stored as SHA-256 hashes — the raw key is shown once at creation.</li>
          <li>Scoped to the creating user&apos;s tenant.</li>
          <li>Can be revoked at any time from the Settings page.</li>
        </ul>
        <div className="code-block">
          <pre>{`# Use API key in CI/CD
curl -H "Authorization: Bearer vw_sk_live_abc123def456" \\
  -H "X-VigilWeave-Tenant: my-org" \\
  https://app.vigilweave.com/api/v1/scans`}</pre>
        </div>
      </section>

      {/* Self-Hosted Enterprise */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">
          Self-Hosted Enterprise Auth
        </h3>
        <p className="text-muted-foreground">
          Enterprise self-hosted customers can choose between local auth and
          WorkOS SSO:
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border border-border rounded-sm overflow-hidden">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-4 py-2 font-semibold text-foreground">
                  Option
                </th>
                <th className="text-left px-4 py-2 font-semibold text-foreground">
                  Config
                </th>
                <th className="text-left px-4 py-2 font-semibold text-foreground">
                  Best For
                </th>
              </tr>
            </thead>
            <tbody className="text-muted-foreground divide-y divide-border">
              <tr>
                <td className="px-4 py-2 font-medium text-foreground">
                  Local users only
                </td>
                <td className="px-4 py-2 font-mono text-xs">
                  SESSION_AUTH_PROVIDER=local
                </td>
                <td className="px-4 py-2">
                  Air-gapped environments, small teams, no external IdP
                </td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-medium text-foreground">
                  WorkOS SSO
                </td>
                <td className="px-4 py-2 font-mono text-xs">
                  SESSION_AUTH_PROVIDER=workos
                </td>
                <td className="px-4 py-2">
                  Teams with existing IdP (Azure AD, Okta), compliance
                  requirements
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="text-sm text-muted-foreground">
          Self-hosted Enterprise with WorkOS requires a WorkOS account and API
          credentials. See the{" "}
          <strong>Self-Hosting &rarr; Commercial Deployment</strong> section for
          the required environment variables.
        </p>
      </section>
    </div>
  );
}
