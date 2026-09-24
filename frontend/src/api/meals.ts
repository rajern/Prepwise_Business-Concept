import { apiUrl } from './config'
import { apiRequestError } from './errors'

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

export async function fetchMeals(signal?: AbortSignal): Promise<Meal[]> {
  const response = await fetch(apiUrl('/api/meals'), {
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
): Promise<MealDetail> {
  const response = await fetch(apiUrl(`/api/meals/${mealId}`), {
    headers: { Accept: 'application/json' },
    signal,
  })

  if (!response.ok) {
    throw await apiRequestError(response)
  }

  return (await response.json()) as MealDetail
}
