import { useState, type JSX, type ReactNode } from 'react'
import { Link } from '@tanstack/react-router'
import { Menu, X } from 'lucide-react'

import { Button } from '../components/ui/button'
import { ThemeToggle } from '../components/ThemeToggle'
import { getDomainContext, marketingUrl, appUrl } from '../lib/domain'
import {
  CONTACT_URL,
  DOWNLOADS_URL,
  LICENSING_URL,
} from '../lib/public-links'
import { useAuth } from '../lib/useAuth'

interface PublicLayoutProps {
  children: ReactNode
}

function buildNavLinks() {
  const ctx = getDomainContext()

  // In unified mode (self-hosted / local dev) all links are internal.
  if (ctx === 'unified') {
    return [
      { label: 'Features', href: '/#features', routerLink: false },
      { label: 'Pricing', href: '/pricing', routerLink: true },
      { label: 'Docs', href: '/docs', routerLink: true },
      { label: 'Downloads', href: DOWNLOADS_URL, routerLink: false },
    ]
  }

  // On the app domain, marketing links point to vigilweave.com
  if (ctx === 'app') {
    return [
      { label: 'Features', href: marketingUrl('/#features'), routerLink: false },
      { label: 'Pricing', href: marketingUrl('/pricing'), routerLink: false },
      { label: 'Docs', href: marketingUrl('/docs'), routerLink: false },
      { label: 'Downloads', href: DOWNLOADS_URL, routerLink: false },
    ]
  }

  // On the marketing domain, all marketing links are internal
  return [
    { label: 'Features', href: '/#features', routerLink: false },
    { label: 'Pricing', href: '/pricing', routerLink: true },
    { label: 'Docs', href: '/docs', routerLink: true },
    { label: 'Downloads', href: DOWNLOADS_URL, routerLink: false },
  ]
}

function buildLegalLinks() {
  const ctx = getDomainContext()

  if (ctx === 'unified') {
    return [
      { label: 'Privacy', href: '/privacy', routerLink: true },
      { label: 'Terms', href: '/terms', routerLink: true },
      { label: 'Refund Policy', href: '/refund-policy', routerLink: true },
      { label: 'Licensing', href: LICENSING_URL, routerLink: false },
    ]
  }

  if (ctx === 'app') {
    return [
      { label: 'Privacy', href: marketingUrl('/privacy'), routerLink: false },
      { label: 'Terms', href: marketingUrl('/terms'), routerLink: false },
      { label: 'Refund Policy', href: marketingUrl('/refund-policy'), routerLink: false },
      { label: 'Licensing', href: LICENSING_URL, routerLink: false },
    ]
  }

  return [
    { label: 'Privacy', href: '/privacy', routerLink: true },
    { label: 'Terms', href: '/terms', routerLink: true },
    { label: 'Refund Policy', href: '/refund-policy', routerLink: true },
    { label: 'Licensing', href: LICENSING_URL, routerLink: false },
  ]
}

const navLinks = buildNavLinks()
const legalLinks = buildLegalLinks()

