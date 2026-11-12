import { useCallback, useMemo, useState, type JSX } from 'react'
import { useNavigate, useSearch } from '@tanstack/react-router'
import {
  Book,
  BookOpen,
  ChevronRight,
  Code2,
  FileText,
  GitBranch,
  HelpCircle,
  LayoutGrid,
  Play,
  Search,
  Server,
  Shield,
  Users,
  Webhook,
} from 'lucide-react'
import { Link } from '@tanstack/react-router'

import { ApiReference } from './docs/ApiReference'
import { AuthUserManagement } from './docs/AuthUserManagement'
import { Faq } from './docs/Faq'
import { GettingStarted } from './docs/GettingStarted'
import { Integrations } from './docs/Integrations'
import { PolicyGovernance } from './docs/PolicyGovernance'
import { ReportsAnalytics } from './docs/ReportsAnalytics'
import { RulesCustomization } from './docs/RulesCustomization'
import { Scanning } from './docs/Scanning'
import { ScmConnections } from './docs/ScmConnections'
import { SelfHosting } from './docs/SelfHosting'
import { Webhooks } from './docs/Webhooks'

const sections = [
  { id: 'getting-started', label: 'Getting Started', icon: Play, component: GettingStarted, keywords: 'install setup docker compose quick start prerequisites' },
  { id: 'auth-user-management', label: 'Auth & Users', icon: Users, component: AuthUserManagement, keywords: 'authentication sso saml oidc scim directory sync active directory okta azure ad workos users roles admin member tenant api keys local auth enterprise' },
  { id: 'scanning', label: 'Scanning', icon: Shield, component: Scanning, keywords: 'sast secrets sca iac scan types triage sarif findings' },
  { id: 'rules-customization', label: 'Rules & Customization', icon: BookOpen, component: RulesCustomization, keywords: 'sonarqube sonarcloud rules custom engine tool configuration rule packs' },
  { id: 'policy-governance', label: 'Policy & Governance', icon: LayoutGrid, component: PolicyGovernance, keywords: 'quality gates policy preset lenient balanced strict waivers audit' },
  { id: 'reports-analytics', label: 'Reports & Analytics', icon: FileText, component: ReportsAnalytics, keywords: 'pdf csv export dashboard owasp cwe compliance report' },
  { id: 'scm-connections', label: 'SCM Connections', icon: GitBranch, component: ScmConnections, keywords: 'github gitlab bitbucket azure devops pat token private repository import' },
  { id: 'integrations', label: 'CI/CD & Integrations', icon: Code2, component: Integrations, keywords: 'github actions azure devops vscode mcp claude prisma sonarqube' },
  { id: 'webhooks', label: 'Webhooks', icon: Webhook, component: Webhooks, keywords: 'webhook push pull request automatic trigger event' },
  { id: 'api-reference', label: 'API Reference', icon: Book, component: ApiReference, keywords: 'api rest curl authentication endpoints projects scans findings' },
  { id: 'self-hosting', label: 'Self-Hosting', icon: Server, component: SelfHosting, keywords: 'docker kubernetes k8s deploy environment variables database workos sso prometheus monitoring' },
  { id: 'faq', label: 'FAQ', icon: HelpCircle, component: Faq, keywords: 'faq questions help support pricing enterprise' },
] as const

export function DocsPage(): JSX.Element {
  const { section } = useSearch({ from: '/docs' })
  const activeSection = section ?? 'getting-started'
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')

  const setActiveSection = useCallback(
    (id: string) => {
      navigate({ to: '/docs', search: { section: id }, replace: true })
      setSearchQuery('')
    },
    [navigate],
  )

  const filteredSections = useMemo(() => {
    if (!searchQuery.trim()) return sections
    const q = searchQuery.toLowerCase()
    return sections.filter(
      (s) =>
        s.label.toLowerCase().includes(q) ||
        s.keywords.toLowerCase().includes(q),
    )
  }, [searchQuery])

  const active = sections.find((s) => s.id === activeSection)
  const ActiveComponent = active?.component ?? GettingStarted

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-10">
      {/* Mobile selector */}
      <div className="lg:hidden mb-6">
        <select
          value={activeSection}
          onChange={(e) => setActiveSection(e.target.value)}
          className="w-full px-3 py-2.5 rounded-sm border border-border bg-card text-sm font-medium"
        >
          {sections.map((s) => (
            <option key={s.id} value={s.id}>{s.label}</option>
          ))}
        </select>
      </div>

      <div className="flex gap-10">
        {/* Left Sidebar */}
        <aside className="hidden lg:block w-56 shrink-0">
          <div className="sticky top-24">
            {/* Search */}
            <div className="relative mb-4">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search docs..."
                className="w-full pl-8 pr-3 py-1.5 rounded-sm border border-border bg-card text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/50"
              />
            </div>

            <div className="flex items-center justify-between mb-3 px-2">
              <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-muted-foreground">
                Documentation
              </p>
              <span className="text-[10px] font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                v1.0.0-beta
              </span>
            </div>
            <nav className="space-y-0.5">
              {filteredSections.map((s) => {
                const isActive = activeSection === s.id
                return (
                  <button
                    key={s.id}
                    onClick={() => setActiveSection(s.id)}
                    className={`w-full flex items-center gap-2.5 text-left px-2.5 py-2 rounded-sm text-sm transition-colors ${
                      isActive
                        ? 'bg-primary/10 text-primary font-medium'
                        : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
                    }`}
                  >
                    <s.icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-primary' : ''}`} />
                    {s.label}
                  </button>
                )
              })}
            </nav>
          </div>
        </aside>

        {/* Content */}
        <main className="flex-1 min-w-0">
          <div className="max-w-3xl">
            {/* Breadcrumb */}
            <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-sm text-muted-foreground mb-6">
              <Link to="/docs" className="hover:text-foreground transition-colors">Docs</Link>
              <ChevronRight className="w-3.5 h-3.5" />
              <span className="text-foreground font-medium">{active?.label ?? 'Getting Started'}</span>
            </nav>
            <ActiveComponent />
          </div>
        </main>
      </div>
    </div>
  )
}
