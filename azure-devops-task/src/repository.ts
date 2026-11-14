export function sanitizeRepositoryUrl(repositoryUrl: string): string {
  try {
    const url = new URL(repositoryUrl)
    if (!url.username && !url.password) return repositoryUrl
    url.username = ''
    url.password = ''
    return url.toString()
  } catch {
    throw new Error('Repository URL must be valid')
  }
}
