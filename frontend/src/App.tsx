import { useEffect, useState } from 'react'

import { fetchMeals, type Meal } from './api/meals'

const nokFormatter = new Intl.NumberFormat('nb-NO', {
  style: 'currency',
  currency: 'NOK',
  maximumFractionDigits: 0,
})

export function App() {
  const [meals, setMeals] = useState<Meal[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [requestNumber, setRequestNumber] = useState(0)

  useEffect(() => {
    const controller = new AbortController()

    void fetchMeals(controller.signal)
      .then(setMeals)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === 'AbortError') {
          return
        }
        setError('We could not load the menu. Please try again.')
      })

    return () => controller.abort()
  }, [requestNumber])

  function retryLoadingMeals() {
    setMeals(null)
    setError(null)
    setRequestNumber((value) => value + 1)
  }

  return (
    <main className="app-shell">
      <section className="hero">
        <p className="eyebrow">Prepwise</p>
        <h1>Ready meals, without the guesswork.</h1>
        <p className="summary">
          Pick balanced meals with clear nutrition and collect them from a
          convenient location in Oslo.
        </p>
      </section>

      <section className="catalogue" aria-labelledby="catalogue-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">This week</p>
            <h2 id="catalogue-heading">Choose your meals</h2>
          </div>
          {meals && <p className="meal-count">{meals.length} meals available</p>}
        </div>

        {meals === null && error === null && (
          <div className="state-panel" role="status">
            Loading the menu…
          </div>
        )}

        {error && (
          <div className="state-panel state-panel--error" role="alert">
            <p>{error}</p>
            <button type="button" onClick={retryLoadingMeals}>
              Try again
            </button>
          </div>
        )}

        {meals && meals.length === 0 && (
          <div className="state-panel">No meals are available right now.</div>
        )}

        {meals && meals.length > 0 && (
          <div className="meal-grid">
            {meals.map((meal) => (
              <article className="meal-card" key={meal.id}>
                <div className="meal-card__topline">
                  <span>{meal.calories} kcal</span>
                  <strong>{nokFormatter.format(Number(meal.price_nok))}</strong>
                </div>
                <h3>{meal.name}</h3>
                <p className="meal-description">{meal.description}</p>

                <dl className="nutrition" aria-label={`Nutrition for ${meal.name}`}>
                  <div>
                    <dt>Protein</dt>
                    <dd>{Number(meal.protein_grams)} g</dd>
                  </div>
                  <div>
                    <dt>Carbs</dt>
                    <dd>{Number(meal.carbohydrate_grams)} g</dd>
                  </div>
                  <div>
                    <dt>Fat</dt>
                    <dd>{Number(meal.fat_grams)} g</dd>
                  </div>
                </dl>

                <p className="ingredients">
                  <span>Ingredients</span>
                  {meal.ingredients.join(', ')}
                </p>

                <div className="allergens" aria-label="Allergens">
                  {meal.allergens.length > 0 ? (
                    meal.allergens.map((allergen) => (
                      <span key={allergen.code}>{allergen.name}</span>
                    ))
                  ) : (
                    <span className="allergens__none">No declared allergens</span>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  )
}
