"""SARIF export helpers."""

from collections import OrderedDict
from typing import Any

from sqlmodel import Session, select

from app.models import Finding, Scan, ScanStatus


def export_scan_to_sarif(session: Session, scan_id: int) -> dict:
    """Export a scan to SARIF 2.1.0."""

    scan = session.get(Scan, scan_id)
    if scan is None:
        raise ValueError(f"Scan {scan_id} not found")
    findings = session.exec(
        select(Finding).where(Finding.scan_id == scan_id, Finding.is_suppressed.is_(False))
    ).all()
    rules = _build_rules(findings)

    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "VigilWeave",
                        "semanticVersion": "1.0.0",
                        "informationUri": "https://vigilweave.com",
                        "rules": list(rules.values()),
                    }
                },
                "taxonomies": _build_taxonomies(findings),
                "results": [
                    {
                        "ruleId": finding.rule_id or finding.fingerprint,
                        "level": _sarif_level(finding.severity),
                        "message": {"text": finding.message},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": finding.file_path or "unknown"},
                                    "region": {
                                        "startLine": finding.line or 1,
                                        "startColumn": finding.column or 1,
                                    },
                                }
                            }
                        ],
                        "fingerprints": {
                            "primaryLocationLineHash": finding.fingerprint,
                        },
                        "partialFingerprints": {
                            "primaryLocationLineHash": finding.fingerprint,
                        },
                        "properties": _result_properties(finding),
                    }
                    for finding in findings
                ],
                "invocations": [
                    {
                        "executionSuccessful": scan.status == ScanStatus.COMPLETED,
                    }
                ],
            }
        ],
    }


def _build_rules(findings: list[Finding]) -> OrderedDict[str, dict[str, Any]]:
    rules: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for finding in findings:
        rule_id = finding.rule_id or finding.fingerprint
        if rule_id in rules:
            continue
        rules[rule_id] = {
            "id": rule_id,
            "name": finding.title,
            "shortDescription": {"text": finding.title},
            "fullDescription": {"text": finding.description or finding.message},
            "helpUri": _help_uri(finding),
            "properties": _rule_properties(finding),
            "relationships": _rule_relationships(finding),
        }
    return rules


def _build_taxonomies(findings: list[Finding]) -> list[dict[str, Any]]:
    cwe_taxa = []
    owasp_taxa = []
    seen_cwe: set[str] = set()
    seen_owasp: set[str] = set()
    for finding in findings:
        if finding.cwe_id and finding.cwe_id not in seen_cwe:
            seen_cwe.add(finding.cwe_id)
            cwe_taxa.append(
                {
                    "id": finding.cwe_id,
                    "name": f"CWE-{finding.cwe_id}",
                    "shortDescription": {"text": f"CWE-{finding.cwe_id}"},
                }
            )
        if finding.owasp_category and finding.owasp_category not in seen_owasp:
            seen_owasp.add(finding.owasp_category)
            owasp_taxa.append(
                {
                    "id": finding.owasp_category,
                    "name": finding.owasp_category,
                    "shortDescription": {"text": finding.owasp_category},
                }
            )

    taxonomies: list[dict[str, Any]] = []
    if cwe_taxa:
        taxonomies.append(
            {
                "name": "CWE",
                "organization": "MITRE",
                "shortDescription": {"text": "Common Weakness Enumeration"},
                "taxa": cwe_taxa,
            }
        )
    if owasp_taxa:
        taxonomies.append(
            {
                "name": "OWASP",
                "organization": "OWASP Foundation",
                "shortDescription": {"text": "OWASP categories referenced by findings"},
                "taxa": owasp_taxa,
            }
        )
    return taxonomies


def _rule_properties(finding: Finding) -> dict[str, Any]:
    tags = [finding.category, finding.tool, finding.scan_source]
    if finding.cwe_id:
        tags.append(f"cwe:{finding.cwe_id}")
    if finding.owasp_category:
        tags.append(f"owasp:{finding.owasp_category}")
    return {
        "category": finding.category,
        "tags": [tag for tag in tags if tag],
        "precision": finding.confidence,
        "security-severity": _security_severity(finding.severity),
    }


def _rule_relationships(finding: Finding) -> list[dict[str, Any]]:
    relationships: list[dict[str, Any]] = []
    if finding.cwe_id:
        relationships.append(
            {
                "target": {
                    "id": finding.cwe_id,
                    "toolComponent": {"name": "CWE"},
                },
                "kinds": ["relevant"],
            }
        )
    if finding.owasp_category:
        relationships.append(
            {
                "target": {
                    "id": finding.owasp_category,
                    "toolComponent": {"name": "OWASP"},
                },
                "kinds": ["relevant"],
            }
        )
    return relationships


def _result_properties(finding: Finding) -> dict[str, Any]:
    properties = {
        "category": finding.category,
        "tool": finding.tool,
        "scanSource": finding.scan_source,
        "tags": _rule_properties(finding)["tags"],
    }
    if finding.cwe_id:
        properties["cweId"] = finding.cwe_id
    if finding.owasp_category:
        properties["owaspCategory"] = finding.owasp_category
    if finding.confidence:
        properties["precision"] = finding.confidence
    return properties


def _help_uri(finding: Finding) -> str | None:
    description = finding.description or ""
    if description.startswith("http://") or description.startswith("https://"):
        return description
    tool_metadata = finding.tool_metadata or {}
    for key in ("source-rule-url", "more_info", "guideline"):
        value = tool_metadata.get(key)
        if isinstance(value, str) and (value.startswith("http://") or value.startswith("https://")):
            return value
    return None


def _security_severity(severity: str) -> str:
    mapping = {
        "Critical": "9.0",
        "High": "8.0",
        "Medium": "5.5",
        "Low": "3.0",
        "Info": "0.0",
    }
    return mapping.get(str(severity), "0.0")


def _sarif_level(severity: str) -> str:
    mapping = {
        "Critical": "error",
        "High": "error",
        "Medium": "warning",
        "Low": "note",
        "Info": "note",
    }
    return mapping.get(severity, "warning")
