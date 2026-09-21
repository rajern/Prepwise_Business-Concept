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

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export async function fetchMeals(signal?: AbortSignal): Promise<Meal[]> {
  const response = await fetch(`${apiBaseUrl}/api/meals`, {
    headers: { Accept: 'application/json' },
    signal,
  })

  if (!response.ok) {
    throw new Error(`Meal request failed with status ${response.status}`)
  }

  return (await response.json()) as Meal[]
}
