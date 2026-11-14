export type ScanStatus = 'queued' | 'running' | 'completed' | 'failed'

export type FindingSeverity = 'Critical' | 'High' | 'Medium' | 'Low' | 'Info'

export interface ScanCreatePayload {
  repo: string
  project_key?: string
  branch?: string
  commit?: string
  scan_type: 'comprehensive' | 'fast' | 'security-only' | 'custom'
  include_quality_metrics: boolean
  tools?: string[]
}

export interface ScanResponse {
  id: number
  repo: string
  branch?: string | null
  commit?: string | null
  status: string
  scan_type: string
  quality_gate_passed?: boolean | null
  total_findings: number
  critical_findings: number
  high_findings: number
  medium_findings: number
  low_findings: number
  info_findings: number
  suppressed_findings: number
  tool_executions?: Array<{
    tool: string
    status: string
    stdout_summary?: string | null
    stderr_summary?: string | null
  }>
}

export interface FindingStats {
  total_findings: number
  critical_findings: number
  high_findings: number
  medium_findings: number
  low_findings: number
  info_findings: number
  by_category: Record<string, number>
  by_tool: Record<string, number>
}

export interface GateEvaluation {
  passed: boolean
  reasons: string[]
}
