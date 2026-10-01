import { expect, test, type APIRequestContext } from '@playwright/test'

const customerToken = 'prepwise-e2e-customer'
let createdOrderId = ''

interface PickupOptions {
  timezone: string
  days: Array<{
    date: string
    slots: Array<{ id: string; start_at: string; end_at: string }>
  }>
}

function apiPath(url: string): string {
  return new URL(url).pathname
}

async function clearCustomerCart(request: APIRequestContext) {
  const headers = { Authorization: `Bearer ${customerToken}` }
  const response = await request.get('/api/cart?lang=no', { headers })
  expect(response.ok()).toBeTruthy()
  const cart = (await response.json()) as { items: Array<{ id: string }>; groups?: Array<{ id: string }> }

  for (const item of cart.items) {
    const deleteResponse = await request.delete(`/api/cart/items/${item.id}`, {
      headers,
    })
    expect(deleteResponse.ok()).toBeTruthy()
  }
  for (const group of cart.groups ?? []) {
    expect((await request.delete(`/api/cart/groups/${group.id}`, { headers })).ok()).toBeTruthy()
  }
}

test.describe.serial('critical customer and admin flows', () => {
  test.beforeAll(async ({ request }) => {
    await clearCustomerCart(request)
  })

  test.afterAll(async ({ request }) => {
    await clearCustomerCart(request)
  })

  test('guest sees the Norwegian menu and sign-in chat, and switches to English', async ({ page }) => {
    await page.goto('/?__e2e_role=guest')
    await expect(page.getByRole('heading', { name: 'Velg dine måltider' })).toBeVisible()
    await expect(page.locator('html')).toHaveAttribute('lang', 'nb')
    await page.getByRole('button', { name: 'Åpne chat' }).click()
    await expect(page.getByRole('heading', { name: 'For innloggede kunder' })).toBeVisible()
    await expect(page.getByText('Logg inn for å chatte om måltider, handlekurven, bestillinger og henting.')).toBeVisible()
    await expect(page.getByRole('textbox', { name: 'Melding' })).toHaveCount(0)
    await page.locator('.chat-launcher').click()
    await expect(page.locator('.chat-panel')).toHaveCount(0)

    const translatedMenu = page.waitForResponse((response) =>
      apiPath(response.url()) === '/api/meals' && new URL(response.url()).searchParams.get('lang') === 'en',
    )
    await page.getByRole('button', { name: 'EN', exact: true }).click()
    expect((await translatedMenu).ok()).toBeTruthy()
    await expect(page.getByRole('heading', { name: 'Choose your meals' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Chicken teriyaki with rice' })).toBeVisible()
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')
    await page.reload()
    await expect(page.getByRole('heading', { name: 'Choose your meals' })).toBeVisible()
    await page.getByRole('button', { name: 'NO', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Velg dine måltider' })).toBeVisible()
  })

  test('customer browses a meal and adds it to the cart', async ({ page }) => {
    await page.goto('/?__e2e_role=customer')

    await expect(page.getByRole('heading', { name: 'Velg dine måltider' })).toBeVisible()
    const firstMeal = page.locator('.meal-card').first()
    await expect(firstMeal).toBeVisible()
    await firstMeal.getByRole('button', { name: 'Legg i handlekurv' }).click()

    await expect(page.locator('.cart-badge')).toHaveText('1')
    await expect(page.getByText('Lagt i handlekurven')).toBeVisible()
    await expect(page.getByRole('dialog')).toHaveCount(0)
    await page.getByRole('button', { name: 'Åpne handlekurv (1)', exact: true }).click()
    await expect(page.getByRole('dialog', { name: 'Handlekurv' })).toBeVisible()
    await expect(page.locator('.cart-count')).toContainText('1 måltider')
    await page.getByRole('button', { name: 'Lukk handlekurv' }).click()
    await expect(page.getByRole('dialog')).toHaveCount(0)
  })

  test('customer checks out and views the created order in history', async ({ page }) => {
    await page.goto('/?__e2e_role=customer')
    await expect(page.locator('.cart-badge')).toHaveText('1')
    await page.getByRole('button', { name: 'Åpne handlekurv (1)', exact: true }).click()
    await page.getByLabel(/^Hentested/).selectOption({ index: 1 })
    const checkoutButton = page.getByRole('button', { name: 'Se over og bestill' })
    await expect(checkoutButton).toBeDisabled()
    const options = await page.request.get('/api/pickup-locations/options')
    expect(options.ok()).toBeTruthy()
    const pickup = (await options.json()) as PickupOptions
    const selectedDay = pickup.days[4]
    const selectedSlot = selectedDay.slots[1]
    await page.getByLabel(/^Hentedato/).selectOption(selectedDay.date)
    await expect(checkoutButton).toBeDisabled()
    await page.getByLabel(/^Hentetid/).selectOption(selectedSlot.id)
    await expect(checkoutButton).toBeEnabled()

    page.once('dialog', (dialog) => dialog.accept())
    const orderResponsePromise = page.waitForResponse(
      (response) =>
        apiPath(response.url()) === '/api/orders' &&
        response.request().method() === 'POST',
    )
    await checkoutButton.click()
    const orderResponse = await orderResponsePromise
    expect(orderResponse.ok()).toBeTruthy()
    const order = (await orderResponse.json()) as { id: string; pickup_start_at: string; pickup_end_at: string }
    createdOrderId = order.id
    expect(new Date(order.pickup_start_at).toISOString()).toBe(new Date(selectedSlot.start_at).toISOString())
    expect(new Date(order.pickup_end_at).toISOString()).toBe(new Date(selectedSlot.end_at).toISOString())
    expect(orderResponse.request().postDataJSON()).toMatchObject({
      pickup_date: selectedDay.date, pickup_slot: selectedSlot.id,
    })

    await expect(page.locator('.cart-badge')).toHaveText('0')
    const firstOrder = page.locator('.order-card').first()
    await expect(firstOrder).toBeVisible()
    await firstOrder.getByRole('button', { name: 'Lukk bestilling' }).click()
    await expect(page.locator('.order-detail')).toHaveCount(0)
    await firstOrder.getByRole('button', { name: 'Se bestilling' }).click()
    await expect(page.getByText('Ordredetaljer')).toBeVisible()
    await expect(page.locator('.order-detail')).toContainText('Mottatt')
    await expect(page.locator('.order-detail')).toContainText('18:00–20:00')
    await page.getByRole('button', { name: 'Åpne handlekurv (0)', exact: true }).click()
    await expect(page.getByText('Handlekurven er tom. Velg et måltid fra menyen.')).toBeVisible()
  })

  test('admin advances the order status', async ({ page }) => {
    expect(createdOrderId).not.toBe('')
    await page.goto('/admin?__e2e_role=admin')
    await page.getByRole('navigation', { name: 'Admin sections' }).getByRole('button', {
      name: 'Orders',
    }).click()

    const firstOrder = page.locator('.admin-record-card').first()
    await expect(firstOrder).toBeVisible()
    await firstOrder.getByRole('button', { name: 'Inspect' }).click()
    await page.getByRole('button', { name: 'Move to Preparing' }).click()
    await expect(page.locator('.admin-order-detail')).toContainText('Preparing')
  })

  test('customer cannot perform an admin operation', async ({ page }) => {
    expect(createdOrderId).not.toBe('')
    await page.goto('/admin?__e2e_role=customer')
    await expect(page.getByRole('heading', { name: 'Access denied' })).toBeVisible()

    const response = await page.request.patch(
      `/api/admin/orders/${createdOrderId}/status`,
      {
        headers: { Authorization: `Bearer ${customerToken}` },
        data: { status: 'ready_for_pickup' },
      },
    )
    expect(response.status()).toBe(403)
  })

  test('pickup groups survive reload, checkout preserves another day, and cancellation moves the order to history', async ({ page }) => {
    await clearCustomerCart(page.request)
    await page.goto('/?__e2e_role=customer')
    await expect(page.locator('.cart-badge')).toHaveText('0')
    await page.getByRole('button', { name: 'Åpne handlekurv (0)', exact: true }).click()
    await page.getByRole('button', { name: 'Legg til hentegruppe' }).click()
    await expect(page.locator('.pickup-group')).toHaveCount(1)
    await page.getByRole('button', { name: 'Legg til hentegruppe' }).click()
    await expect(page.locator('.pickup-group')).toHaveCount(2)
    const groupResponse = await page.request.get('/api/cart', { headers: { Authorization: `Bearer ${customerToken}` } })
    const groups = ((await groupResponse.json()) as { groups: Array<{ id: string }> }).groups
    const pickup = (await (await page.request.get('/api/pickup-locations/options')).json()) as PickupOptions
    for (const [position, group] of groups.entries()) {
      const region = page.locator('.pickup-group').nth(position)
      await region.getByLabel('Hentested', { exact: true }).selectOption({ index: 1 })
      await expect(region.getByLabel('Hentedato', { exact: true })).toBeEnabled()
      await region.getByLabel('Hentedato', { exact: true }).selectOption(pickup.days[position + 1].date)
      await region.getByLabel('Hentetid', { exact: true }).selectOption('16-18')
      await expect(page.getByRole('button', { name: 'Legg til hentegruppe' })).toBeEnabled()
      expect(group.id).not.toBe('')
    }
    await page.getByRole('button', { name: 'Lukk handlekurv' }).click()
    for (const group of groups) {
      await page.getByLabel('Legg måltider i', { exact: true }).selectOption(group.id)
      await page.locator('.meal-card').first().getByRole('button', { name: 'Legg i handlekurv' }).click()
      await expect(page.locator('.meal-card').first().getByRole('button', { name: 'Legg i handlekurv' })).toBeEnabled()
    }
    await expect(page.locator('.cart-badge')).toHaveText('2')
    await page.reload()
    await page.getByRole('button', { name: 'Åpne handlekurv (2)', exact: true }).click()
    const first = page.locator('.pickup-group').first()
    const second = page.locator('.pickup-group').nth(1)
    await expect(first.getByLabel('Hentedato', { exact: true })).toHaveValue(pickup.days[1].date)
    await expect(second.getByLabel('Hentedato', { exact: true })).toHaveValue(pickup.days[2].date)
    page.once('dialog', (dialog) => dialog.accept())
    const placed = page.waitForResponse((response) => apiPath(response.url()) === '/api/orders' && response.request().method() === 'POST')
    await first.getByRole('button', { name: 'Se over og bestill' }).click()
    const newOrder = (await (await placed).json()) as { id: string }
    await expect(page.locator('.cart-badge')).toHaveText('1')
    await page.getByRole('button', { name: 'Åpne handlekurv (1)', exact: true }).click()
    await expect(page.locator('.pickup-group').nth(1).getByLabel('Hentedato', { exact: true })).toHaveValue(pickup.days[2].date)
    await expect(page.locator('.cart-item')).toHaveCount(1)
    await page.getByRole('button', { name: 'Lukk handlekurv' }).click()
    page.once('dialog', (dialog) => dialog.accept())
    await page.getByRole('button', { name: 'Kanseller bestilling', exact: true }).click()
    await expect(page.locator('.order-detail')).toHaveCount(0)
    await expect(page.getByRole('link', { name: 'Ordrehistorikk' })).toHaveAttribute('href', '/orders')
    await page.goto('/orders?__e2e_role=customer')
    await expect(page.getByRole('heading', { name: 'Ordrehistorikk' })).toBeVisible()
    const cancelledCard = page.locator(`.order-card[data-order-id="${newOrder.id}"]`)
    await expect(cancelledCard).toContainText('Kansellert')
    await cancelledCard.getByRole('button', { name: 'Se bestilling' }).click()
    await expect(page.locator('.order-detail')).toContainText('Kansellert')
    const detailResponse = await page.request.get(`/api/orders/${newOrder.id}`, { headers: { Authorization: `Bearer ${customerToken}` } })
    expect((await detailResponse.json()).status).toBe('cancelled')
    await clearCustomerCart(page.request)
  })

  test('chat mutation refreshes the cart without reloading the page', async ({ page }) => {
    await clearCustomerCart(page.request)
    const catalogue = await page.request.get('/api/meals?lang=no')
    expect(catalogue.ok()).toBeTruthy()
    const meal = ((await catalogue.json()) as Array<{ id: string }>)[0]
    // Simulate the assistant's successful write using the real cart API. Never call a paid model.
    await page.route('**/api/assistant/messages', async (route) => {
      expect(route.request().postDataJSON()).toMatchObject({ lang: 'no', history: [] })
      const changed = await page.request.post('/api/cart/items?lang=no', {
        headers: { Authorization: `Bearer ${customerToken}` },
        data: { meal_id: meal.id, quantity: 1 },
      })
      expect(changed.ok()).toBeTruthy()
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          reply: 'Jeg har lagt måltidet i handlekurven.',
          model: 'e2e-stub', response_id: 'e2e-stub',
        }),
      })
    })
    await page.goto('/?__e2e_role=customer')
    await expect(page.locator('.cart-badge')).toHaveText('0')
    await page.getByRole('button', { name: 'Åpne chat' }).click()
    await page.getByRole('textbox', { name: 'Melding', exact: true }).fill('Legg et måltid i handlekurven.')
    await page.getByRole('button', { name: 'Send melding' }).click()
    await expect(page.getByRole('log')).toContainText('Jeg har lagt måltidet i handlekurven.')
    await expect(page.locator('.chat-message--user')).toHaveCount(1)
    await expect(page.locator('.chat-message--assistant')).toHaveCount(1)
    await expect(page.locator('.cart-badge')).toHaveText('1')
    await page.locator('.chat-launcher').click()
    await page.getByRole('button', { name: 'Åpne handlekurv (1)', exact: true }).click()
    await expect(page.locator('.cart-item')).toHaveCount(1)
    await page.getByRole('button', { name: 'Lukk handlekurv' }).click()
    await page.reload()
    await page.getByRole('button', { name: 'Åpne chat' }).click()
    await expect(page.getByRole('log')).toContainText('Jeg har lagt måltidet i handlekurven.')
  })
})
