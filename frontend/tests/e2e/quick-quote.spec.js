import { expect, test } from '@playwright/test';
import {
  mockAuthenticatedUser,
  mockQuickQuote,
  mockQuotePdfGenerate,
  sampleQuote,
} from './helpers/apiMocks.js';

test.describe('quick quote flow', () => {
  test('creates a quote, shows the result, and downloads the PDF', async ({ page }) => {
    await mockAuthenticatedUser(page);
    await mockQuickQuote(page);
    let pdfAuthorizationHeader = null;
    await mockQuotePdfGenerate(page, sampleQuote.id, (request) => {
      pdfAuthorizationHeader = request.headers().authorization;
    });

    await page.goto('/quick-quote');
    await page.getByLabel('Kundenname (optional)').fill(sampleQuote.customer_name);
    await page.getByLabel(/Was soll gemacht werden/).fill('Schlafzimmer streichen, 38 m2, Decke weiss.');
    await page.getByLabel('Fläche / Umfang (optional)').fill('38 m2');
    await page.getByRole('button', { name: 'Angebot erstellen' }).click();

    await expect(page.getByText(sampleQuote.project_title)).toBeVisible();
    await expect(page.getByText(sampleQuote.quote_number)).toBeVisible();
    await expect(page.getByText('1.953,08').first()).toBeVisible();

    await page.getByRole('button', { name: 'PDF herunterladen' }).click();
    await expect.poll(() => pdfAuthorizationHeader).toBe('Bearer test-access-token');
  });
});
