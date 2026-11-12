export function Webhooks() {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-foreground mb-2">Webhooks</h2>
        <p className="text-muted-foreground">
          VigilWeave can receive webhook events from your SCM providers to
          automatically trigger scans when code changes are pushed or pull
          requests are opened.
        </p>
      </div>

      {/* Supported Events */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">
          Supported Events
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border border-border rounded-sm overflow-hidden">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-4 py-2 font-semibold text-foreground">
                  Provider
                </th>
                <th className="text-left px-4 py-2 font-semibold text-foreground">
                  Event
                </th>
                <th className="text-left px-4 py-2 font-semibold text-foreground">
                  Action
                </th>
              </tr>
            </thead>
            <tbody className="text-muted-foreground divide-y divide-border">
              <tr>
                <td className="px-4 py-2 font-medium text-foreground">
                  GitHub
                </td>
                <td className="px-4 py-2">
                  <code className="bg-muted px-1 rounded font-mono text-xs">
                    push
                  </code>
                  ,{" "}
                  <code className="bg-muted px-1 rounded font-mono text-xs">
                    pull_request
                  </code>
                </td>
                <td className="px-4 py-2">
                  Triggers a comprehensive scan on the pushed commit or PR head
                </td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-medium text-foreground">
                  Azure DevOps
                </td>
                <td className="px-4 py-2">
                  <code className="bg-muted px-1 rounded font-mono text-xs">
                    git.push
                  </code>
                  ,{" "}
                  <code className="bg-muted px-1 rounded font-mono text-xs">
                    git.pullrequest.created
                  </code>
                </td>
                <td className="px-4 py-2">
                  Triggers a scan for the repository and branch
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Configuration */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">
          Configuring Webhooks
        </h3>

        <div className="space-y-2">
          <h4 className="font-semibold text-foreground text-sm">
            GitHub Webhooks
          </h4>
          <ol className="list-decimal list-inside space-y-1 text-sm text-muted-foreground">
            <li>
              In your GitHub repository, go to{" "}
              <strong>Settings &rarr; Webhooks &rarr; Add webhook</strong>.
            </li>
            <li>
              Set the Payload URL to{" "}
              <code className="bg-muted px-1.5 py-0.5 rounded font-mono text-xs">
                https://your-instance.example.com/api/v1/webhooks/github
              </code>
            </li>
            <li>
              Set Content type to{" "}
              <code className="bg-muted px-1 rounded font-mono text-xs">
                application/json
              </code>
              .
            </li>
            <li>
              Select events: <strong>Push</strong> and{" "}
              <strong>Pull requests</strong>.
            </li>
            <li>Click <strong>Add webhook</strong>.</li>
          </ol>
        </div>

        <div className="space-y-2">
          <h4 className="font-semibold text-foreground text-sm">
            Azure DevOps Service Hooks
          </h4>
          <ol className="list-decimal list-inside space-y-1 text-sm text-muted-foreground">
            <li>
              In your Azure DevOps project, go to{" "}
              <strong>Project Settings &rarr; Service hooks</strong>.
            </li>
            <li>
              Create a new subscription with <strong>Web Hooks</strong> as the
              service.
            </li>
            <li>
              Set the URL to{" "}
              <code className="bg-muted px-1.5 py-0.5 rounded font-mono text-xs">
                https://your-instance.example.com/api/v1/webhooks/azure-devops
              </code>
            </li>
            <li>
              Select the <strong>Code pushed</strong> or{" "}
              <strong>Pull request created</strong> trigger.
            </li>
          </ol>
        </div>
      </section>

      {/* Webhook Payload */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">
          How It Works
        </h3>
        <p className="text-muted-foreground">
          When VigilWeave receives a webhook event, it:
        </p>
        <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
          <li>
            Validates the payload signature (GitHub) or verifies the source
            (Azure DevOps).
          </li>
          <li>
            Extracts the repository URL, branch, and commit SHA from the event.
          </li>
          <li>
            Looks up matching projects in VigilWeave by repository URL.
          </li>
          <li>
            Queues a comprehensive scan for each matching project using the
            provided commit reference.
          </li>
          <li>
            For pull request events, posts scan results back as a PR comment
            (if configured).
          </li>
        </ol>
      </section>
    </div>
  );
}
