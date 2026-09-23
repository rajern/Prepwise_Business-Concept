import { useEffect, useMemo, useState } from 'react'

import {
  fetchMeal,
  fetchMeals,
  MealRequestError,
  type Meal,
  type MealDetail,
} from './api/meals'
import { AuthControls } from './auth/AuthControls'

const nokFormatter = new Intl.NumberFormat('nb-NO', {
  style: 'currency',
  currency: 'NOK',
  maximumFractionDigits: 0,
})

type CatalogueFilter = 'all' | 'high-protein' | 'under-600'

interface AppProps {
  apiScope: string
}

export function App({ apiScope }: AppProps) {
  const [meals, setMeals] = useState<Meal[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [requestNumber, setRequestNumber] = useState(0)
  const [searchQuery, setSearchQuery] = useState('')
  const [catalogueFilter, setCatalogueFilter] =
    useState<CatalogueFilter>('all')
  const [selectedMealId, setSelectedMealId] = useState<string | null>(null)
  const [mealDetail, setMealDetail] = useState<MealDetail | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)

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

  useEffect(() => {
    if (!selectedMealId) {
      return
    }

    const controller = new AbortController()

    void fetchMeal(selectedMealId, controller.signal)
      .then(setMealDetail)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === 'AbortError') {
          return
        }
        setDetailError(
          reason instanceof MealRequestError && reason.status === 404
            ? 'This meal could not be found. It may have been removed.'
            : 'We could not load the meal details. Please try again.',
        )
      })

    return () => controller.abort()
  }, [selectedMealId])

  const filteredMeals = useMemo(() => {
    if (!meals) {
      return []
    }

    const normalizedQuery = searchQuery.trim().toLocaleLowerCase()
    return meals.filter((meal) => {
      const searchableText = [meal.name, meal.description, ...meal.ingredients]
        .join(' ')
        .toLocaleLowerCase()
      const matchesSearch =
        normalizedQuery.length === 0 || searchableText.includes(normalizedQuery)
      const matchesFilter =
        catalogueFilter === 'all' ||
        (catalogueFilter === 'high-protein' &&
          Number(meal.protein_grams) >= 40) ||
        (catalogueFilter === 'under-600' && meal.calories < 600)

      return matchesSearch && matchesFilter
    })
  }, [catalogueFilter, meals, searchQuery])

  function retryLoadingMeals() {
    setMeals(null)
    setError(null)
    setRequestNumber((value) => value + 1)
  }

  function closeMealDetails() {
    setSelectedMealId(null)
    setMealDetail(null)
    setDetailError(null)
  }

  function openMealDetails(mealId: string) {
    setMealDetail(null)
    setDetailError(null)
    setSelectedMealId(mealId)
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Prepwise home">
          Prepwise
        </a>
        <AuthControls apiScope={apiScope} />
      </header>
      <section className="hero">
        <p className="eyebrow">Pickup meals in Oslo</p>
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
          {meals && (
            <p className="meal-count" aria-live="polite">
              {filteredMeals.length === meals.length
                ? `${meals.length} meals available`
                : `${filteredMeals.length} of ${meals.length} meals shown`}
            </p>
          )}
        </div>

        {meals && meals.length > 0 && (
          <div className="catalogue-tools" aria-label="Filter meals">
            <label className="filter-field filter-field--search">
              <span>Search</span>
              <input
                type="search"
                value={searchQuery}
                placeholder="Meal or ingredient"
                onChange={(event) => setSearchQuery(event.target.value)}
              />
            </label>
            <label className="filter-field">
              <span>Nutrition</span>
              <select
                value={catalogueFilter}
                onChange={(event) =>
                  setCatalogueFilter(event.target.value as CatalogueFilter)
                }
              >
                <option value="all">All meals</option>
                <option value="high-protein">40 g+ protein</option>
                <option value="under-600">Under 600 kcal</option>
              </select>
            </label>
          </div>
        )}

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

        {meals && meals.length > 0 && filteredMeals.length === 0 && (
          <div className="state-panel">
            No meals match those filters. Try a different search or nutrition
            filter.
          </div>
        )}

        {selectedMealId && (
          <MealDetailPanel
            detail={mealDetail}
            error={detailError}
            onClose={closeMealDetails}
          />
        )}

        {filteredMeals.length > 0 && (
          <div className="meal-grid">
            {filteredMeals.map((meal) => (
              <MealCard
                key={meal.id}
                meal={meal}
                onOpen={() => openMealDetails(meal.id)}
              />
            ))}
          </div>
        )}
      </section>
    </main>
  )
}

