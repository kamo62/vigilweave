import type { FindingStats, ScanCreatePayload, ScanResponse } from './types'

const REQUEST_TIMEOUT_MS = 30_000

export class VigilWeaveClient {
  constructor(
    private readonly baseUrl: string,
    private readonly apiKey: string,
  ) {}

  async createScan(payload: ScanCreatePayload): Promise<ScanResponse> {
    return this.request('/api/v1/scans/', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  }

  async getScan(scanId: number): Promise<ScanResponse> {
    return this.request(`/api/v1/scans/${scanId}`)
  }

  async getStats(scanId: number): Promise<FindingStats> {
    return this.request(`/api/v1/scans/${scanId}/findings/stats`)
  }

  async getSarif(scanId: number): Promise<unknown> {
    return this.request(`/api/v1/scans/${scanId}/sarif`)
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(new URL(path, this.baseUrl), {
      ...init,
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${this.apiKey}`,
        ...(init.headers ?? {}),
      },
    })
    if (!response.ok) {
      throw new Error(`VigilWeave request failed (${response.status} ${response.statusText})`)
    }
    return (await response.json()) as T
  }
}
