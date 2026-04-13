import { expect, test } from '@playwright/test';

test('revision workflow reaches runs and logs', async ({ page }) => {
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

  await page.evaluate(async () => {
    const createNewsletterResponse = await fetch('/api/newsletters', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        name: 'Workflow Newsletter',
        description: 'Workflow check',
        prompt: 'Summarize https://example.com/updates',
        draft_subject: 'Initial subject',
        draft_preheader: 'Initial preheader',
        draft_body_text: 'Initial body',
        provider_name: 'openai',
        model_name: 'gpt-4o-mini',
        template_key: 'signal',
        audience_name: 'operators',
        delivery_topic: 'workflow-newsletter',
        timezone: 'UTC',
        schedule_enabled: false,
        status: 'active',
        recipient_import_text: 'qa@example.com',
      }),
    });
    const newsletter = await createNewsletterResponse.json();

    const generationResponse = await fetch(`/api/newsletters/${newsletter.id}/generate-draft`, {
      method: 'POST',
      credentials: 'include',
    });
    const generation = await generationResponse.json();

    await fetch(`/api/newsletters/${newsletter.id}/revisions/${generation.revision_id}/approve`, {
      method: 'POST',
      credentials: 'include',
    });

    await fetch(`/api/newsletters/${newsletter.id}/revisions/${generation.revision_id}/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ revision_id: generation.revision_id, idempotency_key: 'playwright-send-1' }),
    });
  });

  if (await page.getByRole('button', { name: 'Dashboard' }).count()) {
    await page.getByRole('button', { name: 'Dashboard' }).click();
  }
  await expect(page.getByRole('heading', { name: /run dashboard/i })).toBeVisible();
  await expect(page.getByText(/Delivery Runs/i)).toBeVisible();
  await expect(page.locator('table tbody tr').first()).toBeVisible();

  await page.getByRole('button', { name: 'Logs' }).click();
  await expect(page.getByRole('tab', { name: 'Audit Trail' })).toBeVisible();
  await page.getByRole('tab', { name: 'Operational Log' }).click();
  await expect(page.locator('table tbody tr').first()).toBeVisible();
});
