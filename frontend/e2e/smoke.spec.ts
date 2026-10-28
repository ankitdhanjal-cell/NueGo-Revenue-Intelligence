import { expect, test } from '@playwright/test';

// Read-only: it never records a decision, so it does not write to the shared database.
test('open an upcoming service, see the model fare and the allowed fare options', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('tab', { name: 'Next 30 days', selected: true })).toBeVisible();

  await page.getByRole('row').filter({ hasText: 'Delhi → Rishikesh' }).first().click();
  await expect(page.getByRole('heading', { name: 'Our suggestion' })).toBeVisible();
  await expect(page.getByText('Predicted fare')).toBeVisible();
  await expect(page.getByText('Suggested fare, inside your pricing rules')).toBeVisible();
  await expect(page.getByText('Departs 08 Nov 2026')).toBeVisible();

  await page.getByRole('button', { name: 'Change fare' }).click();
  const dialog = page.getByRole('dialog', { name: 'Change fare' });
  const fare = dialog.getByLabel(/New fare/);
  await expect(fare.locator('option[disabled]').first()).toBeAttached(); // a blocked fare cannot be picked
  await expect(fare.locator('option:not([disabled])')).not.toHaveCount(1); // placeholder plus allowed steps
  await dialog.getByRole('button', { name: 'Cancel' }).click();
  await expect(dialog).toBeHidden();

  await page.getByRole('tab', { name: 'Past decisions' }).click();
  await expect(page.getByRole('region', { name: 'Past decisions' })).toBeVisible();
});

test('the departed-services tab lists real history and the rules page loads', async ({ page }) => {
  await page.goto('/?window=earlier');
  await expect(page.getByRole('row').nth(1)).toBeVisible();
  await page.goto('/settings');
  await expect(page.getByRole('heading', { name: 'Pricing rules' })).toBeVisible();
});
