import { apiUrl } from './config'
import { apiRequestError } from './errors'
import type { Language } from '../i18n'

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

export async function fetchCart(
  accessToken: string,
  signal?: AbortSignal,
  language: Language = 'no',
): Promise<Cart> {
  return cartRequest(`/api/cart?lang=${language}`, accessToken, { signal })
}

export async function addCartItem(
  accessToken: string,
  mealId: string,
  language: Language = 'no',
): Promise<Cart> {
  return cartRequest(`/api/cart/items?lang=${language}`, accessToken, {
    method: 'POST',
    body: JSON.stringify({ meal_id: mealId, quantity: 1 }),
  })
}

export async function updateCartItem(
  accessToken: string,
  itemId: string,
  quantity: number,
  language: Language = 'no',
): Promise<Cart> {
  return cartRequest(`/api/cart/items/${itemId}?lang=${language}`, accessToken, {
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
    throw await apiRequestError(response)
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
    throw await apiRequestError(response)
  }
  return (await response.json()) as Cart
}
