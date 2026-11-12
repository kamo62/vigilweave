import type { JSX, ReactNode } from 'react'
import { Link, useLocation } from '@tanstack/react-router'

interface LegalPageShellProps {
  title: string
  summary: string
  effectiveDate: string
  children: ReactNode
}

export function LegalPageShell({
  title,
  summary,
  effectiveDate,
  children,
}: LegalPageShellProps): JSX.Element {
  const location = useLocation()
  
  return (
    <div className="mx-auto max-w-7xl px-6 py-16">
      <div className="flex gap-10">
        <aside className="hidden lg:block w-56 shrink-0">
          <div className="sticky top-24">
            <div className="flex items-center justify-between mb-3 px-2">
              <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-muted-foreground">
                Legal
              </p>
            </div>
            <nav className="space-y-0.5">
              {[
                { path: '/privacy', label: 'Privacy Policy' },
                { path: '/terms', label: 'Terms of Service' },
                { path: '/refund-policy', label: 'Refund Policy' }
              ].map((link) => {
                const isActive = location.pathname.startsWith(link.path)
                return (
                  <Link
                    key={link.path}
                    to={link.path}
                    className={`block px-2.5 py-2 text-sm rounded-sm transition-colors ${
                      isActive 
                        ? 'bg-primary/10 text-primary font-medium' 
                        : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
                    }`}
                  >
                    {link.label}
                  </Link>
                )
              })}
            </nav>
          </div>
        </aside>
        <main className="flex-1 min-w-0 max-w-4xl">
          <header className="mb-10 space-y-3 border-b border-border pb-8">
            <h1 className="text-4xl font-bold tracking-tight">{title}</h1>
            <p className="max-w-3xl text-sm leading-7 text-muted-foreground">{summary}</p>
            <p className="text-xs text-muted-foreground">Effective date: {effectiveDate}</p>
          </header>
          <div className="prose prose-neutral max-w-none dark:prose-invert prose-headings:tracking-tight prose-p:text-muted-foreground prose-li:text-muted-foreground">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
