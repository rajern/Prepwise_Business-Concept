import { apiUrl } from './config'

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

export async function fetchMeals(signal?: AbortSignal): Promise<Meal[]> {
  const response = await fetch(apiUrl('/api/meals'), {
    headers: { Accept: 'application/json' },
    signal,
  })

  if (!response.ok) {
    throw new Error(`Meal request failed with status ${response.status}`)
  }

  return (await response.json()) as Meal[]
}
