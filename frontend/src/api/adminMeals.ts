import { apiUrl } from './config'
import type { Allergen, MealDetail } from './meals'

export interface AdminMealWrite {
  name: string
  description: string
  image_url: string | null
  price_nok: number
  calories: number
  protein_grams: number
  carbohydrate_grams: number
  fat_grams: number
  ingredients: string[]
  allergen_codes: string[]
  available: boolean
}

export class AdminMealRequestError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string | null,
  ) {
    super(`Admin meal request failed with status ${status}`)
  }
}

export function fetchAdminMeals(
  accessToken: string,
  signal?: AbortSignal,
): Promise<MealDetail[]> {
  return adminRequest('/api/admin/meals', accessToken, { signal })
}

export function fetchAdminAllergens(
  accessToken: string,
  signal?: AbortSignal,
): Promise<Allergen[]> {
  return adminRequest('/api/admin/meals/allergens', accessToken, { signal })
}

export function createAdminMeal(
  accessToken: string,
  payload: AdminMealWrite,
): Promise<MealDetail> {
  return adminRequest('/api/admin/meals', accessToken, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateAdminMeal(
  accessToken: string,
  mealId: string,
  payload: AdminMealWrite,
): Promise<MealDetail> {
  return adminRequest(`/api/admin/meals/${mealId}`, accessToken, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

async function adminRequest<T>(
  path: string,
  accessToken: string,
  init: RequestInit,
): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: {
      Accept: 'application/json',
      Authorization: `Bearer ${accessToken}`,
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
    },
  })
  if (!response.ok) {
    let detail: string | null = null
    try {
      const body = (await response.json()) as { detail?: unknown }
      detail = typeof body.detail === 'string' ? body.detail : null
    } catch {
      // Status is enough when the backend did not return a JSON error.
    }
    throw new AdminMealRequestError(response.status, detail)
  }
  return (await response.json()) as T
}
