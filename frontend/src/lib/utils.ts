import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...values: ClassValue[]) {
  return twMerge(clsx(values))
}

export function normalizeSeverity(value: string) {
  const lower = value.toLowerCase()
  if (lower === 'critical') return 'Critical'
  if (lower === 'high') return 'High'
  if (lower === 'medium') return 'Medium'
  if (lower === 'low') return 'Low'
  return 'Info'
}

export function formatMinutes(value: number | null | undefined) {
  if (!value) return '0m'
  if (value < 60) return `${value}m`
  const hours = Math.floor(value / 60)
  const minutes = value % 60
  return minutes ? `${hours}h ${minutes}m` : `${hours}h`
}

export function qualityTone(score: number | null | undefined) {
  if (score === null || score === undefined) return 'default'
  if (score >= 80) return 'success'
  if (score >= 60) return 'default'
  return 'danger'
}

export type LetterGrade = 'A' | 'B' | 'C' | 'D' | 'E'

export function qualityGrade(score: number | null | undefined): LetterGrade {
  if (score === null || score === undefined) return 'E'
  if (score >= 90) return 'A'
  if (score >= 80) return 'B'
  if (score >= 70) return 'C'
  if (score >= 50) return 'D'
  return 'E'
}

export function securityGrade(criticalCount: number, highCount: number): LetterGrade {
  if (criticalCount === 0 && highCount === 0) return 'A'
  if (criticalCount === 0 && highCount <= 2) return 'B'
  if (criticalCount <= 1) return 'C'
  if (criticalCount <= 3) return 'D'
  return 'E'
}

export const gradeColor: Record<LetterGrade, string> = {
  A: 'bg-success text-success-foreground',
  B: 'bg-success/70 text-success-foreground',
  C: 'bg-warning text-warning-foreground',
  D: 'bg-warning/70 text-warning-foreground',
  E: 'bg-danger text-danger-foreground',
}
