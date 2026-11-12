export function ReportsAnalytics() {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-foreground mb-2">Reports &amp; Analytics</h2>
        <p className="text-muted-foreground">
          VigilWeave provides reporting and export workflows to help teams review
          scan results, share findings with stakeholders, and preserve an audit
          trail for follow-up work.
        </p>
      </div>

      {/* PDF Reports */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">PDF Report Generation</h3>
        <p className="text-muted-foreground">
          Generate professional PDF reports from any scan. Reports
          include an executive summary, finding breakdown by severity, detailed
          finding descriptions, and remediation guidance.
        </p>
        <div className="code-block">
          <pre>{`# Generate a PDF report for a specific scan
curl -X GET http://localhost:8000/api/v1/scans/{scan_id}/report/pdf \\
  -H "Authorization: Bearer YOUR_API_KEY_HERE" \\
  -o scan-report.pdf
`}</pre>
        </div>
        <p className="text-sm text-muted-foreground">
          PDF reports can also be generated from the UI by clicking the
          &ldquo;Download Report&rdquo; button on a scan detail page.
        </p>
      </section>

      {/* CSV / Excel Export */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">CSV Export</h3>
        <p className="text-muted-foreground">
          Export raw finding data for further analysis in spreadsheets, BI tools, or
          custom scripts. CSV exports are generated per scan with the same filters
          used in the UI.
        </p>
        <div className="code-block">
          <pre>{`# Export findings as CSV
curl -X GET "http://localhost:8000/api/v1/scans/{scan_id}/findings/export" \\
  -H "Authorization: Bearer YOUR_API_KEY_HERE" \\
  -o findings.csv`}</pre>
        </div>
        <p className="text-sm text-muted-foreground">
          Exported data includes finding ID, title, severity, status, tool, file
          path, line number, CWE ID, and timestamps.
        </p>
      </section>

      {/* Dashboard Insights */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Dashboard Insights</h3>
        <p className="text-muted-foreground">
          The dashboard surfaces current scan health and finding summaries so
          teams can quickly spot hotspots and prioritize remediation.
        </p>
        <ul className="list-disc list-inside space-y-1 text-muted-foreground">
          <li>
            <strong>Severity overview</strong> &mdash; Current critical, high,
            medium, and low finding counts for the latest scans.
          </li>
          <li>
            <strong>Project health snapshots</strong> &mdash; Quality scores,
            gate outcomes, and open findings across tracked projects.
          </li>
          <li>
            <strong>Triage state</strong> &mdash; Visibility into open, confirmed,
            waived, false-positive, and fixed finding states.
          </li>
        </ul>
      </section>

      {/* Mapping and Audit Context */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Mapping and Audit Context</h3>
        <p className="text-muted-foreground">
          VigilWeave carries taxonomy and audit metadata alongside findings so
          teams can prepare downstream reporting and review workflows.
        </p>

        <div className="space-y-4">
          <div className="rounded-sm border border-border p-4 space-y-1">
            <h4 className="font-semibold text-foreground">OWASP Top 10</h4>
            <p className="text-sm text-muted-foreground">
              Findings can be associated with OWASP-style categories to help
              security reviewers understand where common weaknesses cluster.
            </p>
          </div>

          <div className="rounded-sm border border-border p-4 space-y-1">
            <h4 className="font-semibold text-foreground">CWE Mapping</h4>
            <p className="text-sm text-muted-foreground">
              Every finding is tagged with its Common Weakness Enumeration (CWE) ID
              where applicable. Filter and group findings by CWE to understand
              recurring weakness patterns across scans.
            </p>
          </div>

          <div className="rounded-sm border border-border p-4 space-y-1">
            <h4 className="font-semibold text-foreground">Audit Trail</h4>
            <p className="text-sm text-muted-foreground">
              Policy changes, waiver actions, and scan activity can be reviewed
              later to support internal security reviews and customer reporting.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