interface MealCardProps {
  meal: Meal
  onOpen: () => void
}

function MealCard({ meal, onOpen }: MealCardProps) {
  return (
    <article className="meal-card">
      <MealArtwork meal={meal} />
      <div className="meal-card__body">
        <div className="meal-card__topline">
          <span>{meal.calories} kcal</span>
          <strong>{nokFormatter.format(Number(meal.price_nok))}</strong>
        </div>
        <h3>{meal.name}</h3>
        <p className="meal-description">{meal.description}</p>
        <Nutrition meal={meal} />
        <div className="allergens" aria-label="Allergens">
          {meal.allergens.length > 0 ? (
            meal.allergens.map((allergen) => (
              <span key={allergen.code}>{allergen.name}</span>
            ))
          ) : (
            <span className="allergens__none">No declared allergens</span>
          )}
        </div>
        <button className="detail-button" type="button" onClick={onOpen}>
          View details
        </button>
      </div>
    </article>
  )
}

interface MealDetailPanelProps {
  detail: MealDetail | null
  error: string | null
  onClose: () => void
}

function MealDetailPanel({ detail, error, onClose }: MealDetailPanelProps) {
  return (
    <section className="meal-detail" aria-labelledby="meal-detail-heading">
      <div className="meal-detail__header">
        <p className="eyebrow">Meal details</p>
        <button className="close-button" type="button" onClick={onClose}>
          Close
        </button>
      </div>

      {!detail && !error && (
        <div className="meal-detail__state" role="status">
          Loading meal details…
        </div>
      )}

      {error && (
        <div className="meal-detail__state meal-detail__state--error" role="alert">
          {error}
        </div>
      )}

      {detail && (
        <div className="meal-detail__content">
          <MealArtwork meal={detail} detail />
          <div>
            <div className="meal-detail__status-row">
              <span
                className={`availability ${
                  detail.available ? '' : 'availability--unavailable'
                }`}
              >
                {detail.available ? 'Available this week' : 'Currently unavailable'}
              </span>
              <strong>{nokFormatter.format(Number(detail.price_nok))}</strong>
            </div>
            <h3 id="meal-detail-heading">{detail.name}</h3>
            <p className="meal-detail__description">{detail.description}</p>
            <Nutrition meal={detail} />
            <div className="meal-detail__facts">
              <div>
                <h4>Ingredients</h4>
                <p>{detail.ingredients.join(', ')}</p>
              </div>
              <div>
                <h4>Allergens</h4>
                <p>
                  {detail.allergens.length > 0
                    ? detail.allergens.map((allergen) => allergen.name).join(', ')
                    : 'No declared allergens'}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

function MealArtwork({ meal, detail = false }: { meal: Meal; detail?: boolean }) {
  if (meal.image_url) {
    return (
      <img
        className={`meal-artwork ${detail ? 'meal-artwork--detail' : ''}`}
        src={meal.image_url}
        alt={meal.name}
      />
    )
  }

  return (
    <div
      className={`meal-artwork meal-artwork--placeholder ${
        detail ? 'meal-artwork--detail' : ''
      }`}
      role="img"
      aria-label={`No image available for ${meal.name}`}
    >
      <span>Prepwise kitchen</span>
    </div>
  )
}

function Nutrition({ meal }: { meal: Meal }) {
  return (
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
  )
}
