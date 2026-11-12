import type { Scan } from '@/lib/api'

function scanTimestamp(scan: Scan): number {
  const value = scan.completed_at ?? scan.started_at
  const timestamp = Date.parse(value)
  return Number.isFinite(timestamp) ? timestamp : 0
}

export function pickLatestScan(scans: readonly Scan[]): Scan | null {
  let latest: Scan | null = null

  for (const scan of scans) {
    if (!latest) {
      latest = scan
      continue
    }

    const candidateTime = scanTimestamp(scan)
    const currentTime = scanTimestamp(latest)
    if (candidateTime > currentTime || (candidateTime === currentTime && scan.id > latest.id)) {
      latest = scan
    }
  }

  return latest
}
