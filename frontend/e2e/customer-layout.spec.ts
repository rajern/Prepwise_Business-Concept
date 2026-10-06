import { expect, test } from '@playwright/test'

// Browser-only UI evidence: every API response is mocked; no model/provider or production calls.
test('customer dialogs, pickup groups and order sections work on desktop and mobile', async ({ page }) => {
  await page.clock.setFixedTime(new Date('2026-10-01T10:00:00Z'))
  const meal = { id: 'meal-one', name: 'Kylling teriyaki med ris', description: 'Kylling med ris og brokkoli.', image_url: '/images/meals/chicken-teriyaki-v1.webp', price_nok: '129.00', calories: 585, protein_grams: '43', carbohydrate_grams: '68', fat_grams: '14', ingredients: ['Kylling', 'Ris', 'Brokkoli'], allergens: [{ code: 'soy', name: 'Soya' }], available: true }
  const location = { id: 'location-one', name: 'Prepwise Grünerløkka', address_line: 'Thorvald Meyers gate 35', postal_code: '0555', city: 'Oslo' }
  const groups = ['2026-10-02', '2026-10-03'].map((date, index) => {
    const id = `group-${index}`
    return { id, version: 'a'.repeat(64), pickup_location_id: location.id, pickup_date: date, pickup_slot: '16-18', items: [{ id: `item-${index}`, group_id: id, quantity: 1, line_total_nok: '129.00', meal }], total_quantity: 1, total_nok: '129.00' }
  })
  const order = (id: string, status: string) => ({ id, status, total_nok: '129.00', created_at: '2026-10-01T10:00:00Z', pickup_start_at: '2026-10-02T14:00:00Z', pickup_end_at: '2026-10-02T16:00:00Z', pickup_location_name: location.name, pickup_location_address: 'Thorvald Meyers gate 35, 0555 Oslo', can_cancel: status === 'received', cancellation_deadline: '2026-10-01T22:00:00Z', items: [{ meal_id: meal.id, meal_name: meal.name, quantity: 1, unit_price_nok: '129.00', line_total_nok: '129.00' }] })
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const path = new URL(route.request().url()).pathname
    let body: unknown
    if (path === '/api/meals') body = [meal]
    else if (path === '/api/meals/meal-one') body = meal
    else if (path === '/api/cart') body = { groups, items: groups.flatMap((group) => group.items), total_quantity: 2, total_nok: '258.00' }
    else if (path === '/api/orders') body = [order('active', 'received'), order('old', 'completed')]
    else if (path === '/api/orders/active') body = order('active', 'received')
    else if (path === '/api/orders/old') body = order('old', 'completed')
    else if (path === '/api/pickup-locations') body = [location]
    else if (path === '/api/pickup-locations/options') body = { timezone: 'Europe/Oslo', days: groups.map((group) => ({ date: group.pickup_date, slots: [{ id: '16-18', start_at: `${group.pickup_date}T14:00:00Z`, end_at: `${group.pickup_date}T16:00:00Z` }] })) }
    else throw new Error(`Unexpected request in offline UI proof: ${path}`)
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  })
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/?__e2e_role=customer')
    await expect(page.locator('.meal-card')).toHaveCount(1)
    await page.getByRole('button', { name: 'Se detaljer', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: 'Måltidsdetaljer' })
    await expect(dialog).toBeVisible()
    await expect(dialog.getByRole('heading', { name: meal.name })).toBeVisible()
    await expect.poll(() => dialog.locator('img').evaluate((element: HTMLImageElement) => element.naturalWidth)).toBe(960)
    await page.screenshot({ path: test.info().outputPath(`meal-dialog-${width}.png`) })
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Se detaljer', exact: true })).toBeFocused()
    await page.getByRole('button', { name: 'Åpne handlekurv (2)', exact: true }).click()
    const cart = page.getByRole('dialog', { name: 'Handlekurv', exact: true })
    await expect(cart).toBeVisible()
    await expect(cart.locator('.pickup-group')).toHaveCount(2)
    await expect(cart.locator('.pickup-group').first().getByLabel('Hentedato', { exact: true })).toHaveValue('2026-10-02')
    await expect(cart.locator('.pickup-group').nth(1).getByLabel('Hentedato', { exact: true })).toHaveValue('2026-10-03')
    expect(await cart.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true)
    await page.screenshot({ path: test.info().outputPath(`grouped-cart-${width}.png`) })
    await page.keyboard.press('Escape')
    await expect(cart).not.toBeVisible()
    await page.getByRole('button', { name: /Kommende bestillinger/ }).click()
    await expect(page.locator('.order-card')).toHaveCount(1)
    await page.getByRole('button', { name: 'Se bestilling', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Kanseller bestilling', exact: true })).toBeVisible()
    await page.screenshot({ path: test.info().outputPath(`upcoming-orders-${width}.png`) })
    await page.locator('.order-card').getByRole('button', { name: 'Lukk bestilling' }).click()
    await expect(page.locator('.order-detail')).toHaveCount(0)
    await page.goto('/orders?__e2e_role=customer')
    await expect(page.getByRole('heading', { name: 'Ordrehistorikk' })).toBeVisible()
    await expect(page.locator('.order-card')).toHaveCount(1)
    await expect(page.locator('.order-card')).toContainText('Fullført')
    await expect(page.locator('.meal-card')).toHaveCount(0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    await page.screenshot({ path: test.info().outputPath(`order-history-${width}.png`) })
  }
})
