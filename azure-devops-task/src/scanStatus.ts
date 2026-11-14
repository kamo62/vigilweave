export type PollingDecision = 'pending' | 'completed' | 'failed' | 'unexpected'

export function pollingDecision(status: string): PollingDecision {
  if (status === 'completed' || status === 'failed') return status
  if (status === 'queued' || status === 'running') return 'pending'
  return 'unexpected'
}
