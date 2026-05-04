import { expect, test } from '@playwright/test';
import { mockAgentPdf, mockAgentQuote, mockAuthenticatedUser } from './helpers/apiMocks.js';

test.describe('quote chat', () => {
  test('sends a message and surfaces quote actions + PDF download', async ({ page }) => {
    await mockAuthenticatedUser(page);
    await mockAgentQuote(page);
    let pdfAuthorizationHeader = null;
    await mockAgentPdf(page, (request) => {
      pdfAuthorizationHeader = request.headers().authorization;
    });

    await page.goto('/quote/new');
    await page.getByPlaceholder('Projekt beschreiben…').fill(
      'Wohnzimmer 25 m2 weiss streichen, Decke mitmachen.',
    );
    await page.keyboard.press('Enter');

    await expect(page.getByText('Wohnzimmer 25 m2 weiss streichen')).toBeVisible();
    await expect(page.getByText('Kostenvoranschlag fertig. PDF kommt gleich.')).toBeVisible();
    await expect(page.getByText('Angebot KV-20260503-201500-demo42 ist fertig.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'PDF öffnen' }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'Angebot anzeigen' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Im Dashboard anzeigen' })).toBeVisible();

    await page.getByRole('button', { name: 'PDF öffnen' }).first().click();
    await expect.poll(() => pdfAuthorizationHeader).toBe('Bearer test-access-token');
  });

  test('back-link returns to dashboard', async ({ page }) => {
    await mockAuthenticatedUser(page);
    await page.goto('/quote/new');
    await page.getByRole('link', { name: /Zurück zum Dashboard/ }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
  });
});
