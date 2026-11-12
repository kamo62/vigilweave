"""Initial schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260314_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("tenant_slug", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("key_prefix", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index(op.f("ix_api_keys_is_active"), "api_keys", ["is_active"], unique=False)
    op.create_index(op.f("ix_api_keys_key_hash"), "api_keys", ["key_hash"], unique=False)
    op.create_index(op.f("ix_api_keys_key_prefix"), "api_keys", ["key_prefix"], unique=False)
    op.create_index(op.f("ix_api_keys_name"), "api_keys", ["name"], unique=False)
    op.create_index(op.f("ix_api_keys_tenant_slug"), "api_keys", ["tenant_slug"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_slug", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_events_action"), "audit_events", ["action"], unique=False)
    op.create_index(op.f("ix_audit_events_actor"), "audit_events", ["actor"], unique=False)
    op.create_index(op.f("ix_audit_events_created_at"), "audit_events", ["created_at"], unique=False)
    op.create_index(op.f("ix_audit_events_entity_type"), "audit_events", ["entity_type"], unique=False)
    op.create_index(op.f("ix_audit_events_tenant_slug"), "audit_events", ["tenant_slug"], unique=False)

    op.create_table(
        "policy_profiles",
        sa.Column("tenant_slug", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("repo_pattern", sa.String(), nullable=True),
        sa.Column("branch_pattern", sa.String(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("max_critical_findings", sa.Integer(), nullable=False),
        sa.Column("max_high_findings", sa.Integer(), nullable=False),
        sa.Column("min_quality_score", sa.Float(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_policy_profiles_is_default"), "policy_profiles", ["is_default"], unique=False)
    op.create_index(op.f("ix_policy_profiles_name"), "policy_profiles", ["name"], unique=False)
    op.create_index(op.f("ix_policy_profiles_tenant_slug"), "policy_profiles", ["tenant_slug"], unique=False)

    op.create_table(
        "scans",
        sa.Column("tenant_slug", sa.String(), nullable=False),
        sa.Column("repo", sa.String(), nullable=False),
        sa.Column("branch", sa.String(), nullable=True),
        sa.Column("commit", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("scan_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("include_quality_metrics", sa.Boolean(), nullable=False),
        sa.Column("quality_gate_passed", sa.Boolean(), nullable=True),
        sa.Column("total_findings", sa.Integer(), nullable=False),
        sa.Column("critical_findings", sa.Integer(), nullable=False),
        sa.Column("high_findings", sa.Integer(), nullable=False),
        sa.Column("medium_findings", sa.Integer(), nullable=False),
        sa.Column("low_findings", sa.Integer(), nullable=False),
        sa.Column("info_findings", sa.Integer(), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("complexity_score", sa.Float(), nullable=True),
        sa.Column("maintainability_score", sa.Float(), nullable=True),
        sa.Column("style_score", sa.Float(), nullable=True),
        sa.Column("quality_grade", sa.String(), nullable=True),
        sa.Column("technical_debt_minutes", sa.Integer(), nullable=True),
        sa.Column("avg_cyclomatic_complexity", sa.Float(), nullable=True),
        sa.Column("max_cyclomatic_complexity", sa.Integer(), nullable=True),
        sa.Column("maintainability_index", sa.Float(), nullable=True),
        sa.Column("duplication_percentage", sa.Float(), nullable=True),
        sa.Column("quality_issues", sa.Integer(), nullable=False),
        sa.Column("style_issues", sa.Integer(), nullable=False),
        sa.Column("complexity_issues", sa.Integer(), nullable=False),
        sa.Column("suppressed_findings", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scan_metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scans_repo"), "scans", ["repo"], unique=False)
    op.create_index(op.f("ix_scans_scan_type"), "scans", ["scan_type"], unique=False)
    op.create_index(op.f("ix_scans_source"), "scans", ["source"], unique=False)
    op.create_index(op.f("ix_scans_status"), "scans", ["status"], unique=False)
    op.create_index(op.f("ix_scans_tenant_slug"), "scans", ["tenant_slug"], unique=False)

    op.create_table(
        "waivers",
        sa.Column("tenant_slug", sa.String(), nullable=False),
        sa.Column("repo_pattern", sa.String(), nullable=True),
        sa.Column("branch_pattern", sa.String(), nullable=True),
        sa.Column("rule_id", sa.String(), nullable=True),
        sa.Column("fingerprint", sa.String(), nullable=True),
        sa.Column("file_path", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_waivers_category"), "waivers", ["category"], unique=False)
    op.create_index(op.f("ix_waivers_fingerprint"), "waivers", ["fingerprint"], unique=False)
    op.create_index(op.f("ix_waivers_is_active"), "waivers", ["is_active"], unique=False)
    op.create_index(op.f("ix_waivers_rule_id"), "waivers", ["rule_id"], unique=False)
    op.create_index(op.f("ix_waivers_tenant_slug"), "waivers", ["tenant_slug"], unique=False)

    op.create_table(
        "file_metrics",
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("lines_of_code", sa.Integer(), nullable=False),
        sa.Column("cyclomatic_complexity", sa.Integer(), nullable=False),
        sa.Column("maintainability_index", sa.Float(), nullable=False),
        sa.Column("duplication_percentage", sa.Float(), nullable=False),
        sa.Column("line_coverage", sa.Float(), nullable=True),
        sa.Column("linting_errors", sa.Integer(), nullable=False),
        sa.Column("linting_warnings", sa.Integer(), nullable=False),
        sa.Column("style_violations", sa.Integer(), nullable=False),
        sa.Column("technical_debt_minutes", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_file_metrics_file_path"), "file_metrics", ["file_path"], unique=False)
    op.create_index(op.f("ix_file_metrics_language"), "file_metrics", ["language"], unique=False)
    op.create_index(op.f("ix_file_metrics_scan_id"), "file_metrics", ["scan_id"], unique=False)

    op.create_table(
        "findings",
        sa.Column("tool", sa.String(), nullable=False),
        sa.Column("identifier", sa.String(), nullable=True),
        sa.Column("scan_source", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=True),
        sa.Column("line", sa.Integer(), nullable=True),
        sa.Column("column", sa.Integer(), nullable=True),
        sa.Column("rule_id", sa.String(), nullable=True),
        sa.Column("cwe_id", sa.String(), nullable=True),
        sa.Column("owasp_category", sa.String(), nullable=True),
        sa.Column("confidence", sa.String(), nullable=True),
        sa.Column("fingerprint", sa.String(), nullable=False),
        sa.Column("is_suppressed", sa.Boolean(), nullable=False),
        sa.Column("suppression_reason", sa.String(), nullable=True),
        sa.Column("waiver_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.Integer(), nullable=False),
        sa.Column("tool_metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["waiver_id"], ["waivers.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_findings_category"), "findings", ["category"], unique=False)
    op.create_index(op.f("ix_findings_fingerprint"), "findings", ["fingerprint"], unique=False)
    op.create_index(op.f("ix_findings_identifier"), "findings", ["identifier"], unique=False)
    op.create_index(op.f("ix_findings_is_suppressed"), "findings", ["is_suppressed"], unique=False)
    op.create_index(op.f("ix_findings_rule_id"), "findings", ["rule_id"], unique=False)
    op.create_index(op.f("ix_findings_scan_id"), "findings", ["scan_id"], unique=False)
    op.create_index(op.f("ix_findings_scan_source"), "findings", ["scan_source"], unique=False)
    op.create_index(op.f("ix_findings_severity"), "findings", ["severity"], unique=False)
    op.create_index(op.f("ix_findings_tool"), "findings", ["tool"], unique=False)
    op.create_index(op.f("ix_findings_waiver_id"), "findings", ["waiver_id"], unique=False)

    op.create_table(
        "tool_executions",
        sa.Column("tool", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("findings_count", sa.Integer(), nullable=False),
        sa.Column("stdout_summary", sa.String(), nullable=True),
        sa.Column("stderr_summary", sa.String(), nullable=True),
        sa.Column("version", sa.String(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tool_executions_scan_id"), "tool_executions", ["scan_id"], unique=False)
    op.create_index(op.f("ix_tool_executions_status"), "tool_executions", ["status"], unique=False)
    op.create_index(op.f("ix_tool_executions_tool"), "tool_executions", ["tool"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tool_executions_tool"), table_name="tool_executions")
    op.drop_index(op.f("ix_tool_executions_status"), table_name="tool_executions")
    op.drop_index(op.f("ix_tool_executions_scan_id"), table_name="tool_executions")
    op.drop_table("tool_executions")

    op.drop_index(op.f("ix_findings_waiver_id"), table_name="findings")
    op.drop_index(op.f("ix_findings_tool"), table_name="findings")
    op.drop_index(op.f("ix_findings_severity"), table_name="findings")
    op.drop_index(op.f("ix_findings_scan_source"), table_name="findings")
    op.drop_index(op.f("ix_findings_scan_id"), table_name="findings")
    op.drop_index(op.f("ix_findings_rule_id"), table_name="findings")
    op.drop_index(op.f("ix_findings_is_suppressed"), table_name="findings")
    op.drop_index(op.f("ix_findings_identifier"), table_name="findings")
    op.drop_index(op.f("ix_findings_fingerprint"), table_name="findings")
    op.drop_index(op.f("ix_findings_category"), table_name="findings")
    op.drop_table("findings")

    op.drop_index(op.f("ix_file_metrics_scan_id"), table_name="file_metrics")
    op.drop_index(op.f("ix_file_metrics_language"), table_name="file_metrics")
    op.drop_index(op.f("ix_file_metrics_file_path"), table_name="file_metrics")
    op.drop_table("file_metrics")

    op.drop_index(op.f("ix_waivers_tenant_slug"), table_name="waivers")
    op.drop_index(op.f("ix_waivers_rule_id"), table_name="waivers")
    op.drop_index(op.f("ix_waivers_is_active"), table_name="waivers")
    op.drop_index(op.f("ix_waivers_fingerprint"), table_name="waivers")
    op.drop_index(op.f("ix_waivers_category"), table_name="waivers")
    op.drop_table("waivers")

    op.drop_index(op.f("ix_scans_tenant_slug"), table_name="scans")
    op.drop_index(op.f("ix_scans_status"), table_name="scans")
    op.drop_index(op.f("ix_scans_source"), table_name="scans")
    op.drop_index(op.f("ix_scans_scan_type"), table_name="scans")
    op.drop_index(op.f("ix_scans_repo"), table_name="scans")
    op.drop_table("scans")

    op.drop_index(op.f("ix_policy_profiles_tenant_slug"), table_name="policy_profiles")
    op.drop_index(op.f("ix_policy_profiles_name"), table_name="policy_profiles")
    op.drop_index(op.f("ix_policy_profiles_is_default"), table_name="policy_profiles")
    op.drop_table("policy_profiles")

    op.drop_index(op.f("ix_audit_events_tenant_slug"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_entity_type"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_created_at"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_actor"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_action"), table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index(op.f("ix_api_keys_tenant_slug"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_name"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_key_prefix"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_key_hash"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_is_active"), table_name="api_keys")
    op.drop_table("api_keys")
