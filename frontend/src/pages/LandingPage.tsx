import { useNavigate } from '@tanstack/react-router'
import { Button, Card, Chip } from '@heroui/react'
import { motion, type Variants } from 'framer-motion'
import { Shield, Target, BarChart3, Bot, Github, Cloud, Code2, Search, TerminalSquare } from 'lucide-react'

import { getDomainContext, appUrl } from '../lib/domain'
import { DOWNLOADS_URL, SALES_EMAIL_URL } from '../lib/public-links'
import { useAuth } from '../lib/useAuth'

/* ── Animation presets ── */
const rise: Variants = {
  hidden: { opacity: 0, y: 30 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] } },
}

const stagger: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.12 } },
}

/* ── Data ── */
const products = [
  {
    icon: Shield,
    name: 'VigilWeave Scan',
    hook: 'Comprehensive security scanning, one dashboard',
    body: 'Run SAST, secrets detection, SCA, and IaC validation in a single pass. Unified SARIF output with de-duplication and severity mapping.',
    accent: 'from-primary/20 to-primary/5',
    ring: 'group-hover:ring-primary/30',
  },
  {
    icon: Target,
    name: 'VigilWeave Policy',
    hook: 'Quality gates that enforce standards',
    body: 'Define pass/fail criteria with lenient, balanced, or strict presets. Block merges that violate your security posture.',
    accent: 'from-primary/20 to-primary/5',
    ring: 'group-hover:ring-primary/30',
  },
  {
    icon: BarChart3,
    name: 'VigilWeave Reports',
    hook: 'PDF reports your CISO will love',
    body: 'Executive summaries, trend charts, and compliance matrices. Export to PDF, CSV, or SARIF for downstream tooling.',
    accent: 'from-cyan-500/20 to-cyan-500/5',
    ring: 'group-hover:ring-cyan-500/30',
  },
  {
    icon: Bot,
    name: 'VigilWeave MCP',
    hook: 'AI-assisted security triage',
    body: 'Model Context Protocol integration lets AI agents query findings, suggest fixes, and auto-triage false positives.',
    accent: 'from-fuchsia-500/20 to-fuchsia-500/5',
    ring: 'group-hover:ring-fuchsia-500/30',
  },
]

const integrations = [
  { name: 'GitHub', icon: Github },
  { name: 'Azure DevOps', icon: Cloud },
  { name: 'VS Code', icon: Code2 },
  { name: 'Prisma Cloud', icon: Shield },
  { name: 'SonarQube', icon: Search },
]

const stats = [
  { value: '25+', label: 'Languages' },
  { value: '5', label: 'Scan Engines' },
  { value: '5 min', label: 'Setup Time' },
]

const terminalLines = [
  { text: '$ vigilweave scan ./my-app', cls: 'text-[var(--code-command)]' },
  { text: '', cls: '' },
  { text: '  Scanning ./my-app...', cls: 'text-[var(--code-output)]' },
  { text: '  Running SAST analysis........ done', cls: 'text-[var(--code-output)]' },
  { text: '  Detecting secrets............ done', cls: 'text-[var(--code-output)]' },
  { text: '  Scanning dependencies........ done', cls: 'text-[var(--code-output)]' },
  { text: '', cls: '' },
  { text: '  3 critical  12 high  45 medium findings', cls: 'text-[var(--code-highlight)]' },
  { text: '  Report saved to vigilweave.sarif', cls: 'text-[var(--code-command)]' },
]

