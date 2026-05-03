import { expect, test } from '@playwright/test';
import {
  mockAuthenticatedUser,
  mockDuplicateQuote,
  mockQuoteDetail,
  mockQuotePdfGenerate,
  mockUpdateQuoteStatus,
  sampleQuote,
} from './helpers/apiMocks.js';

test.describe('quote detail actions', () => {
  test('shows old quote actions and downloads PDFs with auth', async ({ page }) => {
    await mockAuthenticatedUser(page);
    await mockQuoteDetail(page);
    let pdfAuthorizationHeader = null;
    await mockQuotePdfGenerate(page, sampleQuote.id, (request) => {
      pdfAuthorizationHeader = request.headers().authorization;
    });

    await page.goto(`/quotes/${sampleQuote.id}`);

    await expect(page.getByRole('heading', { name: `Angebot ${sampleQuote.quote_number}` })).toBeVisible();
    await expect(page.getByRole('button', { name: 'PDF herunterladen' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Bearbeiten' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Duplizieren' })).toBeVisible();
    await expect(page.getByLabel('Status ändern')).toHaveValue('draft');

    await page.getByRole('button', { name: 'PDF herunterladen' }).click();
    await expect.poll(() => pdfAuthorizationHeader).toBe('Bearer test-access-token');
  });

  test('can change status and duplicate a quote', async ({ page }) => {
    await mockAuthenticatedUser(page);
    await mockQuoteDetail(page);
    await mockUpdateQuoteStatus(page);
    await mockDuplicateQuote(page);

    await page.goto(`/quotes/${sampleQuote.id}`);
    await page.getByLabel('Status ändern').selectOption('accepted');
    await expect(page.locator('span').filter({ hasText: 'Angenommen' })).toBeVisible();

    await page.getByRole('button', { name: 'Duplizieren' }).click();
    await expect(page).toHaveURL(/\/quotes\/43$/);
  });
});