export function PublicLayout({ children }: PublicLayoutProps): JSX.Element {
  const [mobileOpen, setMobileOpen] = useState(false)
  const domainCtx = getDomainContext()
  const {
    bootstrapRegistrationRequired,
    isAuthenticated,
    sessionAuthProvider,
    user,
  } = useAuth()

  const primaryLink: '/setup' | '/login' | '/signup' =
    sessionAuthProvider === 'local'
      ? bootstrapRegistrationRequired
        ? '/setup'
        : '/login'
      : '/signup'
  const primaryLabel =
    sessionAuthProvider === 'local'
      ? bootstrapRegistrationRequired
        ? 'Set Up Admin'
        : 'Log In'
      : 'Get Started'

  function renderPrimaryAction(onClick?: () => void) {
    if (primaryLink === '/setup') {
      return (
        <Link to="/setup" search={{ next: undefined }} onClick={onClick}>
          {primaryLabel}
        </Link>
      )
    }

    if (primaryLink === '/login') {
      return (
        <Link
          to="/login"
          search={{ next: undefined, invite: undefined }}
          onClick={onClick}
        >
          {primaryLabel}
        </Link>
      )
    }

    return (
      <Link to="/signup" search={{ next: undefined, invite: undefined }} onClick={onClick}>
        {primaryLabel}
      </Link>
    )
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Navbar ── */}
      <header className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur-xl supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Brand */}
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-sm bg-brand-gradient flex items-center justify-center shadow-md shadow-primary/25 group-hover:shadow-primary/40 transition-shadow">
              <span className="text-white font-bold text-sm tracking-tight">VW</span>
            </div>
            <span className="font-semibold text-lg text-foreground">VigilWeave</span>
          </Link>

          {/* Desktop Nav */}
          <nav className="hidden md:flex items-center gap-1">
            {navLinks.map((link) =>
              link.routerLink ? (
                <Link
                  key={link.label}
                  to={link.href as '/pricing' | '/docs'}
                  className="px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground rounded-sm hover:bg-accent/50 transition-colors"
                >
                  {link.label}
                </Link>
              ) : (
                <a
                  key={link.label}
                  href={link.href}
                  {...(link.href.startsWith('http') ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
                  className="px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground rounded-sm hover:bg-accent/50 transition-colors"
                >
                  {link.label}
                </a>
              ),
            )}
          </nav>

          {/* Desktop Auth */}
          <div className="hidden md:flex items-center gap-3">
            <ThemeToggle />
            {isAuthenticated ? (
              <>
                <span className="text-sm text-muted-foreground truncate max-w-[180px]">
                  {user?.email}
                </span>
                {domainCtx === 'marketing' ? (
                  <Button size="sm" asChild>
                    <a href={appUrl('/projects')}>Dashboard</a>
                  </Button>
                ) : (
                  <Button size="sm" asChild>
                    <Link to="/projects">Dashboard</Link>
                  </Button>
                )}
              </>
            ) : (
              <>
                {domainCtx === 'marketing' ? (
                  <>
                    <Button variant="ghost" size="sm" className="h-9 px-4 font-medium" asChild>
                      <a href={appUrl('/login')}>Log in</a>
                    </Button>
                    <Button size="sm" className="h-9 px-4 font-medium bg-brand-gradient text-white border-0 shadow-md shadow-primary/25 hover:shadow-primary/40 transition-shadow" asChild>
                      <a href={appUrl(primaryLink)}>{primaryLabel}</a>
                    </Button>
                  </>
                ) : (
                  <>
                    <Button variant="ghost" size="sm" className="h-9 px-4 font-medium" asChild>
                      <Link to="/login" search={{ next: undefined, invite: undefined }}>
                        Log in
                      </Link>
                    </Button>
                    <Button size="sm" className="h-9 px-4 font-medium bg-brand-gradient text-white border-0 shadow-md shadow-primary/25 hover:shadow-primary/40 transition-shadow" asChild>
                      {renderPrimaryAction()}
                    </Button>
                  </>
                )}
              </>
            )}
          </div>

          {/* Mobile Hamburger */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="md:hidden p-2 rounded-sm text-muted-foreground hover:text-foreground hover:bg-accent/50"
            aria-label="Toggle menu"
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>

        {/* Mobile Menu */}
        {mobileOpen && (
          <div className="md:hidden border-t border-border/60 bg-background/95 backdrop-blur-xl">
            <div className="px-4 py-4 space-y-1">
              {navLinks.map((link) =>
                link.routerLink ? (
                  <Link
                    key={link.label}
                    to={link.href as '/pricing' | '/docs'}
                    className="block px-3 py-2.5 text-sm font-medium text-muted-foreground hover:text-foreground rounded-sm hover:bg-accent/50"
                    onClick={() => setMobileOpen(false)}
                  >
                    {link.label}
                  </Link>
                ) : (
                  <a
                    key={link.label}
                    href={link.href}
                    {...(link.href.startsWith('http') ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
                    className="block px-3 py-2.5 text-sm font-medium text-muted-foreground hover:text-foreground rounded-sm hover:bg-accent/50"
                    onClick={() => setMobileOpen(false)}
                  >
                    {link.label}
                  </a>
                ),
              )}
              <div className="pt-3 mt-3 border-t border-border/60 flex flex-col gap-2">
                {isAuthenticated ? (
                  domainCtx === 'marketing' ? (
                    <Button size="sm" asChild>
                      <a href={appUrl('/projects')} onClick={() => setMobileOpen(false)}>Dashboard</a>
                    </Button>
                  ) : (
                    <Button size="sm" asChild>
                      <Link to="/projects" onClick={() => setMobileOpen(false)}>Dashboard</Link>
                    </Button>
                  )
                ) : (
                  domainCtx === 'marketing' ? (
                    <>
                      <Button variant="ghost" size="sm" className="h-9 px-4 font-medium w-full" asChild>
                        <a href={appUrl('/login')} onClick={() => setMobileOpen(false)}>Log in</a>
                      </Button>
                      <Button size="sm" className="h-9 px-4 font-medium w-full bg-brand-gradient text-white border-0" asChild>
                        <a href={appUrl(primaryLink)} onClick={() => setMobileOpen(false)}>{primaryLabel}</a>
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button variant="ghost" size="sm" className="h-9 px-4 font-medium w-full" asChild>
                        <Link
                          to="/login"
                          search={{ next: undefined, invite: undefined }}
                          onClick={() => setMobileOpen(false)}
                        >
                          Log in
                        </Link>
                      </Button>
                      <Button size="sm" className="h-9 px-4 font-medium w-full bg-brand-gradient text-white border-0" asChild>
                        {renderPrimaryAction(() => setMobileOpen(false))}
                      </Button>
                    </>
                  )
                )}
              </div>
            </div>
          </div>
        )}
      </header>

      {/* Main content */}
      <main className="flex-1">{children}</main>

      {/* ── Footer ── */}
      <footer className="border-t border-border/60 bg-card/50">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            <div className="col-span-2 md:col-span-1">
              <div className="flex items-center gap-2.5 mb-4">
                <div className="w-7 h-7 rounded-sm bg-brand-gradient flex items-center justify-center">
                  <span className="text-white font-bold text-xs">VW</span>
                </div>
                <span className="font-semibold text-foreground">VigilWeave</span>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed max-w-xs">
                Application security platform for engineering teams. Self-hosted and cloud.
              </p>
            </div>

            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4">Product</h4>
              <ul className="space-y-2.5 text-sm">
                <li><a href="/#features" className="text-muted-foreground hover:text-foreground transition-colors">Features</a></li>
                <li><Link to="/pricing" className="text-muted-foreground hover:text-foreground transition-colors">Pricing</Link></li>
                <li><Link to="/docs" className="text-muted-foreground hover:text-foreground transition-colors">Documentation</Link></li>
                <li><a href={DOWNLOADS_URL} className="text-muted-foreground hover:text-foreground transition-colors">Downloads</a></li>
              </ul>
            </div>

            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4">Resources</h4>
              <ul className="space-y-2.5 text-sm">
                <li><a href={CONTACT_URL} className="text-muted-foreground hover:text-foreground transition-colors">Contact</a></li>
                <li><a href={CONTACT_URL} className="text-muted-foreground hover:text-foreground transition-colors">Contact</a></li>
              </ul>
            </div>

            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4">Legal</h4>
              <ul className="space-y-2.5 text-sm">
                {legalLinks.map((link) => (
                  <li key={link.label}>
                    {link.routerLink ? (
                      <Link
                        to={link.href as '/privacy' | '/terms' | '/refund-policy'}
                        className="text-muted-foreground hover:text-foreground transition-colors"
                      >
                        {link.label}
                      </Link>
                    ) : (
                      <a href={link.href} className="text-muted-foreground hover:text-foreground transition-colors">
                        {link.label}
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="mt-10 pt-6 border-t border-border/60 text-center text-xs text-muted-foreground">
            &copy; {new Date().getFullYear()} VigilWeave. Commercial software &middot; Source-available to customers and approved evaluators.
          </div>
        </div>
      </footer>
    </div>
  )
}
