# SCM providers API reference

Research date: 2026-11-14. Source baseline: working tree based on `093de62`, including the concurrent SCM credential-binding changes reviewed for this document. This is a source and official-documentation reference, not evidence of a running deployment or successful access to a vendor account. All examples are synthetic.

Transport and webhook sections updated from the current working tree on 2026-11-15.
Synthetic Git and webhook contract checks were run; no live provider credentials were used.

## Scope and evidence

The labels IMPLEMENTED, PROVIDER CAPABILITY and KNOWN GAP distinguish application behaviour from vendor features. A vendor accepting a credential type does not establish that VigilWeave implements its onboarding, renewal or every endpoint needed for discovery.

Primary application sources:

| Area | Current source |
| --- | --- |
| Provider requests, pagination and authenticated URLs | [scm_providers.py](../app/services/scm_providers.py) |
| Stored connection contract | [scm_connection.py](../app/models/scm_connection.py) |
| Connection routes and base-URL policy | [scm_connections.py](../app/api/scm_connections.py) |
| Runtime credential selection | [scm_clone.py](../app/services/scm_clone.py) |
| GitHub App requests and webhook scan creation | [github_app.py](../app/services/github_app.py) |
| GitHub App onboarding, tenant links and reassignment | [integrations.py](../app/api/integrations.py), [integration models](../app/models/integration.py) |
| Project repository links and scan association | [projects.py](../app/api/projects.py), [project models](../app/models/project.py), [scans.py](../app/api/scans.py), [project_mapping.py](../app/services/project_mapping.py) |
| Encryption, authentication and network checks | [token_encryption.py](../app/core/token_encryption.py), [security.py](../app/core/security.py), [network_security.py](../app/core/network_security.py), [configuration](../app/core/config.py) |
| Clone execution and failure handling | [git_utils.py](../app/services/git_utils.py), [scanner.py](../app/services/scanner.py) |
| Browser form and repository selection | [SCMConnectionForm.tsx](../frontend/src/components/SCMConnectionForm.tsx), [SCMRepoPicker.tsx](../frontend/src/components/SCMRepoPicker.tsx), [ProjectsPage.tsx](../frontend/src/pages/ProjectsPage.tsx), [API client](../frontend/src/lib/api.ts) |
| Existing source-level regression evidence | [test_scm_connections_api.py](../tests/test_scm_connections_api.py), [test_reference_review_security.py](../tests/test_reference_review_security.py), [test_devops_integrations_api.py](../tests/test_devops_integrations_api.py) |

The [in-app SCM help](../frontend/src/pages/docs/ScmConnections.tsx) summarises setup and provider limitations. Its examples now include required `base_url`, the implemented `/import-repos` route and a target `project_key`. The detailed contracts and remaining compatibility gaps are described below.

## Permission and paging summary

The permissions below describe the provider requirements for the operations used here. Token scope, the identity's actual membership, resource selection and organisation policy all constrain access.

| Provider / flow | IMPLEMENTED authentication | Discovery and clone permissions | IMPLEMENTED pagination and stopping rule |
| --- | --- | --- | --- |
| GitHub token | `Authorization: Bearer TOKEN`; REST version `2026-03-10` | Classic PAT: `repo` for private repositories, plus `read:org` or `user` for `/user/orgs`. Fine-grained PAT: selected owner/repositories, Metadata read for repository listing, Contents read for cloning; organisation approval and SSO restrictions apply. | Organisations and repositories: `per_page=100`, increment `page`; stop on an empty or shorter-than-100 array. Does not read `Link`. |
| GitHub App | App JWT, then installation access token; REST version `2022-11-28` | Installation repository selection; Contents read for Git; Checks write for check runs. Separate app configuration, not a PAT form mode. | One `/installation/repositories?per_page=100` request. No next-page traversal. |
| GitLab | `PRIVATE-TOKEN: TOKEN`; REST `/api/v4` | PAT `read_api` plus `read_repository` for read-only discovery and HTTPS cloning; `api` is a broader alternative that also permits repository access. | Groups and projects: `per_page=100`, increment `page`; stop on empty or shorter-than-100 array. Ignores pagination headers and keyset pagination. |
| Bitbucket Cloud | HTTP Basic using `extra_config.username` and `token` for REST and Git | Current API-token scopes: `read:user:bitbucket`, `read:workspace:bitbucket`, `read:repository:bitbucket` for the corresponding current operations. REST Basic requires Atlassian email; Git supports Bitbucket username or documented static usernames. Current shared identity handling is a gap. | Start with `pagelen=100`; repositories also use `role=member`. Follow validated absolute JSON `next` URLs with their own query; stop when `next` is absent/null. Reject repeated URLs. Legacy workspace endpoint needs migration. |
| Azure DevOps | PAT in HTTP Basic `("", TOKEN)` for REST; `pat:TOKEN` for Git; `api-version=7.1` | Code (Read), `vso.code`; Project and Team (Read), `vso.project`, for project discovery. User also needs repository Read access. | Projects: `$top=100`, follow `x-ms-continuationtoken` as `continuationToken`; stop when token missing/empty or `value` empty. Repositories: one request per selected project. |

