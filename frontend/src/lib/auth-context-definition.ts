import { createContext } from "react";

export type SessionAuthProvider = "none" | "local" | "workos";

export interface User {
  id: number;
  email: string;
  name?: string | null;
  avatar_url?: string | null;
  tenant_slug: string;
  auth_provider: "local" | "workos";
  workos_org_id?: string | null;
  role: "admin" | "member";
  platform_role: "none" | "operator";
  onboarding_completed: boolean;
  created_at: string;
  last_login_at?: string | null;
}

export interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  authBootstrapError: string | null;
  sessionAuthProvider: SessionAuthProvider | null;
  apiKeysEnabled: boolean;
  bootstrapRegistrationRequired: boolean;
  saasEnabled: boolean;
  workosConfigured: boolean;
  login: (options?: { nextPath?: string; inviteToken?: string }) => void;
  logout: () => Promise<void>;
  refreshUser: () => Promise<User | null>;
  refreshCapabilities: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | null>(null);
