import type { ReactNode } from "react";

import { Link, useRouterState } from "@tanstack/react-router";
import {
  Activity,
  FolderOpen,
  LogOut,
  Shield,
  ShieldCheck,
  TerminalSquare,
  User,
  Workflow,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useAuth } from "@/lib/useAuth";
import { useLicense } from "@/lib/hooks/useLicense";

type LayoutProps = { children: ReactNode };
type NavItem = {
  to: string
  label: string
  icon: typeof FolderOpen
  search?: { tab: string }
}

const tierColor: Record<string, "default" | "success" | "primary"> = {
  community: "default",
  pro: "primary",
  enterprise: "success",
};

export function Layout({ children }: LayoutProps) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { tier } = useLicense();
  const { user, logout, isAuthenticated } = useAuth();
  const canAccessSettings = user?.role === 'admin' || user?.platform_role === 'operator';
  const defaultSettingsTab = user?.role === 'admin' ? 'platform' : user?.platform_role === 'operator' ? 'saas-admin' : 'platform'
  const navSections: Array<{ label: string; items: NavItem[] }> = [
    {
      label: 'Main',
      items: [
        { to: '/projects', label: 'Projects', icon: FolderOpen },
        { to: '/scans', label: 'Scans', icon: Activity },
        { to: '/integrations', label: 'Integrations', icon: Workflow },
      ],
    },
    {
      label: 'Governance',
      items: [{ to: '/policies', label: 'Policies', icon: ShieldCheck }],
    },
    ...(canAccessSettings
        ? [
            {
              label: 'Admin',
              items: [{ to: '/settings', label: 'Settings', icon: TerminalSquare, search: { tab: defaultSettingsTab } }],
            },
          ]
      : []),
  ];

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="sticky top-0 flex h-screen w-[240px] shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
        {/* Brand */}
        <div className="flex items-center gap-3 px-5 py-5 border-b border-sidebar-border">
          <div className="flex h-9 w-9 items-center justify-center rounded-sm bg-primary text-primary-foreground shadow-sm">
            <Shield className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-bold text-sidebar-foreground tracking-tight">
              VigilWeave
            </p>
            <p className="text-[10px] font-medium text-muted-foreground tracking-wide uppercase">
              Security Platform
            </p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-6 px-3 py-4">
          {navSections.map((section) => (
            <div key={section.label}>
              <p className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground/70">
                {section.label}
              </p>
              <div className="space-y-0.5">
                {section.items.map(({ to, label, icon: Icon, search }) => {
                  const active =
                    pathname === to || pathname.startsWith(to + "/");
                  return (
                    <Link
                      aria-current={active ? "page" : undefined}
                      className={`flex items-center gap-3 rounded-sm px-3 py-2 text-[13px] transition-all duration-150 ${
                        active
                          ? "bg-accent text-accent-foreground font-semibold border-l-2 border-primary"
                          : "text-muted-foreground hover:bg-accent/50 hover:text-accent-foreground border-l-2 border-transparent"
                      }`}
                      key={to}
                      to={to}
                      search={search}
                    >
                      <Icon size={16} strokeWidth={active ? 2.5 : 2} />
                      <span>{label}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* Footer with User Menu */}
        <div className="border-t border-sidebar-border px-5 py-4">
          <div className="flex items-center justify-between mb-3">
            <ThemeToggle />
            <Badge color="default" variant="bordered" size="sm">
              <span className="font-mono text-[10px]">v2.0.0</span>
            </Badge>
          </div>
          {isAuthenticated && user ? (
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center">
                  <span className="text-primary text-sm font-bold">
                    {(user.name?.[0] || user.email[0]).toUpperCase()}
                  </span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-sidebar-foreground truncate">
                    {user.name || user.email.split("@")[0]}
                  </p>
                  <p className="text-xs text-muted-foreground truncate">
                    {user.email}
                  </p>
                </div>
              </div>
              <div className="flex gap-2 pt-1">
                <Button
                  variant="ghost"
                  size="sm"
                  className="flex-1 h-8 text-xs"
                  asChild
                >
                  <Link to="/settings" search={{ tab: defaultSettingsTab }}>
                    <User className="mr-1.5 h-3.5 w-3.5" />
                    Settings
                  </Link>
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 text-xs text-destructive hover:text-destructive hover:bg-destructive/10"
                  onClick={logout}
                >
                  <LogOut className="mr-1.5 h-3.5 w-3.5" />
                  Sign out
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-muted-foreground font-mono">
                v2.0.0
              </span>
              <Badge
                color={tierColor[tier] ?? "default"}
                variant="bordered"
                size="sm"
              >
                {tier === "community" ? "OSS" : tier.toUpperCase()}
              </Badge>
            </div>
          )}
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 overflow-y-auto bg-background">
        <div className="mx-auto max-w-[1200px] px-8 py-8">{children}</div>
      </div>
    </div>
  );
}
