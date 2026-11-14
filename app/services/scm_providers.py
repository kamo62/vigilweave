"""SCM provider clients for GitHub, GitLab, Bitbucket, and Azure DevOps."""

from __future__ import annotations

import logging
from typing import Protocol
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import httpx

from app.models.scm_connection import SCMOrganization, SCMProvider, SCMRepository

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 15.0


def _validated_destination(url: str, base: str, *, path_prefix: str = ""):
    """Keep credentials on their configured HTTPS origin and deployment path."""
    parsed, expected = urlsplit(url), urlsplit(base)
    if (
        url != url.strip()
        or any(ord(char) < 32 for char in url)
        or parsed.scheme != "https"
        or expected.scheme != "https"
        or not parsed.hostname
        or parsed.hostname != expected.hostname
        or (parsed.port or 443) != (expected.port or 443)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or "\\" in url
    ):
        raise ValueError("SCM destination must match the configured HTTPS origin")
    path = parsed.path
    # Reject escaped traversal, including repeated encoding, before prefix matching.
    for _ in range(8):
        decoded = unquote(path)
        if decoded == path:
            break
        path = decoded
    if any(part in {".", ".."} for part in path.split("/")) or "\\" in path:
        raise ValueError("SCM destination contains an invalid path")
    prefix = unquote(path_prefix).rstrip("/")
    if prefix and not path.startswith(prefix + "/"):
        raise ValueError("SCM destination is outside the configured path")
    return parsed


def _credential_url(url: str, base: str, username: str, token: str, *, prefix: str = "") -> str:
    original = urlsplit(url)
    if original.password is not None:
        raise ValueError("SCM clone URL must not contain a password")
    # Azure and Bitbucket return username-bearing HTTPS clone URLs. Replace that
    # username after parsing the actual destination, rather than appending userinfo.
    if original.username is not None:
        url = urlunsplit(original._replace(netloc=original.netloc.rsplit("@", 1)[-1]))
    parsed = _validated_destination(url, base, path_prefix=prefix)
    if parsed.query:
        raise ValueError("SCM clone URL must not contain a query")
    credentials = f"{quote(username, safe='')}:{quote(token, safe='')}"
    return urlunsplit(parsed._replace(netloc=f"{credentials}@{parsed.netloc}"))


def _continuation_url(url: str | None, base: str, seen: set[str]) -> str | None:
    if url is None:
        return None
    _validated_destination(url, base, path_prefix=f"{urlsplit(base).path}/2.0")
    if url in seen:
        raise ValueError("SCM pagination repeated a continuation URL")
    seen.add(url)
    return url


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class SCMProviderClient(Protocol):
    """Interface for SCM provider operations."""

    def test_connection(self) -> tuple[bool, str, str | None]:
        """Test the connection. Returns (ok, message, username)."""
        ...

    def list_organizations(self) -> list[SCMOrganization]:
        """List organizations/groups/workspaces the token has access to."""
        ...

    def list_repositories(self, org: str) -> list[SCMRepository]:
        """List repositories within an organization."""
        ...

    def authenticated_clone_url(self, repo_url: str) -> str:
        """Produce an authenticated HTTPS clone URL."""
        ...


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------


