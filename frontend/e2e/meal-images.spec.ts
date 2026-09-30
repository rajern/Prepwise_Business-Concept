import { expect, test } from '@playwright/test'

test('all twelve illustrations load on desktop and mobile, in both languages', async ({ page }) => {
  await page.goto('/?__e2e_role=guest')
  await expect(page.locator('.meal-card')).toHaveCount(12)
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: 900 })
    for (const card of await page.locator('.meal-card').all()) {
      await card.scrollIntoViewIfNeeded()
      const image = card.locator('img')
      await expect(image).toBeVisible()
      await expect(image).toHaveAttribute('src', /\/images\/meals\/[a-z-]+-v1\.webp$/)
      await expect.poll(() => image.evaluate((element: HTMLImageElement) => element.naturalWidth)).toBe(960)
      await expect(card.locator('figcaption')).toHaveText('AI-generert illustrasjon. Anretningen kan variere.')
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    await page.locator('.meal-card').first().scrollIntoViewIfNeeded()
    await page.screenshot({ path: test.info().outputPath(`meal-images-${width}.png`) })
  }
  await page.getByRole('button', { name: 'EN', exact: true }).click()
  await expect(page.locator('.meal-card figcaption')).toHaveCount(12)
  await expect(page.locator('.meal-card figcaption').first()).toHaveText('AI-generated illustration. Actual presentation may vary.')
  await page.locator('.meal-card').first().getByRole('button', { name: 'View details' }).click()
  await expect(page.locator('.meal-detail img')).toHaveAttribute('loading', 'eager')
  await expect(page.locator('.meal-detail figcaption')).toHaveText('AI-generated illustration. Actual presentation may vary.')
  // Vite's development SPA fallback differs from SWA. Real missing-asset 404s
  // are checked after deployment, with the SWA exclusion covered by unit tests.
})