export function LandingPage() {
  const { bootstrapRegistrationRequired, isAuthenticated, login, sessionAuthProvider } = useAuth()
  const navigate = useNavigate()
  const domainCtx = getDomainContext()
  const primaryAuthPath =
    sessionAuthProvider === 'local'
      ? bootstrapRegistrationRequired
        ? '/setup'
        : '/login'
      : '/signup'

  return (
    <div className="flex flex-col overflow-hidden">

      {/* ━━━ Hero ━━━ */}
      <section className="relative isolate min-h-[90vh] flex items-center justify-center">
        {/* Gradient backdrop */}
        <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_80%_60%_at_50%_-10%,oklch(0.45_0.18_275/0.35),transparent)]" />
        <div className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-b from-background via-background to-card" />

        <motion.div
          className="relative max-w-3xl mx-auto px-6 py-32 text-center"
          initial="hidden"
          animate="show"
          variants={stagger}
        >
          <motion.div variants={rise} className="mb-8">
            <Chip color="accent" variant="secondary" size="sm" className="border border-primary/30 bg-primary/10 text-primary">
              <span className="relative flex h-2 w-2 mr-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-60" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
              </span>
              Now in Public Beta
            </Chip>
          </motion.div>

          <motion.h1
            variants={rise}
            className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-extrabold tracking-tight leading-[1.08] mb-6"
          >
            Weave security into{' '}
            <span className="text-brand-gradient">
              every line of code
            </span>
          </motion.h1>

          <motion.p variants={rise} className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-10 leading-relaxed">
            SAST, secrets, SCA, IaC scanning plus quality gates and reporting — in one platform you can self-host or run in the cloud.
          </motion.p>

          <motion.div variants={rise} className="flex flex-col sm:flex-row gap-3 justify-center">
            {isAuthenticated ? (
              <Button
                variant="primary"
                size="lg"
                onPress={() => domainCtx === 'marketing' ? window.location.assign(appUrl('/projects')) : navigate({ to: '/projects' })}
              >
                Go to Dashboard
              </Button>
            ) : (
              <>
                <Button
                  variant="primary"
                  size="lg"
                  onPress={() => domainCtx === 'marketing' ? window.location.assign(appUrl(primaryAuthPath)) : login()}
                  className="shadow-lg shadow-primary/25 hover:shadow-primary/40 transition-shadow"
                >
                  Start Free on Cloud
                </Button>
                <Button
                  variant="outline"
                  size="lg"
                  onPress={() => window.open(DOWNLOADS_URL, '_blank')}
                >
                  Download Community
                </Button>
              </>
            )}
          </motion.div>
        </motion.div>
      </section>

      {/* ━━━ Product Showcase ━━━ */}
      <section id="features" className="py-24 bg-card/50">
        <div className="max-w-6xl mx-auto px-6">
          <motion.div
            initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.2 }}
            variants={rise}
            className="text-center mb-16"
          >
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              Everything you need for code security
            </h2>
            <p className="text-muted-foreground max-w-2xl mx-auto">
              Four products, one platform. From scanning to compliance, VigilWeave covers the full security lifecycle.
            </p>
          </motion.div>

          <motion.div
            className="grid grid-cols-1 md:grid-cols-2 gap-5"
            initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.15 }}
            variants={stagger}
          >
            {products.map((p) => (
              <motion.div key={p.name} variants={rise} className="group">
                <Card className={`relative h-full ring-1 ring-transparent ${p.ring} transition-all duration-300 hover:shadow-lg`}>
                  <div className={`absolute inset-0 rounded-sm bg-gradient-to-br ${p.accent} opacity-0 group-hover:opacity-100 transition-opacity duration-300`} />
                  <Card.Content className="relative">
                    <div className="flex gap-4">
                      <div className="shrink-0 mt-0.5">
                        <div className="w-10 h-10 rounded-sm bg-primary/10 flex items-center justify-center">
                          <p.icon className="w-5 h-5 text-primary" />
                        </div>
                      </div>
                      <div>
                        <Card.Title className="font-bold text-base">{p.name}</Card.Title>
                        <p className="text-sm font-medium text-primary mb-2">{p.hook}</p>
                        <Card.Description>{p.body}</Card.Description>
                      </div>
                    </div>
                  </Card.Content>
                </Card>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ━━━ Integrations ━━━ */}
      <section className="py-16 border-y border-border/40">
        <div className="max-w-5xl mx-auto px-6 text-center">
          <motion.div
            initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.3 }}
            variants={rise}
          >
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground mb-8">
              Works with your stack
            </p>
            <div className="flex flex-wrap justify-center items-center gap-x-10 gap-y-4">
              {integrations.map((i) => (
                <div
                  key={i.name}
                  className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  <i.icon className="w-4 h-4" />
                  <span className="text-sm font-medium">{i.name}</span>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* ━━━ Stats ━━━ */}
      <section className="py-20">
        <motion.div
          className="max-w-3xl mx-auto px-6 grid grid-cols-3 gap-8 text-center"
          initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.3 }}
          variants={stagger}
        >
          {stats.map((s) => (
            <motion.div key={s.label} variants={rise}>
              <div className="text-4xl sm:text-5xl md:text-6xl font-extrabold text-brand-gradient mb-1">
                {s.value}
              </div>
              <p className="text-sm text-muted-foreground font-medium">{s.label}</p>
            </motion.div>
          ))}
        </motion.div>
      </section>

      {/* ━━━ Pricing Preview ━━━ */}
      <section className="py-24 bg-card/50">
        <div className="max-w-5xl mx-auto px-6">
          <motion.div
            initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.2 }}
            variants={rise}
            className="text-center mb-14"
          >
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Simple, transparent pricing</h2>
            <p className="text-muted-foreground max-w-xl mx-auto">
              Start free with the self-hosted Community edition. Upgrade when you need cloud hosting, commercial support, or enterprise controls.
            </p>
          </motion.div>

          <motion.div
            className="grid grid-cols-1 md:grid-cols-3 gap-6"
            initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.15 }}
            variants={stagger}
          >
            {/* Community */}
            <motion.div variants={rise}>
              <Card className="h-full">
                <Card.Header>
                  <Card.Title className="text-lg font-bold">Community</Card.Title>
                  <div className="text-3xl font-extrabold">Free</div>
                  <Card.Description>Self-hosted, forever</Card.Description>
                </Card.Header>
                <Card.Content>
                  <ul className="space-y-2.5 mb-6 text-sm text-muted-foreground">
                    {['Unlimited projects', 'All scan engines', 'SARIF export', 'Self-hosted'].map((f) => (
                      <li key={f} className="flex items-center gap-2">
                        <span className="text-success text-xs">&#10003;</span> {f}
                      </li>
                    ))}
                  </ul>
                </Card.Content>
                <Card.Footer>
                  <Button
                    variant="outline"
                    fullWidth
                    onPress={() => window.open(DOWNLOADS_URL, '_blank')}
                  >
                    Download
                  </Button>
                </Card.Footer>
              </Card>
            </motion.div>

            {/* Pro */}
            <motion.div variants={rise}>
              <Card className="h-full border-2 border-primary shadow-lg shadow-primary/10 relative">
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 z-10">
                  <Chip variant="primary" size="sm" className="bg-primary text-primary-foreground dark:text-white dark:border dark:border-primary/50 shadow-sm">
                    Most Popular
                  </Chip>
                </div>
                <Card.Header className="pt-5">
                  <Card.Title className="text-lg font-bold">Pro</Card.Title>
                  <div className="text-3xl font-extrabold">
                    $69<span className="text-sm font-normal text-muted-foreground">/dev/yr</span>
                  </div>
                  <Card.Description>Teams shipping to production</Card.Description>
                </Card.Header>
                <Card.Content>
                  <ul className="space-y-2.5 mb-6 text-sm text-muted-foreground">
                    {['Everything in Community', 'PDF reports & CSV', 'Bulk triage', 'Custom policies', 'Cloud hosting'].map((f) => (
                      <li key={f} className="flex items-center gap-2">
                        <span className="text-success text-xs">&#10003;</span> {f}
                      </li>
                    ))}
                  </ul>
                </Card.Content>
                <Card.Footer>
                  <Button variant="primary" fullWidth onPress={() => domainCtx === 'marketing' ? window.location.assign(appUrl(primaryAuthPath)) : login()}>
                    Start Free Trial
                  </Button>
                </Card.Footer>
              </Card>
            </motion.div>

            {/* Enterprise */}
            <motion.div variants={rise}>
              <Card className="h-full">
                <Card.Header>
                  <Card.Title className="text-lg font-bold">Enterprise</Card.Title>
                  <div className="text-3xl font-extrabold">Custom</div>
                  <Card.Description>Large organisations</Card.Description>
                </Card.Header>
                <Card.Content>
                  <ul className="space-y-2.5 mb-6 text-sm text-muted-foreground">
                    {['Everything in Pro', 'SSO / SAML', 'Portfolio management', 'Compliance reports', 'Dedicated support'].map((f) => (
                      <li key={f} className="flex items-center gap-2">
                        <span className="text-success text-xs">&#10003;</span> {f}
                      </li>
                    ))}
                  </ul>
                </Card.Content>
                <Card.Footer>
                  <Button
                    variant="outline"
                    fullWidth
                    onPress={() => window.open(SALES_EMAIL_URL)}
                  >
                    Contact Sales
                  </Button>
                </Card.Footer>
              </Card>
            </motion.div>
          </motion.div>

          <motion.div
            initial="hidden" whileInView="show" viewport={{ once: true }}
            variants={rise}
            className="text-center mt-12 mb-4"
          >
            <Button
              variant="ghost"
              onPress={() => navigate({ to: '/pricing' })}
              className="text-primary font-medium"
            >
              View full comparison &rarr;
            </Button>
          </motion.div>
        </div>
      </section>

      {/* ━━━ Developer Experience ━━━ */}
      <section className="py-24">
        <div className="max-w-3xl mx-auto px-6">
          <motion.div
            initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.2 }}
            variants={rise}
            className="text-center mb-10"
          >
            <h2 className="text-3xl md:text-4xl font-bold mb-3">Developer-first experience</h2>
            <p className="text-muted-foreground">One command. Full security audit. Zero config.</p>
          </motion.div>

          <motion.div
            initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.3 }}
            variants={rise}
          >
            <Card className="overflow-hidden shadow-xl shadow-black/5">
              {/* Title bar */}
              <div className="flex items-center gap-2 px-4 py-3 bg-muted/30 border-b border-border/60">
                <div className="flex gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-full bg-destructive/60" />
                  <div className="w-2.5 h-2.5 rounded-full bg-warning/60" />
                  <div className="w-2.5 h-2.5 rounded-full bg-success/60" />
                </div>
                <div className="flex items-center gap-1.5 ml-2 text-xs text-muted-foreground">
                  <TerminalSquare className="w-3 h-3" />
                  <span className="font-mono">vigilweave CLI</span>
                </div>
              </div>
              {/* CLI output */}
              <Card.Content className="p-5 bg-[var(--code-bg)]">
                <pre className="font-mono text-sm leading-[1.8]">
                  {terminalLines.map((line, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0 }}
                      whileInView={{ opacity: 1 }}
                      viewport={{ once: true }}
                      transition={{ delay: idx * 0.18, duration: 0.25 }}
                      className={line.cls || 'h-5'}
                    >
                      {line.text || '\u00A0'}
                    </motion.div>
                  ))}
                </pre>
              </Card.Content>
            </Card>
          </motion.div>
        </div>
      </section>

      {/* ━━━ Final CTA ━━━ */}
      <section className="relative isolate py-24">
        <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_80%_50%_at_50%_110%,oklch(0.45_0.18_275/0.25),transparent)]" />

        <motion.div
          className="max-w-2xl mx-auto px-6 text-center"
          initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.3 }}
          variants={stagger}
        >
          <motion.h2 variants={rise} className="text-3xl md:text-5xl font-bold mb-5">
            Ready to ship secure code?
          </motion.h2>
          <motion.p variants={rise} className="text-lg text-muted-foreground mb-10 max-w-lg mx-auto">
            Join developers who trust VigilWeave to catch security issues before they reach production.
          </motion.p>
          <motion.div variants={rise} className="flex flex-col sm:flex-row gap-3 justify-center">
            {isAuthenticated ? (
              <Button
                variant="primary"
                size="lg"
                onPress={() => domainCtx === 'marketing' ? window.location.assign(appUrl('/projects')) : navigate({ to: '/projects' })}
              >
                Go to Dashboard
              </Button>
            ) : (
              <>
                <Button
                  variant="primary"
                  size="lg"
                  onPress={() => domainCtx === 'marketing' ? window.location.assign(appUrl(primaryAuthPath)) : login()}
                  className="shadow-lg shadow-primary/25"
                >
                  Get Started Free
                </Button>
                <Button
                  variant="outline"
                  size="lg"
                  onPress={() => navigate({ to: '/pricing' })}
                >
                  View Pricing
                </Button>
              </>
            )}
          </motion.div>
        </motion.div>
      </section>
    </div>
  )
}
