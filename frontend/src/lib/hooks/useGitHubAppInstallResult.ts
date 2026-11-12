import { useEffect, useState } from 'react'

export type GitHubAppInstallResult = {
  connected: boolean
  message: string
}

export function useGitHubAppInstallResult(): GitHubAppInstallResult | null {
  const [result, setResult] = useState<GitHubAppInstallResult | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const connected = params.get('githubAppConnected')
    const message = params.get('githubAppMessage')
    if (!connected || !message) {
      return
    }

    setResult({ connected: connected === '1', message })

    const nextUrl = new URL(window.location.href)
    nextUrl.searchParams.delete('githubAppConnected')
    nextUrl.searchParams.delete('githubAppMessage')
    window.history.replaceState({}, '', `${nextUrl.pathname}${nextUrl.search}${nextUrl.hash}`)
  }, [])

  return result
}
