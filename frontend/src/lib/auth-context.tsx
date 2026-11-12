/**
 * Authentication context provider for SaaS platform.
 *
 * Provides authentication state management for WorkOS-based sessions.
 * Falls back to API key mode for self-hosted deployments.
 */

import type { JSX, ReactNode } from "react";
import { useCallback, useEffect, useState } from "react";

import { clearRuntimeAuthConfig, getCsrfToken, setCsrfToken } from "./auth";
import { fetchCapabilities } from "./api";
import { buildApiUrl } from "./api-url";
import { buildLoginPath } from "./navigation";
import {
  AuthContext,
  type AuthContextType,
  type SessionAuthProvider,
  type User,
} from "./auth-context-definition";

interface AuthProviderProps {
  children: ReactNode;
}

function parseSessionAuthProvider(value: unknown): SessionAuthProvider {
  return value === "none" || value === "local" || value === "workos"
    ? value
    : "none";
}

function parseBooleanFlag(value: unknown): boolean {
  return value === true;
}

export function AuthProvider({ children }: AuthProviderProps): JSX.Element {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [authBootstrapError, setAuthBootstrapError] = useState<string | null>(null);
  const [sessionAuthProvider, setSessionAuthProvider] =
    useState<SessionAuthProvider | null>(null);
  const [apiKeysEnabled, setApiKeysEnabled] = useState(true);
  const [bootstrapRegistrationRequired, setBootstrapRegistrationRequired] =
    useState(false);
  const [saasEnabled, setSaasEnabled] = useState(false);
  const [workosConfigured, setWorkosConfigured] = useState(false);

  const refreshUser = useCallback(async (): Promise<User | null> => {
    try {
      const response = await fetch(buildApiUrl("/api/v1/auth/me"), {
        credentials: "include",
      });

      if (response.ok) {
        const userData = (await response.json()) as User;
        setUser(userData);
        return userData;
      } else if (response.status === 401) {
        setUser(null);
        return null;
      }
    } catch (error) {
      console.error("Failed to refresh user:", error);
      setUser(null);
      return null;
    }

    setUser(null);
    return null;
  }, []);

  const checkAuthStatus = useCallback(async () => {
    try {
      setIsLoading(true);

      const capabilities = await fetchCapabilities();
      const resolvedSessionAuthProvider = parseSessionAuthProvider(
        capabilities.authentication?.session_auth_provider,
      );
      const resolvedApiKeysEnabled = parseBooleanFlag(
        capabilities.authentication?.api_keys,
      );
      const resolvedBootstrapRegistrationRequired = parseBooleanFlag(
        capabilities.authentication?.bootstrap_registration_required,
      );
      const resolvedSaasEnabled = parseBooleanFlag(
        capabilities.authentication?.saas_enabled,
      );
      const resolvedWorkosConfigured = parseBooleanFlag(
        capabilities.authentication?.workos_configured,
      );
      setAuthBootstrapError(null);
      setSessionAuthProvider(resolvedSessionAuthProvider);
      setApiKeysEnabled(resolvedApiKeysEnabled);
      setBootstrapRegistrationRequired(resolvedBootstrapRegistrationRequired);
      setSaasEnabled(resolvedSaasEnabled);
      setWorkosConfigured(resolvedWorkosConfigured);

      if (
        resolvedSessionAuthProvider !== "none" &&
        (resolvedSessionAuthProvider !== "workos" || resolvedWorkosConfigured)
      ) {
        try {
          const csrfResponse = await fetch(buildApiUrl("/api/v1/auth/csrf"), {
            credentials: "include",
          });
          if (csrfResponse.ok) {
            const payload = (await csrfResponse.json()) as { csrf_token?: string };
            const token = (payload.csrf_token ?? "").trim();
            if (token) {
              setCsrfToken(token);
            }
          }
        } catch (csrfError) {
          console.error("Failed to initialize CSRF token:", csrfError);
        }
        await refreshUser();
      } else {
        setUser(null);
      }
    } catch (error) {
      console.error("Failed to check auth status:", error);
      setAuthBootstrapError(
        error instanceof Error
          ? error.message
          : "Authentication bootstrap failed.",
      );
      setSessionAuthProvider(null);
      setApiKeysEnabled(false);
      setBootstrapRegistrationRequired(false);
      setSaasEnabled(false);
      setWorkosConfigured(false);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, [refreshUser]);

  // Check authentication status on mount
  useEffect(() => {
    checkAuthStatus();
  }, [checkAuthStatus]);

  const login = useCallback((options?: { nextPath?: string; inviteToken?: string }) => {
    const loginPath = buildLoginPath({
      nextPath: options?.nextPath,
      inviteToken: options?.inviteToken,
    });
    if (sessionAuthProvider === "local") {
      window.location.assign(
        bootstrapRegistrationRequired
          ? options?.nextPath
            ? `/setup?${new URLSearchParams({ next: options.nextPath }).toString()}`
            : "/setup"
          : loginPath,
      );
      return;
    }
    if (
      !saasEnabled ||
      sessionAuthProvider === null ||
      sessionAuthProvider === "none" ||
      !workosConfigured
    ) {
      return;
    }
    const query = new URLSearchParams();
    if (options?.nextPath) {
      query.set("next", options.nextPath);
    }
    if (options?.inviteToken) {
      query.set("invite", options.inviteToken);
    }
    const suffix = query.toString();
    window.location.assign(
      buildApiUrl(`/api/v1/auth/login${suffix ? `?${suffix}` : ""}`),
    );
  }, [
    bootstrapRegistrationRequired,
    saasEnabled,
    sessionAuthProvider,
    workosConfigured,
  ]);

  const logout = useCallback(async () => {
    try {
      const headers = new Headers();
      const csrfToken = getCsrfToken();
      if (csrfToken) {
        headers.set("X-CSRF-Token", csrfToken);
      }
      await fetch(buildApiUrl("/api/v1/auth/logout"), {
        method: "POST",
        credentials: "include",
        headers,
      });
    } catch (error) {
      console.error("Logout error:", error);
    } finally {
      setUser(null);
      clearRuntimeAuthConfig();
      if (sessionAuthProvider === "workos") {
        window.location.assign("/");
      } else if (sessionAuthProvider === "local") {
        window.location.assign("/login");
      }
    }
  }, [sessionAuthProvider]);

  const refreshCapabilities = useCallback(async () => {
    await checkAuthStatus();
  }, [checkAuthStatus]);

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    authBootstrapError,
    sessionAuthProvider,
    apiKeysEnabled,
    bootstrapRegistrationRequired,
    saasEnabled,
    workosConfigured,
    login,
    logout,
    refreshUser,
    refreshCapabilities,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
