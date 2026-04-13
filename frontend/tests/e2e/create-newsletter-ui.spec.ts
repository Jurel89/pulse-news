import { expect, test } from '@playwright/test';

test('create newsletter through the UI', async ({ page }) => {
  await page.goto('/');

  if (await page.getByRole('heading', { name: /create the first operator account/i }).count()) {
    await page.getByLabel('Email').fill('operator@example.com');
    await page.getByLabel('Password').fill('super-secret-password');
    await page.getByRole('button', { name: /create operator account/i }).click();
  } else {
    await page.getByLabel('Email').fill('operator@example.com');
    await page.getByLabel('Password').fill('super-secret-password');
    await page.getByRole('button', { name: /log in/i }).click();
  }

  await page.evaluate(async () => {
    const createApiKey = async (providerType: string, name: string, fromEmail?: string) => {
      await fetch('/api/api-keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          name,
          provider_type: providerType,
          key_value: `key-${providerType}`,
          is_active: true,
          from_email: fromEmail ?? null,
        }),
      });
    };

    await createApiKey('openai', 'OpenAI Test Key');
    await createApiKey('resend', 'Resend Test Key', 'newsletter@example.com');

    await fetch('/api/providers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        name: 'OpenAI Provider',
        provider_type: 'openai',
        is_enabled: true,
        default_model: 'gpt-4o-mini',
      }),
    });
  });

  await page.reload();
  if (await page.getByRole('heading', { name: /log in to pulse news/i }).count()) {
    await page.getByLabel('Email').fill('operator@example.com');
    await page.getByLabel('Password').fill('super-secret-password');
    await page.getByRole('button', { name: /log in/i }).click();
  }

  await page.getByRole('button', { name: 'Jobs' }).click();
  await page.getByRole('button', { name: /new newsletter/i }).click();
  await page.getByLabel('Name').fill('UI Created Newsletter');
  await page.getByLabel('Description').fill('Created through the UI');
  await page.getByLabel('Status').selectOption({ label: 'Active' });
  await page.getByLabel('Prompt').fill('Summarize https://example.com/updates');
  await page.getByLabel('Draft Subject').fill('Initial subject');
  await page.getByLabel('Draft Preheader').fill('Initial preheader');
  await page.getByLabel('Draft Body').fill('Initial body');
  await page.getByLabel('Provider').selectOption({ label: 'OpenAI Provider' });
  await page.getByLabel('Model').selectOption({ label: 'gpt-4o-mini' });
  await page.getByLabel('AI API Key').selectOption({ index: 1 });
  await page.getByLabel('Resend API Key').selectOption({ index: 1 });
  await page.getByLabel('Template').selectOption({ index: 1 });
  await page.getByLabel('Audience').fill('operators');
  await page.getByLabel('Delivery Topic').fill('ui-created-newsletter');
  await page.getByLabel('Timezone').selectOption({ label: 'UTC' });
  await page.getByLabel('Recipients').fill('qa@example.com');

  await Promise.all([
    page.waitForResponse((response) =>
      response.url().includes('/api/newsletters') && response.request().method() === 'POST' && response.ok(),
    ),
    page.getByRole('button', { name: /create newsletter/i }).click(),
  ]);

  await page.reload();
  if (await page.getByRole('heading', { name: /log in to pulse news/i }).count()) {
    await page.getByLabel('Email').fill('operator@example.com');
    await page.getByLabel('Password').fill('super-secret-password');
    await page.getByRole('button', { name: /log in/i }).click();
  }

  await page.getByRole('button', { name: 'Jobs' }).click();
  await expect(page.locator('tr', { hasText: 'UI Created Newsletter' }).first()).toBeVisible({ timeout: 15000 });
});
