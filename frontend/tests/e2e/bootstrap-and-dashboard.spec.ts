import { expect, test, type Page } from '@playwright/test';

const E2E_EMAIL = process.env.PLAYWRIGHT_E2E_EMAIL ?? 'operator@example.com';
const E2E_PASSWORD = process.env.PLAYWRIGHT_E2E_PASSWORD ?? 'super-secret-password';

type SessionPayload = {
  initialized: boolean;
  authenticated: boolean;
};

async function ensureAuthenticated(page: Page): Promise<void> {
  await page.goto('/');

  const session = await page.evaluate(async () => {
    const response = await fetch('/api/auth/session', { credentials: 'include' });
    return (await response.json()) as SessionPayload;
  });

  if (!session.initialized) {
    const bootstrapResult = await page.evaluate(
      async ({ email, password }) => {
        const response = await fetch('/api/auth/bootstrap', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ email, password }),
        });
        return { ok: response.ok, status: response.status, body: await response.text() };
      },
      { email: E2E_EMAIL, password: E2E_PASSWORD },
    );

    if (!bootstrapResult.ok) {
      // Parallel workers may race on first-run bootstrap; if the partner
      // worker already claimed it, fall through to login with the same
      // credentials.
      const loginResult = await page.evaluate(
        async ({ email, password }) => {
          const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ email, password }),
          });
          return { ok: response.ok, status: response.status, body: await response.text() };
        },
        { email: E2E_EMAIL, password: E2E_PASSWORD },
      );

      expect(
        loginResult.ok,
        `Bootstrap failed (${bootstrapResult.status} ${bootstrapResult.body}) and login fallback also failed (${loginResult.status} ${loginResult.body})`,
      ).toBe(true);
    }
  } else if (!session.authenticated) {
    const loginResult = await page.evaluate(
      async ({ email, password }) => {
        const response = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ email, password }),
        });
        return { ok: response.ok, status: response.status, body: await response.text() };
      },
      { email: E2E_EMAIL, password: E2E_PASSWORD },
    );

    expect(
      loginResult.ok,
      `Login failed for PLAYWRIGHT_E2E_EMAIL=${E2E_EMAIL}: ${loginResult.status} ${loginResult.body}`,
    ).toBe(true);
  }

  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Dashboard' })).toBeVisible({ timeout: 15000 });
}

type SeedResult = { ok: boolean; status: number; body: string };

async function seedApiKey(
  page: Page,
  params: { name: string; providerType: string; isActive?: boolean; fromEmail?: string | null },
): Promise<number> {
  const result = await page.evaluate(async (payload) => {
    const response = await fetch('/api/api-keys', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        name: payload.name,
        provider_type: payload.providerType,
        key_value: 'e2e-test-secret',
        from_email: payload.fromEmail ?? null,
        is_active: payload.isActive ?? true,
      }),
    });
    const body = await response.text();
    let id: number | null = null;
    try {
      id = JSON.parse(body)?.id ?? null;
    } catch {
      id = null;
    }
    return { ok: response.ok, status: response.status, body, id } as SeedResult & { id: number | null };
  }, params);

  expect(result.ok, `Seed api key failed: ${result.status} ${result.body}`).toBe(true);
  expect(result.id, 'Seed api key response missing id').not.toBeNull();
  return result.id as number;
}

async function seedProvider(
  page: Page,
  params: { name: string; providerType: string; isEnabled?: boolean; defaultModel?: string },
): Promise<number> {
  const result = await page.evaluate(async (payload) => {
    const response = await fetch('/api/providers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        name: payload.name,
        provider_type: payload.providerType,
        is_enabled: payload.isEnabled ?? true,
        default_model: payload.defaultModel ?? null,
      }),
    });
    const body = await response.text();
    let id: number | null = null;
    try {
      id = JSON.parse(body)?.id ?? null;
    } catch {
      id = null;
    }
    return { ok: response.ok, status: response.status, body, id } as SeedResult & { id: number | null };
  }, params);

  expect(result.ok, `Seed provider failed: ${result.status} ${result.body}`).toBe(true);
  expect(result.id, 'Seed provider response missing id').not.toBeNull();
  return result.id as number;
}

test('bootstrap and dashboard flow', async ({ page }) => {
  await ensureAuthenticated(page);

  await expect(page.getByRole('heading', { name: /run dashboard/i })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Newsletters' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Logs' })).toBeVisible();
});

test('provider dropdown actions open and execute', async ({ page }) => {
  await ensureAuthenticated(page);

  const suffix = `${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
  const apiKeyName = `e2e-prov-key-${suffix}`;
  const providerName = `e2e-provider-${suffix}`;

  await seedApiKey(page, { name: apiKeyName, providerType: 'openai', isActive: true });
  await seedProvider(page, {
    name: providerName,
    providerType: 'openai',
    isEnabled: true,
    defaultModel: 'gpt-4o-mini',
  });

  await page.getByRole('button', { name: 'Providers' }).click();
  await page.waitForLoadState('networkidle');

  const providerRow = page.locator('tr.data-row', { hasText: providerName }).first();
  await expect(providerRow).toBeVisible({ timeout: 15000 });

  const actionTrigger = providerRow.locator('button.action-dropdown-trigger').first();
  await expect(actionTrigger).toBeVisible({ timeout: 15000 });

  await actionTrigger.click();
  const disableAction = page.locator('button.action-dropdown-item').filter({ hasText: /^Disable$/ }).first();
  await expect(disableAction).toBeVisible({ timeout: 15000 });
  await disableAction.click();

  await expect(providerRow.locator('.status-badge')).toHaveText(/Disabled/i, { timeout: 15000 });

  await actionTrigger.click();
  const enableAction = page.locator('button.action-dropdown-item').filter({ hasText: /^Enable$/ }).first();
  await expect(enableAction).toBeVisible({ timeout: 15000 });
  await enableAction.click();

  await expect(providerRow.locator('.status-badge')).toHaveText(/Enabled/i, { timeout: 15000 });
});

test('api key action buttons toggle active state', async ({ page }) => {
  await ensureAuthenticated(page);

  const suffix = `${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
  const apiKeyName = `e2e-key-${suffix}`;

  await seedApiKey(page, { name: apiKeyName, providerType: 'anthropic', isActive: true });

  await page.getByRole('button', { name: 'API Keys' }).click();
  await page.waitForLoadState('networkidle');

  const card = page.locator('article.newsletter-card', { hasText: apiKeyName }).first();
  await expect(card).toBeVisible({ timeout: 15000 });

  const statusChip = card.locator('.status-chip');
  await expect(statusChip).toHaveText(/Active/i);

  const toggleButton = card.locator('.card-actions button', { hasText: /^(Activate|Deactivate)$/ }).first();
  await expect(toggleButton).toHaveText(/Deactivate/i);

  await toggleButton.click();
  await expect(card.locator('.status-chip')).toHaveText(/Inactive/i, { timeout: 15000 });
  await expect(card.locator('.card-actions button', { hasText: /^(Activate|Deactivate)$/ }).first()).toHaveText(/Activate/i);

  await card.locator('.card-actions button', { hasText: /^Activate$/ }).first().click();
  await expect(card.locator('.status-chip')).toHaveText(/Active/i, { timeout: 15000 });
  await expect(card.locator('.card-actions button', { hasText: /^(Activate|Deactivate)$/ }).first()).toHaveText(/Deactivate/i);
});
