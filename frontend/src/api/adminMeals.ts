import { apiUrl } from './config'
import { apiRequestError } from './errors'
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
    throw await apiRequestError(response)
  }
  return (await response.json()) as T
}
