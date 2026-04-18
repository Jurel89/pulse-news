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

test('chatgpt subscription preset shows oauth prompt and non-codex default model', async ({ page }) => {
  await ensureAuthenticated(page);

  // Clean up any pre-existing ChatGPT OAuth connection so the test starts
  // from a known empty state even on a reused database.  Disable any
  // enabled ChatGPT providers first so the OAuth delete isn't blocked by 409.
  await page.evaluate(async () => {
    const providersResp = await fetch('/api/providers', { credentials: 'include' });
    const providers = await providersResp.json();
    const chatgptProviders = providers.filter(
      (p: any) => p.provider_type === 'openai_chatgpt' && p.is_enabled
    );
    for (const provider of chatgptProviders) {
      await fetch(`/api/providers/${provider.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ ...provider, is_enabled: false }),
      });
    }

    const resp = await fetch('/api/api-keys', { credentials: 'include' });
    const keys = await resp.json();
    const oauthKey = keys.find((k: any) => k.provider_type === 'openai_chatgpt' && k.auth_type === 'oauth');
    if (oauthKey) {
      await fetch(`/api/oauth/openai/${oauthKey.id}`, { method: 'DELETE', credentials: 'include' });
    }
  });

  await page.getByRole('button', { name: 'Providers' }).click();
  await page.waitForLoadState('networkidle');

  await page.getByRole('button', { name: 'New Provider' }).click();
  await page.waitForLoadState('networkidle');

  const presetSelect = page.locator('select').first();
  await presetSelect.waitFor({ state: 'visible', timeout: 15000 });
  await expect(presetSelect).toBeEnabled();
  await presetSelect.selectOption('openai_chatgpt');

  // The provider type input should be auto-filled
  await expect(page.locator('input[placeholder="openai"]')).toHaveValue('openai_chatgpt');

  // No API-key warning should appear for an OAuth-backed preset
  await expect(page.locator('.form-error')).not.toBeVisible();

  // OAuth connect prompt should appear with a clickable link
  const oauthPrompt = page.locator('.form-info');
  await expect(oauthPrompt).toBeVisible();
  await expect(oauthPrompt).toContainText('uses OAuth');

  // Mock the device-start API so the test doesn't depend on live OpenAI.
  await page.route('/api/oauth/openai/device/start', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        device_auth_id: 'dev_e2e_123',
        user_code: 'E2E-TEST',
        verification_uri: 'https://auth.openai.com/codex/device',
        interval: 5,
        expires_in: 900,
      }),
    });
  });

  // Also mock the device-poll API so the modal stays in a pending state
  // instead of hitting the real backend with the fake device_auth_id.
  await page.route('/api/oauth/openai/device/poll', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'pending',
        retry_after: 5,
      }),
    });
  });

  // Clicking the connect link should open the device-auth modal
  await oauthPrompt.locator('a').click();
  const modal = page.locator('.modal-panel');
  await expect(modal).toBeVisible();
  // The modal title should reference ChatGPT / device connection
  await expect(modal).toContainText('ChatGPT');

  await expect(modal).toContainText('Waiting for you to authorise');

  // Wait past the first poll interval. OpenAI typically returns interval=5s;
  // waiting 8s ensures the backend has polled at least once. After the fix,
  // a 403 deviceauth_authorization_unknown response is treated as pending,
  // so the modal must remain usable instead of falling into an error state.
  await page.waitForTimeout(8000);
  await expect(modal).toBeVisible();
  await expect(modal.locator('.error-banner')).not.toBeVisible();
  const waitingText = modal.locator('p').filter({ hasText: /Waiting for you to authorise|Checking for authorisation/ });
  await expect(waitingText).toBeVisible();

  // The default model should not be a codex model
  const defaultModelInput = page.locator('input[list="provider-model-options"]');
  const defaultValue = await defaultModelInput.inputValue();
  expect(defaultValue).not.toContain('codex');
  expect(defaultValue).toMatch(/^gpt-5\./);
});

test('chatgpt device-code modal keeps waiting after transport poll failure', async ({ page }) => {
  await ensureAuthenticated(page);

  await page.evaluate(async () => {
    const providersResp = await fetch('/api/providers', { credentials: 'include' });
    const providers = await providersResp.json();
    const chatgptProviders = providers.filter(
      (p: any) => p.provider_type === 'openai_chatgpt' && p.is_enabled
    );
    for (const provider of chatgptProviders) {
      await fetch(`/api/providers/${provider.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ ...provider, is_enabled: false }),
      });
    }

    const resp = await fetch('/api/api-keys', { credentials: 'include' });
    const keys = await resp.json();
    const oauthKey = keys.find((k: any) => k.provider_type === 'openai_chatgpt' && k.auth_type === 'oauth');
    if (oauthKey) {
      await fetch(`/api/oauth/openai/${oauthKey.id}`, { method: 'DELETE', credentials: 'include' });
    }
  });

  await page.getByRole('button', { name: 'Providers' }).click();
  await page.waitForLoadState('networkidle');

  await page.getByRole('button', { name: 'New Provider' }).click();
  await page.waitForLoadState('networkidle');

  const presetSelect = page.locator('select').first();
  await presetSelect.waitFor({ state: 'visible', timeout: 15000 });
  await expect(presetSelect).toBeEnabled();
  await presetSelect.selectOption('openai_chatgpt');

  const oauthPrompt = page.locator('.form-info');
  await expect(oauthPrompt).toBeVisible();
  await expect(oauthPrompt).toContainText('uses OAuth');

  await page.route('/api/oauth/openai/device/start', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        device_auth_id: 'dev_e2e_transport_failure',
        user_code: 'E2E-FAIL',
        verification_uri: 'https://auth.openai.com/codex/device',
        interval: 1,
        expires_in: 900,
      }),
    });
  });

  let pollAttempts = 0;
  await page.route('/api/oauth/openai/device/poll', async (route) => {
    pollAttempts += 1;

    if (pollAttempts === 2) {
      await route.abort('failed');
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'pending',
        retry_after: 1,
      }),
    });
  });

  await oauthPrompt.locator('a').click();

  const modal = page.locator('.modal-panel');
  await expect(modal).toBeVisible();
  await expect(modal).toContainText('ChatGPT');
  await expect(modal).toContainText('E2E-FAIL');

  const waitingText = modal
    .locator('p')
    .filter({ hasText: /Waiting for you to authorise|Checking for authorisation/ });
  await expect(waitingText).toBeVisible();

  await expect.poll(() => pollAttempts, { timeout: 10000 }).toBeGreaterThanOrEqual(2);

  await expect(modal).toBeVisible();
  await expect(modal).not.toContainText(/Load failed|Failed to fetch|NetworkError|ERR_FAILED/i);
  await expect(waitingText).toBeVisible();
  await expect(modal.locator('.error-banner')).not.toBeVisible();
});