class GitHubClient:
    """GitHub REST API client using a Personal Access Token."""

    def __init__(self, token: str, base_url: str = "https://api.github.com") -> None:
        self._token = token
        self._base = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
        }

    def test_connection(self) -> tuple[bool, str, str | None]:
        try:
            resp = httpx.get(f"{self._base}/user", headers=self._headers, timeout=_DEFAULT_TIMEOUT)
            resp.raise_for_status()
            login = resp.json().get("login", "unknown")
            return True, f"Authenticated as {login}", login
        except httpx.HTTPStatusError as exc:
            return False, f"GitHub API error: {exc.response.status_code}", None
        except Exception as exc:
            return False, f"Connection failed: {exc}", None

    def list_organizations(self) -> list[SCMOrganization]:
        orgs: list[SCMOrganization] = []
        page = 1
        while True:
            resp = httpx.get(
                f"{self._base}/user/orgs",
                headers=self._headers,
                params={"per_page": 100, "page": page},
                timeout=_DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            for org in data:
                orgs.append(
                    SCMOrganization(
                        id=str(org["id"]),
                        name=org["login"],
                        avatar_url=org.get("avatar_url"),
                    )
                )
            page += 1
            if len(data) < 100:
                break
        return orgs

    def list_repositories(self, org: str) -> list[SCMRepository]:
        repos: list[SCMRepository] = []
        # If org is empty or "_user", list the authenticated user's repos
        endpoint = (
            f"{self._base}/user/repos"
            if not org or org == "_user"
            else f"{self._base}/orgs/{quote(org, safe='')}/repos"
        )
        params: dict = {"per_page": 100, "page": 1, "type": "all", "sort": "updated"}
        if not org or org == "_user":
            params = {
                "per_page": 100,
                "page": 1,
                "visibility": "all",
                "affiliation": "owner,collaborator,organization_member",
                "sort": "updated",
            }

        while True:
            resp = httpx.get(
                endpoint, headers=self._headers, params=params, timeout=_DEFAULT_TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            for repo in data:
                repos.append(
                    SCMRepository(
                        id=str(repo["id"]),
                        name=repo["name"],
                        full_name=repo["full_name"],
                        clone_url=repo["clone_url"],
                        default_branch=repo.get("default_branch"),
                        description=repo.get("description"),
                        language=repo.get("language"),
                        is_private=repo.get("private", False),
                        updated_at=repo.get("updated_at"),
                    )
                )
            if len(data) < 100:
                break
            params["page"] += 1
        return repos

    def authenticated_clone_url(self, repo_url: str) -> str:
        parsed = urlsplit(self._base)
        base = "https://github.com" if parsed.hostname == "api.github.com" else self._base
        return _credential_url(repo_url, base, "x-access-token", self._token)


# ---------------------------------------------------------------------------
# GitLab
# ---------------------------------------------------------------------------


class GitLabClient:
    """GitLab REST API client using a Personal Access Token."""

    def __init__(self, token: str, base_url: str = "https://gitlab.com") -> None:
        self._token = token
        self._base = base_url.rstrip("/")
        self._headers = {"PRIVATE-TOKEN": token}

    def test_connection(self) -> tuple[bool, str, str | None]:
        try:
            resp = httpx.get(
                f"{self._base}/api/v4/user", headers=self._headers, timeout=_DEFAULT_TIMEOUT
            )
            resp.raise_for_status()
            username = resp.json().get("username", "unknown")
            return True, f"Authenticated as {username}", username
        except httpx.HTTPStatusError as exc:
            return False, f"GitLab API error: {exc.response.status_code}", None
        except Exception as exc:
            return False, f"Connection failed: {exc}", None

    def list_organizations(self) -> list[SCMOrganization]:
        groups: list[SCMOrganization] = []
        page = 1
        while True:
            resp = httpx.get(
                f"{self._base}/api/v4/groups",
                headers=self._headers,
                params={
                    "min_access_level": 10,
                    "top_level_only": True,
                    "per_page": 100,
                    "page": page,
                },
                timeout=_DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            for group in data:
                groups.append(
                    SCMOrganization(
                        id=str(group["id"]),
                        name=group.get("full_path", group.get("name", "")),
                        avatar_url=group.get("avatar_url"),
                    )
                )
            if len(data) < 100:
                break
            page += 1
        return groups

    def list_repositories(self, org: str) -> list[SCMRepository]:
        repos: list[SCMRepository] = []
        endpoint = (
            f"{self._base}/api/v4/projects"
            if not org or org == "_user"
            else f"{self._base}/api/v4/groups/{quote(org, safe='')}/projects"
        )
        params: dict = {"per_page": 100, "page": 1, "order_by": "last_activity_at", "sort": "desc"}
        if not org or org == "_user":
            params["membership"] = True

        while True:
            resp = httpx.get(
                endpoint, headers=self._headers, params=params, timeout=_DEFAULT_TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            for project in data:
                repos.append(
                    SCMRepository(
                        id=str(project["id"]),
                        name=project["name"],
                        full_name=project.get("path_with_namespace", project["name"]),
                        clone_url=project.get("http_url_to_repo", ""),
                        default_branch=project.get("default_branch"),
                        description=project.get("description"),
                        is_private=project.get("visibility") == "private",
                        updated_at=project.get("last_activity_at"),
                    )
                )
            if len(data) < 100:
                break
            params["page"] += 1
        return repos

    def authenticated_clone_url(self, repo_url: str) -> str:
        return _credential_url(
            repo_url, self._base, "oauth2", self._token, prefix=urlsplit(self._base).path
        )


# ---------------------------------------------------------------------------
# Bitbucket
# ---------------------------------------------------------------------------


class BitbucketClient:
    """Bitbucket Cloud REST client with a shared REST/Git Basic-auth identity."""

    def __init__(
        self,
        token: str,
        base_url: str = "https://api.bitbucket.org",
        extra_config: dict | None = None,
    ) -> None:
        self._token = token
        self._base = base_url.rstrip("/")
        self._username = (extra_config or {}).get("username", "")
        self._auth = (self._username, token)

    def test_connection(self) -> tuple[bool, str, str | None]:
        try:
            resp = httpx.get(f"{self._base}/2.0/user", auth=self._auth, timeout=_DEFAULT_TIMEOUT)
            resp.raise_for_status()
            display_name = resp.json().get("display_name", "unknown")
            return True, f"Authenticated as {display_name}", display_name
        except httpx.HTTPStatusError as exc:
            return False, f"Bitbucket API error: {exc.response.status_code}", None
        except Exception as exc:
            return False, f"Connection failed: {exc}", None

    def list_organizations(self) -> list[SCMOrganization]:
        workspaces: list[SCMOrganization] = []
        initial_url = f"{self._base}/2.0/user/permissions/workspaces"
        url: str | None = initial_url
        seen = {initial_url}
        params: dict[str, str | int] | None = {"pagelen": 100}
        while url:
            resp = httpx.get(url, auth=self._auth, params=params, timeout=_DEFAULT_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("values", []):
                ws = item.get("workspace", {})
                workspaces.append(
                    SCMOrganization(
                        id=ws.get("uuid", ws.get("slug", "")),
                        name=ws.get("slug", ws.get("name", "")),
                        avatar_url=ws.get("links", {}).get("avatar", {}).get("href"),
                    )
                )
            url = _continuation_url(data.get("next"), self._base, seen)
            params = None  # Continuations already contain their own query.
        return workspaces

    def list_repositories(self, org: str) -> list[SCMRepository]:
        repos: list[SCMRepository] = []
        initial_url = f"{self._base}/2.0/repositories/{quote(org, safe='')}"
        url: str | None = initial_url
        seen = {initial_url}
        params: dict[str, str | int] | None = {"role": "member", "pagelen": 100}
        while url:
            resp = httpx.get(
                url,
                auth=self._auth,
                params=params,
                timeout=_DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            for repo in data.get("values", []):
                clone_url = ""
                for link in repo.get("links", {}).get("clone", []):
                    if link.get("name") == "https":
                        clone_url = link["href"]
                        break
                repos.append(
                    SCMRepository(
                        id=repo.get("uuid", ""),
                        name=repo["name"],
                        full_name=repo.get("full_name", repo["name"]),
                        clone_url=clone_url,
                        default_branch=repo.get("mainbranch", {}).get("name")
                        if repo.get("mainbranch")
                        else None,
                        description=repo.get("description"),
                        language=repo.get("language"),
                        is_private=repo.get("is_private", False),
                        updated_at=repo.get("updated_on"),
                    )
                )
            url = _continuation_url(data.get("next"), self._base, seen)
            params = None
        return repos

    def authenticated_clone_url(self, repo_url: str) -> str:
        base = (
            "https://bitbucket.org"
            if urlsplit(self._base).hostname == "api.bitbucket.org"
            else self._base
        )
        return _credential_url(repo_url, base, self._username, self._token)


# ---------------------------------------------------------------------------
# Azure DevOps
# ---------------------------------------------------------------------------


class AzureDevOpsClient:
    """Azure DevOps REST API client using a Personal Access Token."""

    def __init__(
        self, token: str, base_url: str = "https://dev.azure.com", extra_config: dict | None = None
    ) -> None:
        self._token = token
        self._base = base_url.rstrip("/")
        self._org = (extra_config or {}).get("organization", "")
        self._auth = ("", token)  # Basic auth with empty username

    def test_connection(self) -> tuple[bool, str, str | None]:
        try:
            resp = httpx.get(
                f"{self._base}/{quote(self._org, safe='')}/_apis/projects",
                auth=self._auth,
                params={"$top": 1, "api-version": "7.1"},
                timeout=_DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            return True, f"Connected to organization '{self._org}'", self._org
        except httpx.HTTPStatusError as exc:
            return False, f"Azure DevOps API error: {exc.response.status_code}", None
        except Exception as exc:
            return False, f"Connection failed: {exc}", None

    def list_organizations(self) -> list[SCMOrganization]:
        """List projects within the Azure DevOps organization (projects are the grouping unit)."""
        projects: list[SCMOrganization] = []
        url = f"{self._base}/{quote(self._org, safe='')}/_apis/projects"
        continuation_token: str | None = None

        while True:
            params: dict = {"stateFilter": "wellFormed", "$top": 100, "api-version": "7.1"}
            if continuation_token:
                params["continuationToken"] = continuation_token

            resp = httpx.get(url, auth=self._auth, params=params, timeout=_DEFAULT_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            for project in data.get("value", []):
                projects.append(
                    SCMOrganization(
                        id=project["id"],
                        name=project["name"],
                    )
                )

            continuation_token = resp.headers.get("x-ms-continuationtoken")
            if not continuation_token or not data.get("value"):
                break

        return projects

    def list_repositories(self, org: str) -> list[SCMRepository]:
        """List repositories within an Azure DevOps project."""
        repos: list[SCMRepository] = []
        organization_path = quote(self._org, safe="")
        project_path = quote(org, safe="")
        resp = httpx.get(
            f"{self._base}/{organization_path}/{project_path}/_apis/git/repositories",
            auth=self._auth,
            params={"api-version": "7.1"},
            timeout=_DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        for repo in data.get("value", []):
            repos.append(
                SCMRepository(
                    id=repo["id"],
                    name=repo["name"],
                    full_name=f"{repo.get('project', {}).get('name', org)}/{repo['name']}",
                    clone_url=repo.get("remoteUrl", ""),
                    default_branch=(repo.get("defaultBranch", "") or "").removeprefix("refs/heads/")
                    or None,
                    description=repo.get("project", {}).get("description"),
                    is_private=True,  # ADO repos are always private by default
                )
            )

        return repos

    def authenticated_clone_url(self, repo_url: str) -> str:
        if not self._org:
            raise ValueError("Azure DevOps organisation is required")
        return _credential_url(
            repo_url,
            self._base,
            "pat",
            self._token,
            prefix=f"{urlsplit(self._base).path}/{self._org}",
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_scm_client(
    provider: SCMProvider, token: str, base_url: str, extra_config: dict | None = None
) -> SCMProviderClient:
    """Return the appropriate SCM provider client."""
    match provider:
        case SCMProvider.GITHUB:
            return GitHubClient(token, base_url)
        case SCMProvider.GITLAB:
            return GitLabClient(token, base_url)
        case SCMProvider.BITBUCKET:
            return BitbucketClient(token, base_url, extra_config)
        case SCMProvider.AZURE_DEVOPS:
            return AzureDevOpsClient(token, base_url, extra_config)
        case _:
            raise ValueError(f"Unsupported SCM provider: {provider}")
