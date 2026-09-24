import { expect, test, type APIRequestContext } from '@playwright/test'

const customerToken = 'prepwise-e2e-customer'
let createdOrderId = ''

async function clearCustomerCart(request: APIRequestContext) {
  const headers = { Authorization: `Bearer ${customerToken}` }
  const response = await request.get('/api/cart', { headers })
  expect(response.ok()).toBeTruthy()
  const cart = (await response.json()) as { items: Array<{ id: string }> }

  for (const item of cart.items) {
    const deleteResponse = await request.delete(`/api/cart/items/${item.id}`, {
      headers,
    })
    expect(deleteResponse.ok()).toBeTruthy()
  }
}

test.describe.serial('critical customer and admin flows', () => {
  test.beforeAll(async ({ request }) => {
    await clearCustomerCart(request)
  })

  test('customer browses a meal and adds it to the cart', async ({ page }) => {
    await page.goto('/?__e2e_role=customer')

    await expect(page.getByRole('heading', { name: 'Choose your meals' })).toBeVisible()
    const firstMeal = page.locator('.meal-card').first()
    await expect(firstMeal).toBeVisible()
    await firstMeal.getByRole('button', { name: 'Add to cart' }).click()

    await expect(page.locator('.cart-count')).toContainText('1 meal')
  })

  test('customer checks out and views the created order in history', async ({ page }) => {
    await page.goto('/?__e2e_role=customer')
    await expect(page.locator('.cart-count')).toContainText('1 meal')
    await page.getByLabel('Pickup location').selectOption({ index: 1 })

    page.once('dialog', (dialog) => dialog.accept())
    const orderResponsePromise = page.waitForResponse(
      (response) =>
        response.url().endsWith('/api/orders') &&
        response.request().method() === 'POST',
    )
    await page.getByRole('button', { name: 'Review and place order' }).click()
    const orderResponse = await orderResponsePromise
    expect(orderResponse.ok()).toBeTruthy()
    createdOrderId = ((await orderResponse.json()) as { id: string }).id

    await expect(page.getByText('Your cart is empty. Add a meal below.')).toBeVisible()
    const firstOrder = page.locator('.order-card').first()
    await expect(firstOrder).toBeVisible()
    await firstOrder.getByRole('button', { name: 'View order' }).click()
    await expect(page.getByText('Order details')).toBeVisible()
    await expect(page.locator('.order-detail')).toContainText('Received')
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
})
