# VigilWeave Azure DevOps Task

This package provides a Node 20 Azure Pipelines task that:

- creates and polls a VigilWeave scan
- normalizes severity values before policy evaluation
- writes JSON summary and SARIF outputs
- prepares SARIF for `AdvancedSecurity-Publish@1`
- updates a PR summary comment in place when `System.AccessToken` is available

Build with `bun run build` and package with `tfx extension create`.
