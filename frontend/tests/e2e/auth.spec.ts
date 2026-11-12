import { expect, test, type Page, type Route } from '@playwright/test'

function capabilitiesPayload(overrides?: Record<string, unknown>) {
  return {
    authentication: {
      auth_mode: 'workos',
      session_auth_provider: 'workos',
      api_keys: false,
      bootstrap_registration_required: false,
      saas_enabled: true,
      workos_configured: true,
    },
    license: {
      tier: 'enterprise',
      features: ['advanced_policies', 'custom_policies'],
      organization: 'Acme',
    },
    runtime: {
      distribution_mode: 'saas',
    },
    ...overrides,
  }
}

async function fulfillJson(route: Route, status: number, body: unknown) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

async function mockApi(
  page: Page,
  options: {
    capabilitiesStatus?: number
    meStatus?: number
    meBody?: Record<string, unknown>
    scansBody?: unknown[]
  } = {},
) {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())

    if (url.pathname === '/api/v1/system/capabilities') {
      await fulfillJson(route, options.capabilitiesStatus ?? 200, capabilitiesPayload())
      return
    }

    if (url.pathname === '/api/v1/auth/me') {
      if ((options.meStatus ?? 200) === 401) {
        await fulfillJson(route, 401, { detail: 'Unauthorized' })
        return
      }

      await fulfillJson(route, options.meStatus ?? 200, {
        id: 1,
        email: 'owner@example.com',
        name: 'Owner',
        tenant_slug: 'acme',
        auth_provider: 'workos',
        workos_org_id: 'org_acme',
        role: 'admin',
        platform_role: 'none',
        onboarding_completed: false,
        created_at: '2026-04-01T00:00:00Z',
        last_login_at: '2026-04-01T00:00:00Z',
        ...options.meBody,
      })
      return
    }

    if (url.pathname === '/api/v1/scans/') {
      await fulfillJson(route, 200, options.scansBody ?? [])
      return
    }

    await fulfillJson(route, 200, {})
  })
}

test('protected routes fail closed when auth bootstrap fails', async ({ page }) => {
  await page.route('**/api/v1/system/capabilities', async (route) => {
    await fulfillJson(route, 503, { detail: 'Unavailable' })
  })

  await page.goto('/projects')

  await expect(
    page.getByText('Authentication could not be initialized. Retry once the API is reachable.'),
  ).toBeVisible()
  await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible()
})

test('workos users are redirected to onboarding before protected routes', async ({ page }) => {
  await mockApi(page, {
    meBody: { onboarding_completed: false },
  })

  await page.goto('/projects')

  await expect(page).toHaveURL(/\/onboarding\?next=%2Fprojects$/)
  await expect(page.getByRole('heading', { name: 'Welcome to VigilWeave, Owner!' })).toBeVisible()
})

test('completed onboarding resumes the preserved next route', async ({ page }) => {
  await mockApi(page, {
    meBody: { onboarding_completed: true },
    scansBody: [],
  })

  await page.goto('/onboarding?next=%2Fscans')

  await expect(page).toHaveURL(/\/scans$/)
  await expect(page.getByRole('heading', { name: 'Scans', exact: true })).toBeVisible()
})
