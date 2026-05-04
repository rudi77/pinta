import { expect, test } from '@playwright/test';
import {
  mockAgentPdf,
  mockAgentPdfInfo,
  mockAuthenticatedUser,
  mockDuplicateQuote,
  mockQuoteDetail,
  mockUpdateQuoteStatus,
  sampleQuote,
} from './helpers/apiMocks.js';

test.describe('quote detail actions', () => {
  test('downloads agent-generated PDF with auth', async ({ page }) => {
    await mockAuthenticatedUser(page);
    await mockQuoteDetail(page);
    await mockAgentPdfInfo(page, sampleQuote.id);
    let pdfAuthorizationHeader = null;
    await mockAgentPdf(page, (request) => {
      pdfAuthorizationHeader = request.headers().authorization;
    });

    await page.goto(`/quotes/${sampleQuote.id}`);

    await expect(page.getByRole('heading', { name: `Angebot ${sampleQuote.quote_number}` })).toBeVisible();
    await expect(page.getByRole('button', { name: 'PDF herunterladen' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Neues Angebot' })).toBeVisible();
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
