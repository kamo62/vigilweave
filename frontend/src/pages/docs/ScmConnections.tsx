export function ScmConnections() {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-foreground mb-2">
          SCM Connections
        </h2>
        <p className="text-muted-foreground">
          Connect VigilWeave to your source code management platforms to scan
          private repositories. VigilWeave supports GitHub, GitLab, Bitbucket,
          and Azure DevOps via personal access tokens (PATs).
        </p>
      </div>

      {/* Supported Providers */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">
          Supported Providers
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border border-border rounded-sm overflow-hidden">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-4 py-2 font-semibold text-foreground">
                  Provider
                </th>
                <th className="text-left px-4 py-2 font-semibold text-foreground">
                  Auth Method
                </th>
                <th className="text-left px-4 py-2 font-semibold text-foreground">
                  Required Token Scopes
                </th>
              </tr>
            </thead>
            <tbody className="text-muted-foreground divide-y divide-border">
              <tr>
                <td className="px-4 py-2 font-medium text-foreground">
                  GitHub
                </td>
                <td className="px-4 py-2">Personal Access Token (classic or fine-grained)</td>
                <td className="px-4 py-2">
                  <code className="bg-muted px-1 rounded font-mono text-xs">repo</code>{" "}
                  (full control of private repositories)
                </td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-medium text-foreground">
                  GitLab
                </td>
                <td className="px-4 py-2">Personal Access Token</td>
                <td className="px-4 py-2">
                  <code className="bg-muted px-1 rounded font-mono text-xs">read_api</code>,{" "}
                  <code className="bg-muted px-1 rounded font-mono text-xs">read_repository</code>
                </td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-medium text-foreground">
                  Bitbucket
                </td>
                <td className="px-4 py-2">App Password</td>
                <td className="px-4 py-2">
                  <code className="bg-muted px-1 rounded font-mono text-xs">repository:read</code>,{" "}
                  <code className="bg-muted px-1 rounded font-mono text-xs">project:read</code>
                </td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-medium text-foreground">
                  Azure DevOps
                </td>
                <td className="px-4 py-2">Personal Access Token</td>
                <td className="px-4 py-2">
                  <code className="bg-muted px-1 rounded font-mono text-xs">Code (Read)</code>,{" "}
                  <code className="bg-muted px-1 rounded font-mono text-xs">Project and Team (Read)</code>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Setting Up a Connection */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">
          Setting Up a Connection
        </h3>
        <ol className="list-decimal list-inside space-y-2 text-muted-foreground">
          <li>
            Navigate to{" "}
            <a
              href="/settings?tab=connections"
              className="text-primary underline underline-offset-2"
            >
              Settings &rarr; Connections
            </a>
            .
          </li>
          <li>
            Click <strong>Add Connection</strong>.
          </li>
          <li>
            Select the SCM provider (GitHub, GitLab, Bitbucket, or Azure
            DevOps).
          </li>
          <li>
            Enter a descriptive <strong>name</strong> for the connection (e.g.,
            &ldquo;GitHub Org - MyCompany&rdquo;).
          </li>
          <li>
            Paste your personal access token. For <strong>Bitbucket</strong>,
            also enter your Bitbucket username. For{" "}
            <strong>Azure DevOps</strong>, enter your organization name.
          </li>
          <li>
            Optionally, set a custom <strong>Base URL</strong> for self-hosted
            instances (e.g., GitHub Enterprise Server or GitLab self-managed).
          </li>
          <li>
            Click <strong>Save</strong>. VigilWeave encrypts and stores your
            token at rest.
          </li>
        </ol>
        <div className="rounded-sm border border-border p-4 space-y-1">
          <h4 className="font-semibold text-foreground text-sm">
            Token Security
          </h4>
          <p className="text-sm text-muted-foreground">
            Tokens are encrypted using Fernet symmetric encryption derived from
            your instance&rsquo;s{" "}
            <code className="bg-muted px-1.5 py-0.5 rounded font-mono text-xs">
              SESSION_SECRET
            </code>
            . Tokens are never stored in plaintext and are never logged or
            exposed in API responses &mdash; only a masked version is shown.
          </p>
        </div>
      </section>

      {/* Testing a Connection */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">
          Testing a Connection
        </h3>
        <p className="text-muted-foreground">
          After creating a connection, click the <strong>Test</strong> button in
          the connections list. VigilWeave will verify that the token is valid
          and has the required permissions by making an authenticated API call
          to the provider.
        </p>
      </section>

      {/* Importing Repositories */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">
          Importing Repositories
        </h3>
        <ol className="list-decimal list-inside space-y-2 text-muted-foreground">
          <li>
            Navigate to{" "}
            <a
              href="/projects"
              className="text-primary underline underline-offset-2"
            >
              Projects
            </a>{" "}
            and click <strong>Create Project</strong>.
          </li>
          <li>
            Switch to the <strong>Import from SCM</strong> tab.
          </li>
          <li>
            Select an existing connection from the dropdown.
          </li>
          <li>
            Choose an <strong>organization</strong> (GitHub) or{" "}
            <strong>group</strong> (GitLab) or <strong>workspace</strong>{" "}
            (Bitbucket) or <strong>project</strong> (Azure DevOps).
          </li>
          <li>
            Browse the repository list and select the repositories to import.
          </li>
          <li>
            Click <strong>Import Selected</strong>. VigilWeave creates a project
            for each selected repository and links it to the SCM connection for
            authenticated cloning.
          </li>
        </ol>
      </section>

      {/* API */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">
          API Reference
        </h3>
        <div className="code-block">
          <pre>{`# List connections
curl -H "Authorization: Bearer YOUR_API_KEY_HERE" \\
  http://localhost:8000/api/v1/scm-connections

# Create a connection
curl -X POST http://localhost:8000/api/v1/scm-connections \\
  -H "Authorization: Bearer YOUR_API_KEY_HERE" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "GitHub - MyOrg",
    "provider": "github",
    "token": "YOUR_SCM_TOKEN_HERE"
  }'

# Test a connection
curl -X POST http://localhost:8000/api/v1/scm-connections/1/test \\
  -H "Authorization: Bearer YOUR_API_KEY_HERE"

# List organizations for a connection
curl -H "Authorization: Bearer YOUR_API_KEY_HERE" \\
  http://localhost:8000/api/v1/scm-connections/1/organizations

# List repositories for an organization
curl -H "Authorization: Bearer YOUR_API_KEY_HERE" \\
  "http://localhost:8000/api/v1/scm-connections/1/repositories?org=my-org"

# Import repositories
curl -X POST http://localhost:8000/api/v1/scm-connections/1/import \\
  -H "Authorization: Bearer YOUR_API_KEY_HERE" \\
  -H "Content-Type: application/json" \\
  -d '{
    "repos": [
      { "name": "api-service", "clone_url": "https://github.com/my-org/api-service.git" },
      { "name": "web-app", "clone_url": "https://github.com/my-org/web-app.git" }
    ]
  }'`}</pre>
        </div>
      </section>
    </div>
  );
}
