import { apiUrl } from './config'
import { apiRequestError } from './errors'
import type { Language } from '../i18n'

export interface Allergen {
  code: string
  name: string
}

export interface Meal {
  id: string
  name: string
  description: string
  image_url: string | null
  price_nok: string
  calories: number
  protein_grams: string
  carbohydrate_grams: string
  fat_grams: string
  ingredients: string[]
  allergens: Allergen[]
}

export interface MealDetail extends Meal {
  available: boolean
}

export async function fetchMeals(signal?: AbortSignal, language: Language = 'no'): Promise<Meal[]> {
  const response = await fetch(apiUrl(`/api/meals?lang=${language}`), {
    headers: { Accept: 'application/json' },
    signal,
  })

  if (!response.ok) {
    throw await apiRequestError(response)
  }

  return (await response.json()) as Meal[]
}

export async function fetchMeal(
  mealId: string,
  signal?: AbortSignal,
  language: Language = 'no',
): Promise<MealDetail> {
  const response = await fetch(apiUrl(`/api/meals/${mealId}?lang=${language}`), {
    headers: { Accept: 'application/json' },
    signal,
  })

  if (!response.ok) {
    throw await apiRequestError(response)
  }

  return (await response.json()) as MealDetail
}
