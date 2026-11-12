import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { router } from './router'

vi.mock('./lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./lib/api')>()
  return {
    ...actual,
    fetchCapabilities: vi.fn().mockResolvedValue({
      authentication: {
        api_keys: true,
        auth_mode: 'local',
        bootstrap_registration_required: false,
        session_auth_provider: 'none',
        saas_enabled: false,
        tenant_headers: true,
        workos_configured: false,
      },
      integrations: { azure_devops: true, prisma_cloud: true },
      ide: { vscode: true, analyze_endpoint: true },
      scan_types: ['comprehensive', 'fast'],
      version: '2.0.0',
    }),
    fetchScans: vi.fn().mockResolvedValue([]),
    fetchProjects: vi.fn().mockResolvedValue([]),
    fetchPortfolios: vi.fn().mockResolvedValue([]),
    fetchApiKeys: vi.fn().mockResolvedValue([]),
  }
})

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the dashboard shell', async () => {
    const queryClient = new QueryClient()

    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    )

    expect(await screen.findByText('VigilWeave')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Projects', level: 1 })).toBeInTheDocument()
    expect(await screen.findByText('No projects yet')).toBeInTheDocument()
  })
})
