export function validateRepositoryUrls(repos: string[]): string | null {
  const invalidRepo = repos.find(
    (repo) => !repo.startsWith('https://') && !repo.startsWith('file://'),
  )

  if (!invalidRepo) {
    return null
  }

  return `Unsupported repository URL: ${invalidRepo}. Only https:// and file:// repositories are allowed.`
}
