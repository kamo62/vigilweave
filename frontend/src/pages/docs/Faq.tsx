import { useState } from "react";

function FaqItem({ question, answer }: { question: string; answer: string }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border border-border rounded-sm">
      <button
        type="button"
        className="w-full text-left px-4 py-3 flex items-center justify-between gap-4 hover:bg-muted/30 transition-colors"
        onClick={() => setOpen(!open)}
      >
        <span className="font-medium text-foreground text-sm">{question}</span>
        <span className="text-muted-foreground shrink-0 text-lg leading-none">
          {open ? "\u2212" : "+"}
        </span>
      </button>
      {open && (
        <div className="px-4 pb-4 text-sm text-muted-foreground">
          {answer}
        </div>
      )}
    </div>
  );
}

export function Faq() {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-foreground mb-2">Frequently Asked Questions</h2>
        <p className="text-muted-foreground">
          Answers to the most common questions about VigilWeave. Click a question to
          expand the answer.
        </p>
      </div>

      {/* General */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">General</h3>
        <div className="space-y-2">
          <FaqItem
            question="What is VigilWeave?"
            answer="VigilWeave is a unified application security platform that combines static analysis, secrets detection, dependency scanning, and infrastructure-as-code validation into a single dashboard. It provides centralized finding management, quality gates, reporting, and CI/CD integration."
          />
          <FaqItem
            question="How is VigilWeave licensed?"
            answer="VigilWeave is commercial, self-hostable software. Community binaries are available publicly for self-hosted use, while commercial source access and private images are available only to paying customers and approved evaluators under source-available terms."
          />
          <FaqItem
            question="How is VigilWeave different from running scanners individually?"
            answer="VigilWeave normalizes findings from all scan engines into a unified format, deduplicates results, provides a single triage workflow, enforces quality gates, tracks trends over time, and generates compliance-ready reports. Instead of configuring, maintaining, and correlating results from multiple scanners yourself, VigilWeave handles everything from a single deployment."
          />
        </div>
      </section>

      {/* Getting Started */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Getting Started</h3>
        <div className="space-y-2">
          <FaqItem
            question="What are the system requirements?"
            answer="VigilWeave requires Docker 24+ with Docker Compose v2, at least 4 GB of RAM, and 10 GB of disk space. For production deployments, we recommend 8 GB RAM and an external PostgreSQL database."
          />
          <FaqItem
            question="What programming languages are supported?"
            answer="VigilWeave supports 25+ programming languages for static analysis, including Python, JavaScript, TypeScript, Java, Go, Ruby, C#, Kotlin, Swift, and Rust. Dependency scanning covers all major package managers including npm, pip, Maven, Cargo, Go modules, and NuGet."
          />
          <FaqItem
            question="Can I use VigilWeave without Docker?"
            answer="The recommended deployment method is Docker Compose. However, you can run the API server and frontend directly on bare metal with Python 3.11+ and Node.js 18+. You will need to install the individual scanner tools separately and ensure they are on the system PATH."
          />
        </div>
      </section>

      {/* Scanning */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Scanning</h3>
        <div className="space-y-2">
          <FaqItem
            question="What scanning capabilities does VigilWeave include?"
            answer="VigilWeave includes four core scanning engines: SAST (static analysis across 25+ languages), Secrets Detection (full git history scanning), Infrastructure as Code validation (Terraform, CloudFormation, Kubernetes, Helm, Dockerfiles), and Dependency Analysis (CVE detection across all major package managers). All engines are built in and require no additional configuration."
          />
          <FaqItem
            question="Can I add custom scanning rules?"
            answer="Yes. VigilWeave supports custom rule definitions for static analysis and secrets detection. You can also extend the scanner plugin system to integrate any tool that produces SARIF or JSON output."
          />
          <FaqItem
            question="How long does a typical scan take?"
            answer="Scan duration depends on repository size and the number of enabled scan types. For a typical medium-sized project (10,000-50,000 lines of code), a full scan completes in 30-120 seconds. Incremental scans on changed files only typically finish in under 15 seconds."
          />
          <FaqItem
            question="Does VigilWeave scan git history for secrets?"
            answer="Yes. The secrets detection engine scans the full git commit history by default to detect secrets that may have been committed and later removed. You can configure it to scan only the current HEAD if historical scanning is not needed."
          />
        </div>
      </section>

      {/* Pricing */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Pricing</h3>
        <div className="space-y-2">
          <FaqItem
            question="What is included in the free tier?"
            answer="Community includes self-hosted deployment, built-in local user login, core scanner orchestration, built-in policy presets, SARIF export, and API keys for automation. It is intended for internal self-hosted use."
          />
          <FaqItem
            question="What does the Pro tier offer?"
            answer="Pro adds commercial hosting or commercial self-hosting options, custom policies, PDF and CSV reporting, bulk triage workflows, and commercial support."
          />
          <FaqItem
            question="What is included in the Enterprise tier?"
            answer="Enterprise pricing is custom and includes everything in Pro plus commercial identity integration, portfolio and reporting workflows, dedicated onboarding, and customer-specific support terms."
          />
          <FaqItem
            question="Is self-hosting free?"
            answer="Community binaries are free to self-host. Paid self-hosted Pro and Enterprise deployments use commercial entitlements and private distribution."
          />
        </div>
      </section>

      {/* Self-Hosting */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Self-Hosting</h3>
        <div className="space-y-2">
          <FaqItem
            question="What are the Docker requirements for self-hosting?"
            answer="You need Docker 24+ with Docker Compose v2. The worker container requires access to the Docker socket (/var/run/docker.sock) to run scanning containers. On systems where Docker socket access is restricted, you can use a rootless Docker or Podman setup."
          />
          <FaqItem
            question="How is data persisted?"
            answer="All scan data, findings, and configuration are stored in the database. Data is persisted via a Docker volume. For production use, we recommend using a managed PostgreSQL service with automated backups."
          />
          <FaqItem
            question="Can I run VigilWeave on Kubernetes?"
            answer="Yes. We provide a complete Kubernetes deployment guide with sample manifests for all components (API, Worker, Frontend, Redis), Ingress configuration, HPA autoscaling, and enterprise overlay. See the Self-Hosting documentation for details. Docker Compose is still the recommended and simplest deployment method for most teams."
          />
        </div>
      </section>

      {/* Enterprise */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Enterprise</h3>
        <div className="space-y-2">
          <FaqItem
            question="Which SSO providers are supported?"
            answer="VigilWeave supports all major identity providers including Okta, Azure Active Directory, Google Workspace, OneLogin, PingFederate, and any SAML 2.0 or OIDC-compatible provider."
          />
          <FaqItem
            question="Does VigilWeave help with compliance?"
            answer="Yes. VigilWeave provides PDF scan reports, CSV exports, audit trails for policy and waiver actions, and taxonomy-aligned findings. Broader regulatory reporting packages depend on the commercial tier you purchase."
          />
          <FaqItem
            question="Can I restrict access by team or project?"
            answer="Current deployments distinguish authenticated admins and members at the tenant level. More granular team and project RBAC is planned for future commercial releases."
          />
        </div>
      </section>
    </div>
  );
}
