export interface IdeFile {
  path: string
  content: string
}

export interface IdeFinding {
  id: number
  scan_id: number
  tool: string
  severity: 'Critical' | 'High' | 'Medium' | 'Low' | 'Info'
  title: string
  message: string
  description?: string | null
  category: string
  file_path?: string | null
  line?: number | null
  column?: number | null
}

export interface IdeScanResponse {
  scan: { id: number } | null
  findings: IdeFinding[]
  severities: Record<string, number>
}
