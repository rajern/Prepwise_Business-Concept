import { apiUrl } from './config'
import { apiRequestError } from './errors'
import type { Language } from '../i18n'
import { authenticatedFetch } from '../auth/authenticatedFetch'

export interface CartMeal {
  id: string
  name: string
  image_url: string | null
  price_nok: string
  available: boolean
}

export interface CartItem {
  id: string
  group_id?: string | null
  quantity: number
  line_total_nok: string
  meal: CartMeal
}

export interface Cart {
  items: CartItem[]
  groups?: CartGroup[]
  total_quantity: number
  total_nok: string
}

export interface CartGroup {
  id: string
  version: string
  pickup_location_id: string | null
  pickup_date: string | null
  pickup_slot: string | null
  items: CartItem[]
  total_quantity: number
  total_nok: string
}
export interface GroupSelection {
  expected_version?: string
  pickup_location_id?: string | null
  pickup_date?: string | null
  pickup_slot?: string | null
}
export async function createCartGroup(token: string, language: Language): Promise<Cart> {
  return cartRequest(`/api/cart/groups?lang=${language}`, token, { method: 'POST', body: '{}' })
}
export async function saveCartGroup(token: string, groupId: string, selection: GroupSelection, language: Language): Promise<Cart> {
  return cartRequest(`/api/cart/groups/${groupId}?lang=${language}`, token, { method: 'PATCH', body: JSON.stringify(selection) })
}
export async function deleteCartGroup(token: string, groupId: string): Promise<void> {
  const response = await authenticatedFetch(apiUrl(`/api/cart/groups/${groupId}`), token, { method: 'DELETE' })
  if (!response.ok) throw await apiRequestError(response)
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
  groupId?: string | null,
): Promise<Cart> {
  return cartRequest(`/api/cart/items?lang=${language}`, accessToken, {
    method: 'POST',
    body: JSON.stringify({ meal_id: mealId, quantity: 1, ...(groupId !== undefined ? { group_id: groupId } : {}) }),
  })
}

export async function updateCartItem(
  accessToken: string,
  itemId: string,
  quantity: number,
  language: Language = 'no',
  groupId?: string | null,
  expectedQuantity?: number,
  expectedGroupId?: string | null,
): Promise<Cart> {
  return cartRequest(`/api/cart/items/${itemId}?lang=${language}`, accessToken, {
    method: 'PATCH',
    body: JSON.stringify({ quantity, expected_quantity: expectedQuantity, expected_group_id: expectedGroupId, ...(groupId !== undefined ? { group_id: groupId } : {}) }),
  })
}

export async function removeCartItem(
  accessToken: string,
  itemId: string,
): Promise<void> {
  const response = await authenticatedFetch(apiUrl(`/api/cart/items/${itemId}`), accessToken, {
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
  const response = await authenticatedFetch(apiUrl(path), accessToken, {
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
