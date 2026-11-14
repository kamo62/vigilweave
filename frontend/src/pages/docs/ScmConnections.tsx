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
          and Azure DevOps. Authentication and discovery support vary by provider;
          a successful connection test does not establish repository or clone access.
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
                  for classic PATs, plus read:org for organisation discovery.
                  Fine-grained PATs need selected repositories, Metadata read and Contents read.
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
                <td className="px-4 py-2">API token compatibility requires follow-up</td>
                <td className="px-4 py-2">
                  Current API tokens use read:user:bitbucket, read:workspace:bitbucket
                  and read:repository:bitbucket. App passwords are retired. The client
                  currently shares one REST/Git identity and uses a legacy workspace endpoint.
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
            the current shared REST/Git identity field has API-token compatibility
            limitations. Verify REST access and Git cloning separately. For{" "}
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
            Stored tokens use Fernet encryption derived from{" "}
            <code className="bg-muted px-1.5 py-0.5 rounded font-mono text-xs">
              TOKEN_ENCRYPTION_KEY
            </code>
            , with session-secret fallbacks. Public connection responses show a
            masked token. Git cloning still uses transient plaintext credentials
            in subprocess arguments and the temporary checkout configuration.
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
          the connections list. VigilWeave makes one identity request, or an Azure
          project-list request. Repository discovery, SSO approval and Git clone
          permissions must be verified separately.
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
            Create the project with the selected repositories. The project links
            retain the SCM connection for later authenticated scans.
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
    "base_url": "https://api.github.com",
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
curl -X POST http://localhost:8000/api/v1/scm-connections/1/import-repos \\
  -H "Authorization: Bearer YOUR_API_KEY_HERE" \\
  -H "Content-Type: application/json" \\
  -d '{
    "project_key": "example-project",
    "repos": ["https://github.com/my-org/api-service.git"]
  }'`}</pre>
        </div>
      </section>
    </div>
  );
}
