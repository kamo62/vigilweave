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

export function resolveRepositoryUrl(
  explicitRepositoryUrl: string,
  repository: string,
  serverUrl: string,
): string {
  if (explicitRepositoryUrl) return sanitizeRepositoryUrl(explicitRepositoryUrl)
  if (!repository) return ''
  const repositoryUrl = `${serverUrl.replace(/\/+$/, '')}/${repository}.git`
  return sanitizeRepositoryUrl(repositoryUrl)
}
