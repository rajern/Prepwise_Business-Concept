import { apiUrl } from './config'

export interface CartMeal {
  id: string
  name: string
  image_url: string | null
  price_nok: string
  available: boolean
}

export interface CartItem {
  id: string
  quantity: number
  line_total_nok: string
  meal: CartMeal
}

export interface Cart {
  items: CartItem[]
  total_quantity: number
  total_nok: string
}

export class CartRequestError extends Error {
  constructor(public readonly status: number) {
    super(`Cart request failed with status ${status}`)
  }
}

export async function fetchCart(
  accessToken: string,
  signal?: AbortSignal,
): Promise<Cart> {
  return cartRequest('/api/cart', accessToken, { signal })
}

export async function addCartItem(
  accessToken: string,
  mealId: string,
): Promise<Cart> {
  return cartRequest('/api/cart/items', accessToken, {
    method: 'POST',
    body: JSON.stringify({ meal_id: mealId, quantity: 1 }),
  })
}

export async function updateCartItem(
  accessToken: string,
  itemId: string,
  quantity: number,
): Promise<Cart> {
  return cartRequest(`/api/cart/items/${itemId}`, accessToken, {
    method: 'PATCH',
    body: JSON.stringify({ quantity }),
  })
}

export async function removeCartItem(
  accessToken: string,
  itemId: string,
): Promise<void> {
  const response = await fetch(apiUrl(`/api/cart/items/${itemId}`), {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (!response.ok) {
    throw new CartRequestError(response.status)
  }
}

async function cartRequest(
  path: string,
  accessToken: string,
  init: RequestInit,
): Promise<Cart> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: {
      Accept: 'application/json',
      Authorization: `Bearer ${accessToken}`,
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
    },
  })
  if (!response.ok) {
    throw new CartRequestError(response.status)
  }
  return (await response.json()) as Cart
}