Official permission references: [GitHub organisation listing](https://docs.github.com/en/rest/orgs/orgs#list-organizations-for-the-authenticated-user), [GitHub repository listing](https://docs.github.com/en/rest/repos/repos#list-repositories-for-the-authenticated-user), [GitHub PATs](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens), [GitHub installation Git authentication](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation), [GitLab scopes](https://docs.gitlab.com/security/tokens/access_token_scopes/), [Bitbucket current user](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-users/), [Bitbucket workspaces](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-workspaces/), [Bitbucket repositories](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-repositories/), [Azure projects](https://learn.microsoft.com/en-us/rest/api/azure/devops/core/projects/list?view=azure-devops-rest-7.1), [Azure repositories](https://learn.microsoft.com/en-us/rest/api/azure/devops/git/repositories/list?view=azure-devops-rest-7.1).

## Connection model, storage and runtime use

### IMPLEMENTED credential contract

`SCMConnectionCreate` requires `name`, `provider`, `base_url` and plaintext `token`; `extra_config` is optional. Provider enum values are `github`, `gitlab`, `bitbucket` and `azure_devops`. There is one encrypted token per connection. There are no top-level username/email, authentication-mode, OAuth client ID, client secret, refresh token or expiry fields.

The current source does have an untyped `extra_config` dictionary. Bitbucket reads `extra_config.username`, and Azure reads `extra_config.organization`. The browser form collects these two values conditionally. Therefore, “token only” describes the dedicated secret field, not an absence of every identity/configuration value. There is no separate Bitbucket REST email and Git username contract. The form labels the secret “Personal Access Token” for every provider; that label does not make all token families interchangeable.

`PATCH` accepts optional `name`, `base_url`, `token`, `extra_config` and `is_active`; it cannot change provider. Supplying `extra_config` replaces the dictionary rather than merging it. Omitted/null values do not clear existing fields. Creation stores the connection without contacting the provider. The schemas do not enforce a non-empty token, provider-specific required configuration or token type; the browser only requires a non-blank name and token.

### IMPLEMENTED encryption and isolation

The tenant and creator come from the authenticated principal. The server encrypts the token with Fernet using a key derived from SHA-256 of the configured secret, encoded for Fernet. Key precedence is `TOKEN_ENCRYPTION_KEY`, then `SESSION_SECRET`, then `WORKOS_SESSION_SECRET`. No configured key raises `TokenEncryptionError`; an incompatible key produces a decryption failure. API and worker processes must use the same key and database. There is no per-tenant encryption key or built-in key migration/rotation process.

Public responses expose `token_masked`, not ciphertext or plaintext token: `****` for tokens of at most eight characters, otherwise the first four and last four characters around `****`. `extra_config` is stored as JSON and returned to administrators without this encryption, so it must not contain additional secrets.

At runtime, the worker resolves the connection ID recorded in scan metadata, verifies that the connection exists, is active and belongs to the scan tenant, validates the clone destination with an empty credential, then decrypts the current token. Rotation affects queued scans when they execute. A missing, foreign-tenant or inactive connection fails the scan instead of silently retrying anonymously. `is_active` is enforced by clone resolution; the test, discovery and dedicated import routes do not currently reject inactive connections.

The provider resolver constructs an authenticated HTTPS URL internally. The Git boundary strips its userinfo and passes a transient Basic header through repository-scoped `GIT_CONFIG_*` environment entries. Git arguments and the saved remote URL omit credentials; system/global Git configuration, credential helpers, prompts, hooks and redirects are disabled. Clones materialise symlinks as plain files. Error/log helpers provide best-effort redaction. The Git process still receives plaintext credentials in its environment, so this does not isolate credentials from the worker user or privileged host processes. Do not print the authenticated URL or place it in repository inventory. Source: [clone resolution](../app/services/scm_clone.py), [Git invocation](../app/services/git_utils.py), [scan failure handling](../app/services/scanner.py).

### IMPLEMENTED destination checks and deployment limits

Connection create/update trims surrounding whitespace and trailing slashes, requires HTTPS, and rejects credentials, queries, fragments, backslashes, control characters and malformed ports in `base_url`. Default host allowlists are:

| Provider | Allowed host patterns |
| --- | --- |
| GitHub | `api.github.com`, `*.ghe.com`, `*.github.example.com` |
| GitLab | `gitlab.com`, `*.gitlab.com`, `*.gitlab.example.com` |
| Bitbucket | `api.bitbucket.org` |
| Azure | `dev.azure.com`, `*.dev.azure.com`, `*.visualstudio.com` |

`ALLOW_PRIVATE_SCM_BASE_URLS=true` bypasses the provider host list only for hosts the syntax-based helper recognises as private, such as private IPs or `.internal`/`.local` names. Other blocks, including loopback and metadata destinations, still apply. This is not arbitrary custom-host support or DNS-resolution enforcement. The generic Git clone check independently rejects private addresses by syntax, so an accepted private API base does not establish end-to-end private cloning. See [network policy](../app/core/network_security.py).

Authenticated clone validation requires the expected HTTPS hostname and effective port, rejects queries/fragments and existing passwords, and checks repeatedly decoded paths for `.`/`..` segments and backslashes. A provider-returned username-only URL is parsed and its username replaced. GitHub Cloud maps API host `api.github.com` to clone host `github.com`; Bitbucket maps `api.bitbucket.org` to `bitbucket.org`. Other bases use their configured origin. GitLab also enforces its configured deployment path prefix; Azure enforces the base path plus configured organisation.

These checks bind credentials to an origin/deployment scope. They do not prove repository ownership, repository-level permission or membership of a provider discovery result. Provider HTTP calls do not explicitly enable redirects; Git HTTP redirects are disabled. Network/DNS enforcement still requires separate assessment.

## Application API contract

Paths below use the default `/api/v1` prefix. An installation can override `API_V1_PREFIX`. A VigilWeave API key/session authorises these routes; the SCM token belongs in the connection body, not in VigilWeave's `Authorization` header.

### IMPLEMENTED route authorisation and responses

Every route in the following table requires `admin`. The shared authentication layer supports configured local/WorkOS browser sessions and enabled API keys supplied as `Authorization: Bearer YOUR_VIGILWEAVE_API_KEY_HERE` or `X-API-Key`. Tenant headers must agree with the authenticated identity. The deliberately configured development bootstrap can grant admin before any API key exists when session auth is `none`; that is not a provider authentication mechanism. See [security.py](../app/core/security.py).

| Method and path under `/api/v1/scm-connections` | Input | Successful response |
| --- | --- | --- |
| `POST /` | Create body | `201`, `SCMConnectionPublic` |
| `GET /` | None | `200`, array of tenant connections, including inactive ones |
| `GET /{id}` | Connection ID | `200`, `SCMConnectionPublic` |
| `PATCH /{id}` | Update body | `200`, `SCMConnectionPublic` |
| `DELETE /{id}` | Connection ID | `204`, no body; `409` if project repositories still link to it |
| `POST /{id}/test` | No body | `200`, `{ "ok": boolean, "message": string, "username": string_or_null }`; persists test time/result |
| `GET /{id}/organizations` | None | `200`, `SCMOrganization[]`; meaning varies by provider |
| `GET /{id}/repositories?org=...` | Group selector; default empty string | `200`, `SCMRepository[]` |
| `POST /{id}/import-repos` | `{ "project_key": string, "repos": string[] }` | `200`, `{ "imported": number, "skipped": number }` |

`SCMConnectionPublic` contains `id`, `tenant_slug`, `name`, `provider`, `base_url`, `token_masked`, `extra_config`, `is_active`, `last_tested_at`, `last_test_ok`, `created_at`, `updated_at` and `created_by`. Dates are serialised timestamps; test fields and creator can be null.

`SCMOrganization` is `{id: string, name: string, avatar_url: string|null}`. `SCMRepository` has string `id`, `name`, `full_name`, `clone_url`; nullable `default_branch`, `description`, `language`, `updated_at`; and boolean `is_private`. These are normalised summaries, not complete vendor responses. GitLab leaves language unset and considers only `visibility=private` private, so internal projects appear `is_private=false`; Azure currently reports every repository as private and uses project description. Do not treat this field as an access-control decision.

Discovery traverses the provider pages synchronously within one application request and returns a single array. The application API does not return its own cursor, completeness flag or partial-result envelope.

The test, organisation listing, repository listing and import routes use the application's authentication-endpoint rate limiter. It keys requests by client IP and request path, returns `429` with `Retry-After` and `X-RateLimit-*`, and is independent of provider quotas. See [rate_limiter.py](../app/core/rate_limiter.py).

Missing/foreign-tenant connection IDs return `404`; unauthenticated requests return `401`; insufficient scope or tenant mismatch returns `403`; invalid base URLs/schema payloads return `422`. Missing target projects return `404`. Provider test methods catch HTTP errors and return `ok=false` with the vendor status in the message; other connection exceptions also become a failed test message. Decryption/factory failures occur outside those methods. Discovery methods call `raise_for_status()` without route-specific translation, so a provider `401`, `403`, `404`, `429` or network error is not guaranteed to be forwarded as the same application status/shape. There is no retry/backoff or rate-header propagation in these clients.

### Synthetic request/response flow

The following is an HTTP contract illustration, not a command to execute:

```http
POST /api/v1/scm-connections/
Authorization: Bearer YOUR_VIGILWEAVE_API_KEY_HERE
Content-Type: application/json

{
  "name": "Example GitHub read access",
  "provider": "github",
  "base_url": "https://api.github.com",
  "token": "YOUR_SCM_TOKEN_HERE",
  "extra_config": null
}
```

A successful create returns `201` with the public connection fields, for example `id=42`, `is_active=true`, `last_tested_at=null`, `last_test_ok=null` and a masked token. It does not establish authentication yet.

```text
Admin creates connection -> API validates base URL -> encrypts token -> tenant record
Admin tests connection -> decrypts token -> vendor identity/project endpoint -> stored test result
Admin lists groups/repos -> vendor pages -> normalised arrays -> repository picker
Admin links selected clone URLs to a project -> ProjectRepository credential-source IDs
Caller creates scan with project_key + exact repo URL -> scan stores selected credential IDs
Worker validates tenant + destination -> decrypts/mints current token -> HTTPS Git clone -> scan
```

Examples of subsequent responses and bodies:

```json
{"ok": true, "message": "Authenticated as example-user", "username": "example-user"}
```

```http
GET /api/v1/scm-connections/42/repositories?org=_user
```

```json
[
  {
    "id": "123",
    "name": "example-service",
    "full_name": "example-org/example-service",
    "clone_url": "https://github.com/example-org/example-service.git",
    "default_branch": "main",
    "description": null,
    "language": null,
    "is_private": true,
    "updated_at": null
  }
]
```

```http
POST /api/v1/scm-connections/42/import-repos
Content-Type: application/json

{"project_key": "example-project", "repos": ["https://github.com/example-org/example-service.git"]}
```

```json
{"imported": 1, "skipped": 0}
```

The import route adds links to an existing tenant project, not new projects, does not clone, and does not call provider discovery. It accepts supplied strings, skips URLs already stored, and does not reassign their credential source. Its initial existing-URL set is not updated during iteration, so repeated new URLs in one request can create duplicate rows/counts. Treat imported URLs as input awaiting runtime destination validation, not certified provider repository IDs.

## GitHub token connection

### IMPLEMENTED requests and discovery

Default base is `https://api.github.com`. Headers are Bearer token, `Accept: application/vnd.github+json` and `X-GitHub-Api-Version: 2026-03-10`. All token-provider HTTP requests use a 15-second timeout per request; there is no total discovery timeout or page ceiling.

| Operation | Request relative to base | Meaning |
| --- | --- | --- |
| Test | `GET /user` | Reads `login`; proves this identity endpoint worked |
| Organisations | `GET /user/orgs?per_page=100&page=N` | Membership discovery permitted by the credential |
| “My Repositories” | `GET /user/repos` with `visibility=all`, `affiliation=owner,collaborator,organization_member`, `sort=updated`, `per_page=100`, `page=N` | Used for empty `org` or `_user`; includes accessible organisational/collaborator repositories, not just personally owned repositories |
| Selected organisation | `GET /orgs/{encoded_org}/repos` with `type=all`, `sort=updated`, `per_page=100`, `page=N` | Organisation repositories visible to this token |

PROVIDER CAPABILITY: organisation listing with a classic PAT requires at least `read:org` or `user`. GitHub explicitly documents a successful empty array for fine-grained tokens on `/user/orgs`. This is a discovery limitation, not proof of an invalid fine-grained token. “My Repositories” can still be useful, or the API caller can supply a known organisation. Source: [authenticated organisation endpoint](https://docs.github.com/en/rest/orgs/orgs#list-organizations-for-the-authenticated-user).

Fine-grained repository listing requires Metadata read; clone access additionally needs Contents read and the intended repositories selected under the correct resource owner. A classic `repo` token is broader. Organisation approval, token restrictions and SAML SSO can prevent access even when `/user` succeeds. Classic PATs may need explicit SSO authorisation; fine-grained tokens are authorised during creation. Without classic-token authorisation, organisation results can be partial, indicated by `X-GitHub-SSO`. Sources: [repository endpoints](https://docs.github.com/en/rest/repos/repos), [PAT selection and approval](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens), [REST authentication and SSO](https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api).

IMPLEMENTED paging uses array length, not GitHub's `Link` contract. An exact multiple of 100 triggers a final empty-page request. Updates while traversing `sort=updated` can change page membership; the client does not deduplicate or provide a consistent snapshot. It does not follow arbitrary server next URLs. Vendor reference: [REST pagination](https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api).

Clone credentials have the form `https://x-access-token:YOUR_ENCODED_SCM_TOKEN_HERE@github.com/example-org/example-service.git`. The stored clone URL must remain credential-free. KNOWN GAP: no GitHub installation-token mode in the PAT connection model; installation tokens belong to the separate flow below.

### Self-hosted variants and errors

For GitHub Enterprise Server, the vendor REST base includes `/api/v3`; configure that full API prefix rather than only the web root. Clone validation uses the same origin without requiring `/api/v3` in repository paths. The application host allowlist and fixed REST version still apply; arbitrary enterprise domains and older server-version compatibility are not automatically supported. GitHub Enterprise Cloud data-residency deployments can have different API and clone subdomains; the client only has the explicit `api.github.com` to `github.com` mapping. Source: [GitHub Enterprise Server REST base](https://docs.github.com/en/enterprise-server@3.22/rest/using-the-rest-api/getting-started-with-the-rest-api).

A `401` commonly indicates an invalid/expired credential; `403` can indicate scope, organisation policy, SSO or throttling; private-resource `404` can conceal missing access. GitHub uses `403`/`429` for rate limits, with `x-ratelimit-remaining`, `x-ratelimit-reset` and sometimes `Retry-After`. The common authenticated user quota is 5,000 requests/hour, with other limits depending on identity and enterprise context. VigilWeave does not inspect these headers or delay requests. Source: [GitHub rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api).

## GitLab connection

IMPLEMENTED default base is `https://gitlab.com`, with `/api/v4` appended by the client and `PRIVATE-TOKEN` authentication. For a supported self-managed deployment prefix, use a base such as `https://gitlab.example.com/gitlab`, not one ending in `/api/v4`; the latter would duplicate the API path. Host acceptance remains subject to application policy. Sources: [REST root and encoding](https://docs.gitlab.com/api/rest/), [PAT HTTPS authentication](https://docs.gitlab.com/user/profile/personal_access_tokens/).

| Operation | Request relative to base | Filters and limits |
| --- | --- | --- |
| Test | `GET /api/v4/user` | Reads `username` only |
| Groups | `GET /api/v4/groups` | `min_access_level=10`, `top_level_only=true`, `per_page=100`, `page=N` |
| “My Repositories” | `GET /api/v4/projects` | Empty `org` or `_user`; `membership=true`, `order_by=last_activity_at`, `sort=desc`, page size 100 |
| Group repositories | `GET /api/v4/groups/{encoded_group}/projects` | Same sort/page parameters; no `include_subgroups` override |

The group list filters out non-top-level groups. GitLab's group-project endpoint defaults to `include_subgroups=false` and `with_shared=true`; VigilWeave does not recursively discover subgroups or override these defaults. A known subgroup path can be supplied through the API, while `_user` lists membership projects across namespaces. Sources: [Groups API](https://docs.gitlab.com/api/groups/), [Projects API](https://docs.gitlab.com/api/projects/).

PROVIDER CAPABILITY: PATs with `read_api` can perform read-only API discovery; `read_repository` grants Git pull access but does not replace general API-read scope. Use both for this read-only flow. `api` is a broader read/write alternative and also grants Git-over-HTTPS repository access. GitLab supports group/project tokens with narrower resource reach, but there is no dedicated token-family selector here or live validation of every discovery operation for those bot identities. Deploy tokens, CI job tokens and OAuth refresh are not implemented connection modes. Source: [access-token scope definitions](https://docs.gitlab.com/security/tokens/access_token_scopes/).

IMPLEMENTED cloning uses `oauth2` as a fixed non-blank username and the token as password. GitLab PAT HTTPS authentication accepts a non-blank username; the literal `oauth2` does not imply an implemented OAuth exchange. Clone URLs must stay within the configured deployment prefix.

IMPLEMENTED paging increments offset pages until empty/short, ignoring `Link`, `X-Next-Page` and `X-Total-Pages`. GitLab documents a maximum offset and keyset support for selected endpoints, so large inventories may fail rather than complete; no keyset fallback exists. Group paths such as `example-group/platform` are encoded once as a single path parameter (`example-group%2Fplatform`). Reverse proxies must preserve encoded slashes. Source: [GitLab REST pagination and encoding](https://docs.gitlab.com/api/rest/).

For `401`/`403`, check validity, scopes and membership separately; `404` can mean inaccessible resource or a path/encoding problem. GitLab returns `429` with retry guidance; limits depend on endpoint and instance configuration. VigilWeave does not retry or consume that guidance. Source: [GitLab REST troubleshooting](https://docs.gitlab.com/api/rest/troubleshooting/).

## Bitbucket Cloud connection

### IMPLEMENTED baseline and current provider requirements

Default API base is `https://api.bitbucket.org`. The client unconditionally uses Basic authentication with `(extra_config.username or "", token)` for every REST request. It uses that same username for HTTPS cloning. No Bearer/API-token mode, email field, OAuth exchange, refresh process, or repository/project/workspace access-token mode is implemented.

| Operation | IMPLEMENTED request | Current documentation / gap |
| --- | --- | --- |
| Test | `GET /2.0/user` | Current-user scope for API tokens is `read:user:bitbucket`; success proves only this request |
| Workspaces | `GET /2.0/user/permissions/workspaces?pagelen=100` | Current reference documents `GET /2.0/user/workspaces` with `read:workspace:bitbucket`; migration is outstanding |
| Repositories | `GET /2.0/repositories/{encoded_workspace}?role=member&pagelen=100` | Workspace repository listing with `read:repository:bitbucket`; not a global personal repository inventory |
| Clone | First `links.clone` entry whose `name` is `https` | Replaces any returned username with `extra_config.username`; default clone origin is `https://bitbucket.org` |

Sources: [current user](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-users/), [current workspace discovery](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-workspaces/), [workspace repositories](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-repositories/).

PROVIDER CAPABILITY: current scoped API tokens support REST Basic authentication with the Atlassian account email and token. Current support documentation also describes API-token Bearer authentication without email. Git authentication accepts the case-sensitive Bitbucket username or static `x-bitbucket-api-token-auth` / `x-token-auth`, with the API token as password. VigilWeave currently implements neither Bearer mode nor separate REST/Git identity values. Entering a Bitbucket username satisfies the form's wording but is not the documented REST Basic email; entering the email makes REST Basic consistent with vendor guidance but is not a documented guarantee for this client's Git username. End-to-end API-token compatibility therefore remains a known gap. Sources: [REST authentication](https://developer.atlassian.com/cloud/bitbucket/rest/intro/#api-tokens), [API-token Git and REST usage](https://support.atlassian.com/bitbucket-cloud/docs/using-api-tokens/).

### App-password lifecycle and workspace migration

PROVIDER CAPABILITY / LIFECYCLE: new Bitbucket Cloud app passwords stopped being available on 9 September 2025. The original 9 June 2026 shutdown was revised to brownouts between 9 June and 28 July 2026, after which app passwords no longer work. At this research date they must be treated as retired. The form and in-app help now explain the current API-token compatibility gap. Atlassian's support page retains the original date in its summary and gives the revised schedule in its later note; this reference uses the revised schedule. Source: [Atlassian's updated migration note](https://support.atlassian.com/bamboo/kb/bitbucket-cloud-repository-configuration-fails-in-bamboo-with-api-tokens/).

KNOWN GAP: the implemented workspace discovery path is absent from the current workspace API reference. Atlassian also published a cross-workspace API end-of-life announcement, including guidance specific to Connect apps; those app-specific replacement tables must not be applied blindly to user API tokens. Migration should target the currently documented user workspace endpoint and confirm its response parser and scopes. Sources: [current workspace reference](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-workspaces/), [Atlassian cross-workspace end-of-life announcement](https://community.developer.atlassian.com/t/bitbucket-cloud-announcing-end-of-life-for-cross-workspace-apis-timeline-next-steps-and-instructions-for-connect-apps/99972).

### Pagination, errors and variants

IMPLEMENTED: the first request adds `pagelen=100`; repository discovery also adds `role=member`. Later requests use the `next` query exactly as returned, with no replacement params. A continuation must be an absolute HTTPS URL on the configured API hostname/effective port and below its `/2.0/` prefix; userinfo, fragments, traversal and repeated exact URLs are rejected before credentials are sent. A short or empty `values` page alone does not stop traversal while a valid `next` exists. Missing/null `next` stops it. An empty-string `next` fails URL validation. There is no page ceiling, and the validator allows another resource beneath the same API prefix, not only the original workspace endpoint.

The provider specifies opaque `next` links and does not guarantee `size`, `page` or `previous`; a short page is not a reliable final-page signal. This is why continuation parameters must not be rebuilt. Source: [Bitbucket pagination contract](https://developer.atlassian.com/cloud/bitbucket/rest/intro/#pagination).

`401` can result from wrong REST identity/token; `403` from scopes or permissions; a legacy-endpoint error may reflect migration rather than credentials. Account-level API tokens do not automatically gain access-token/Forge scaled quotas. Bitbucket documents resource-specific rolling-hour quotas and `X-RateLimit-*` headers for eligible requests. VigilWeave does not handle provider throttling beyond raising an HTTP error. Source: [API request limits](https://support.atlassian.com/bitbucket-cloud/docs/api-request-limits/).

Bitbucket Data Center is not Bitbucket Cloud API 2.0. The implementation and allowed base host are Cloud-specific; changing the URL does not provide a Data Center client.

## Azure DevOps connection

IMPLEMENTED default base is `https://dev.azure.com`; store the organisation separately as `extra_config.organization`, for example `example-org`. Do not include the organisation in both fields. The application calls REST with an empty Basic username and PAT password. The `org` query parameter in VigilWeave repository discovery means an Azure project, not the configured Azure organisation.

| Operation | Request | What it establishes |
| --- | --- | --- |
| Test | `GET {base}/{encoded_organisation}/_apis/projects?$top=1&api-version=7.1` | Projects endpoint accepted the credential, including when no projects are returned; `username` in the result is the configured organisation |
| “Organisations” | Same project endpoint with `stateFilter=wellFormed`, `$top=100`, optional `continuationToken`, `api-version=7.1` | Accessible projects within the single configured organisation |
| Project repositories | `GET {base}/{encoded_organisation}/{encoded_project}/_apis/git/repositories?api-version=7.1` | Repository summaries for that selected project |

PROVIDER CAPABILITY: project listing is governed by project visibility and Project and Team read permission (`vso.project`; the endpoint also documents `vso.profile`). Git repositories require Code read (`vso.code`) and the identity's repository permissions. A successful project-list test does not prove Code read or Git access. Sources: [Projects List 7.1](https://learn.microsoft.com/en-us/rest/api/azure/devops/core/projects/list?view=azure-devops-rest-7.1), [Repositories List 7.1](https://learn.microsoft.com/en-us/rest/api/azure/devops/git/repositories/list?view=azure-devops-rest-7.1).

IMPLEMENTED pagination keeps one project-list URL and passes the response `x-ms-continuationtoken` through the next request's `continuationToken` parameter. It stops when the token is absent/empty or the current `value` is empty, including a short non-empty page only if there is no token. It does not deduplicate projects, guard repeated tokens or bound page count. The repository-list API used here has no documented page/continuation parameters in its 7.1 contract; the application makes one request and does not include hidden repositories explicitly. Do not confuse the project pagination header with repository pagination support.

Azure DevOps Services supports up to 1,000 projects per organisation; Server supports up to 1,000 per collection. That service limit is distinct from `$top=100`, and does not justify stopping after the first page. Source: [Microsoft project limits](https://learn.microsoft.com/en-us/azure/devops/organizations/settings/work/object-limits?view=azure-devops#projects).

IMPLEMENTED HTTPS cloning uses `https://pat:YOUR_ENCODED_SCM_TOKEN_HERE@dev.azure.com/example-org/Example%20Project/_git/example-service`. Existing username-only provider URLs are replaced, not prepended. Clone validation requires the configured origin and organisation path. Organisation and project API parameters are percent-encoded as individual path components; the initial continuation token is supplied through HTTP query encoding rather than string concatenation.

PROVIDER CAPABILITY: Microsoft recommends Entra tokens, managed identities or service principals for integrations, and organisation-scoped PATs when a tool needs PATs. VigilWeave's connection model currently supports only the PAT path; it has no Entra client-credential, managed-identity or OAuth-refresh implementation. Current Microsoft documentation states global PATs retire on 27 January 2027. Source: [PAT authentication and lifecycle](https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops).

KNOWN GAP: allowing `*.visualstudio.com` in base validation does not adapt old organisation-in-host URL layouts; the client still appends `/{organisation}`. Azure DevOps Server collection prefixes and REST-version compatibility are not explicitly modelled. A collection might resemble a configured base path plus grouping segment, but that requires targeted verification; the existing custom-URL control is not a claim of Server support.

Azure can delay requests and return quota headers, including `Retry-After` even on a successful response. Inspect `X-RateLimit-Remaining`, `X-RateLimit-Delay` and related headers when diagnosing throttling; there is no automatic pacing here. `401`/`403` also require checking PAT validity, organisation selection, identity access and organisation policy. Source: [Azure rate and usage limits](https://learn.microsoft.com/en-us/azure/devops/integrate/concepts/rate-limits?view=azure-devops).

## Separate GitHub App flow

### IMPLEMENTED onboarding and API routes

This flow uses deployment configuration `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_APP_SLUG`, `GITHUB_API_URL` and `GITHUB_WEBHOOK_SECRET`, rather than an `SCMConnection` token. The private key may be PEM or base64 PEM. Public API/web base configuration determines callback/webhook URLs. App ID and private key determine runtime credential availability; onboarding additionally needs the slug, and webhook verification needs the webhook secret. See [integration setup](../app/api/integrations.py) and [App service](../app/services/github_app.py).

Paths below are under `/api/v1/integrations`:

| Method and path | Authorisation / response |
| --- | --- |
| `GET /setup` | `scan:read`; provider setup status, configured/missing requirements and URLs |
| `GET /github-app/install-url?return_to=...` | `admin`; `{ "install_url": string }`; `503` when onboarding is not configured |
| `GET /github-app/callback?installation_id=...&state=...` | No principal dependency; validates server-protected tenant state and installation through GitHub, then redirects to the UI with outcome parameters |
| `GET /github-app/installations` | `admin`; tenant installation summaries |
| `GET /github-app/installations/{id}/repositories` | `admin`; normalised `SCMRepository[]`, after tenant installation lookup |
| `GET /github-app/installations/{id}/linked-repos` | `admin`; array of `{project_key, project_name, repo}` |
| `POST /github-app/installations/{id}/reassign` | `admin`; exactly one `target_scm_connection_id` or `target_github_installation_id`; returns `{ "reassigned_count": number }` |
| `DELETE /github-app/installations/{id}` | `admin`; returns removed installation summary; `409` while linked project repositories remain |

Installation summaries contain `installation_id`, `account_login`, nullable `account_type`/`account_avatar_url`, `linked_repo_count`, `created_at` and `updated_at`. They contain no private key or access token. Linking an installation already assigned to another tenant is rejected. Unlinking removes the local tenant mapping; it does not uninstall the App on GitHub. Bulk reassignment updates all source-linked project rows; it checks that a PAT target is a same-tenant active GitHub connection, or that an alternative installation belongs to the tenant. It does not prove access to every reassigned repository or rewrite already queued scan metadata.

### IMPLEMENTED vendor requests and limits

The service signs an RS256 App JWT with an issuance time one minute in the past and expiry nine minutes ahead, then calls:

1. `GET {GITHUB_API_URL}/app/installations/{id}` with App JWT to validate installation metadata.
2. `POST {GITHUB_API_URL}/app/installations/{id}/access_tokens` with App JWT to obtain a runtime installation token.
3. `GET {GITHUB_API_URL}/installation/repositories?per_page=100` with that token to discover repositories.
4. `POST /repos/{owner}/{repo}/check-runs` and `PATCH /repos/{owner}/{repo}/check-runs/{check_run_id}` when the webhook/check integration publishes scan status.

The service uses REST version `2022-11-28` and `GITHUB_API_TIMEOUT_SECONDS` (default 20 seconds). It mints tokens on demand; it has no installation-token cache or OAuth refresh-token exchange. GitHub installation tokens expire after one hour and only reach repositories/permissions granted to the installation. Git requires Contents access; check creation/update requires Checks write. Sources: [installation authentication](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation), [check-run permissions](https://docs.github.com/en/rest/checks/runs).

KNOWN GAPS: installation repository discovery fetches only the first 100 results and converts token, HTTP or response-shape failures into `[]`. A genuine empty installation and an upstream failure therefore look alike. The installation URL and clone resolver remain GitHub.com-specific even though API requests have a configurable base. This is not a complete GitHub Enterprise App deployment implementation.

For project-linked App cloning, the resolver checks deployment configuration, tenant installation membership, GitHub.com clone destination and repository owner against `account_login` before minting a token. Unconfigured credentials, invalid installation IDs, missing tenant mappings, owner mismatches and unavailable tokens fail explicitly. A scan linked to an installation does not silently fall back to an anonymous clone.

## Repository assignment and scan association

IMPLEMENTED: a `ProjectRepository` stores a repository URL, `project_id` and either `scm_connection_id` or `github_installation_id`. Project create/add routes enforce same-tenant credential-source existence and reject supplying both sources. The database columns alone do not encode that mutual-exclusion rule. Current project routes do not verify repository-level vendor permission or provider-origin compatibility at assignment time; clone resolution enforces its destination rules later.

`POST /api/v1/projects/` and `POST /api/v1/projects/{project_key}/repos` require admin and accept a `repos` string array plus the selected credential-source ID. The add route can change an existing link to a supplied credential source and clears the alternate source. The dedicated SCM import route has the narrower skip-existing behaviour described above. The browser's create-project import tab creates one project with the selected repository URLs and connection ID; discovery is not an automatic scan or one-project-per-repository API contract.

Native `POST /api/v1/scans/` requires `scan:write`. Supply the intended `project_key` and exactly matching stored `repo` URL. The tenant-scoped project lookup supplies `project_id` and credential IDs in `scan_metadata`. Missing `project_key` deliberately produces an unassigned scan without inferred credentials, even if an identical URL exists elsewhere. A selected project that lacks that exact repository link returns `400`. This avoids ambiguous project/tenant credential selection; URL spelling, trailing `.git` and username differences can affect exact matching. Sources: [scan route](../app/api/scans.py), [project mapping](../app/services/project_mapping.py).

Synthetic native scan body:

```json
{
  "project_key": "example-project",
  "repo": "https://github.com/example-org/example-service.git",
  "branch": "main",
  "scan_type": "fast",
  "include_quality_metrics": false
}
```

The resulting scan records the IDs under `scan_metadata.scm_connection_id` or `scan_metadata.github.installation_id`; the token is resolved later. HTTP `201` means a scan record was created, not that cloning succeeded. Execution can be eager or queued according to configuration; check scan status and redacted error metadata separately.

GitHub pull-request webhook routing first resolves the installation's stored tenant, then matches the exact repository URL and installation ID within that tenant. Missing installation links and ambiguous project links are rejected. Accepted actions are `opened`, `reopened`, `synchronize` and `ready_for_review`; the handler records App context and the linked SCM connection ID when present. This is separate from native explicit-project lookup. Provider connection testing does not establish that webhook delivery, routing or check publication works.

Scan and IDE request branches must be valid Git branch names; `refs/heads/` is accepted. Explicit scan commits must contain 7–64 hexadecimal characters. Revision expressions such as `HEAD~1`, option-like refs and malformed names are rejected. Clone/history operations validate refs again. See [ref validation](../app/core/git_refs.py).

Azure `git.pullrequest.created` and `git.pullrequest.updated` webhooks currently return `503` before claiming delivery. The deployment-wide webhook secret does not identify a tenant or subscription. Restoring these events requires a stored tenant-owned subscription/credential binding; a URL or tenant supplied in the event body is insufficient. Other Azure events remain ignored. This restriction does not disable the Azure pipeline task, SCM discovery or explicitly assigned native scans.

`POST /api/v1/webhooks/github` uses the configured webhook secret and `X-Hub-Signature-256` rather than an admin principal. It also reads `X-GitHub-Event` and `X-GitHub-Delivery`, applies webhook rate/body limits and records delivery results. The success shape has `accepted`, `event`, nullable `action`, `message`, nullable `scan_id` and `check_run_id`. A missing secret returns `503`, invalid signature `401`, and rejected handler outcome `400`; an already-processing delivery can return `409`. An accepted ignored event does not imply that a scan was created. Source: [webhook route](../app/api/webhooks.py).

## Operational troubleshooting

| Symptom | Checks grounded in current behaviour |
| --- | --- |
| Creating a connection fails before a vendor request | Check required `base_url`, HTTPS/host policy and encryption-key configuration. Creation never contacts the vendor. |
| Test succeeds, but private repositories or cloning fail | Test is only `/user` or Azure project-list access. Verify repository scope, selected resources, membership, SSO/approval, exact destination origin and Git permission separately. |
| GitHub fine-grained token shows no organisations | Expected vendor behaviour for `/user/orgs`. Try the implemented `_user` view or an explicitly supplied known organisation; do not infer failed authentication. |
| GitLab subgroup projects are missing | Top-level group filter and non-recursive group-project defaults apply. Check `_user` membership view or supply the subgroup path; check encoded slashes at the proxy. |
| Bitbucket token fails REST or Git | Distinguish REST email from Git username, current API-token scopes from retired app-password settings, and the legacy workspace route from the current API. One successful stage does not resolve the shared-identity gap. |
| GitHub App sees exactly 100 repositories, or none unexpectedly | First-page-only discovery and swallowed upstream errors are known gaps. Check app configuration, installation selection and vendor status through secret-safe diagnostics. |
| Azure shows project names instead of organisations | This is implemented behaviour. Confirm `extra_config.organization`; `org` selects a project inside it. |
| Azure project inventory stops unexpectedly or hangs | Inspect continuation-header presence and empty `value`; repeated-token and total-page safeguards are absent. `$top=100` is a page size, not the service's project limit. |
| Clone fails after connection rotation/deactivation | Worker resolves the current stored token and active flag. Check API/worker encryption-key agreement, tenant link and destination; test-history fields can be stale. |
| Scan is unassigned or has no credentials | Native scan creation requires explicit `project_key` and an exact stored repo link. Adding a connection alone is insufficient. |
| Deleting a connection/installation returns `409` | Remove or reassign dependent project repository links first. There is no PAT bulk-reassignment route equivalent to the App route. |
| UI/API listing fails with a generic server error | Provider discovery exceptions are not normalised. Separate application authorisation/rate limiting from upstream HTTP status, TLS/DNS, timeout and pagination failures. |
| Provider throttling | Examine provider-specific quota/retry headers securely. Current clients have no retry/backoff; repeated Test/list requests consume both application and upstream budgets. |

For a useful incident record, retain timestamp, application revision, worker/API configuration differences, provider type/base origin, tenant/connection or installation ID, endpoint, upstream status, safe request ID, page/token presence and the scan ID. Exclude tokens, Basic headers, authenticated clone URLs, private keys and full sensitive response bodies. Neither a provider identity response nor source review proves a private clone or successful scan.

## KNOWN GAPS and explicit follow-up work

These are documentation findings, not implemented fixes or evidence that the canonical task list has been updated:

1. Correct Bitbucket's credential contract for current API tokens: choose an explicit supported REST authentication mode, handle Git identity independently, retire app-password guidance and migrate workspace discovery with current response fixtures/scopes. Do not present the existing form as verified end-to-end API-token support.
2. Paginate GitHub App repository discovery and distinguish upstream failure from an empty accessible set. Cover more than 100 results with a focused fixture.
3. Make connection-test wording reflect identity/project connectivity, or implement separate explicit repository/clone permission verification. Add expiry/capability diagnostics only when supported by actual provider responses.
4. Define discovery completeness: provider-aware continuation handling, bounded/repeated-token safeguards, response validation, deduplication and clear partial-result/error reporting. Preserve same-origin/prefix checks before reusing credentials on next links.
5. Address GitLab subgroup traversal and offset limits if full group inventory is required; record the chosen shared-project behaviour. Correct normalised internal/private visibility if callers need that distinction.
6. Define supported self-hosted deployments explicitly: arbitrary enterprise host policy, separate API/clone origins where necessary, GitHub App install/clone hosts, GitLab prefixes and Azure Server/legacy layouts. Verify private API and clone policy together; do not claim DNS or redirect isolation from the existing syntax checks.
7. Validate imported/assigned repository URLs and active credential sources consistently; avoid duplicate new URLs in one import body. Enforce credential-source exclusivity at persistence boundaries if records can be written outside project routes. Clarify historical/queued scan behaviour before deletion or reassignment.
8. Extend tenant/owner checks to every credential-using path as appropriate, including webhook/check operations, rather than assuming the clone guard covers them all. The clone resolver now fails explicitly when requested App configuration is absent.
9. Normalise provider exceptions and rate-limit diagnostics without leaking secrets; consider provider-directed pacing and bounded retries. Refresh stale `last_test_ok` information after credential/base changes or clearly label it as historical.
10. Provide an operational encryption-key migration procedure and assess runtime Git credential exposure, subprocess environment, temporary checkout access and redirect/network controls. No OAuth refresh, service-principal or managed-identity support should be claimed until implemented.

The main integration pass also updated the in-app request examples, retired app-password guidance and connection-test claims. Remaining implementation work is recorded in the existing local `Tasks.md` plan.

## Validation and research coverage

This document was prepared by reading current source, callers, schemas, frontend form/help and relevant tests, plus official GitHub, GitLab, Atlassian and Microsoft documentation linked beside the applicable claims. Relative source links were checked locally. The concurrent SCM source diff was reviewed before finalisation. No application/bundle code was run, imported, tested, built or installed for this documentation task, and no live account, token, clone or provider API call was used. The untrusted `DO-NOT-RUN` tree was not used as executable or copied source material.

Regression red/green execution is not applicable to this document-only change: no runtime behaviour or assertion was changed. Existing tests cited above were inspected, not run; their current pass/fail state belongs to the main integration report. Coverage gaps include live provider permissions/SSO, Bitbucket API-token interoperability and endpoint migration, large inventories, self-hosted variants, native Git behaviour and deployed API/worker key agreement. Vendor documentation describes provider capability; it does not close those application verification gaps.
