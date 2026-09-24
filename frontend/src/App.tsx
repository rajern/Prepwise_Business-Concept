import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  addCartItem,
  type Cart,
  CartRequestError,
  fetchCart,
  removeCartItem,
  updateCartItem,
} from './api/cart'
import {
  fetchMeal,
  fetchMeals,
  MealRequestError,
  type Meal,
  type MealDetail,
} from './api/meals'
import {
  fetchPickupLocations,
  type PickupLocation,
} from './api/pickupLocations'
import { AuthControls } from './auth/AuthControls'

const nokFormatter = new Intl.NumberFormat('nb-NO', {
  style: 'currency',
  currency: 'NOK',
  maximumFractionDigits: 0,
})

type CatalogueFilter = 'all' | 'high-protein' | 'under-600'

interface AppProps {
  apiScope: string
  initialAccessToken?: string | null
}

export function App({ apiScope, initialAccessToken = null }: AppProps) {
  const [meals, setMeals] = useState<Meal[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [requestNumber, setRequestNumber] = useState(0)
  const [searchQuery, setSearchQuery] = useState('')
  const [catalogueFilter, setCatalogueFilter] =
    useState<CatalogueFilter>('all')
  const [selectedMealId, setSelectedMealId] = useState<string | null>(null)
  const [mealDetail, setMealDetail] = useState<MealDetail | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [accessToken, setAccessToken] = useState<string | null>(initialAccessToken)
  const [cart, setCart] = useState<Cart | null>(null)
  const [cartError, setCartError] = useState<string | null>(null)
  const [cartMutationKey, setCartMutationKey] = useState<string | null>(null)
  const [pickupLocations, setPickupLocations] = useState<PickupLocation[] | null>(
    null,
  )
  const [selectedPickupId, setSelectedPickupId] = useState('')

  const handleAccessTokenChange = useCallback((nextAccessToken: string | null) => {
    setAccessToken(nextAccessToken)
    setCart(null)
    setCartError(null)
    setPickupLocations(null)
    setSelectedPickupId('')
  }, [])

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

  useEffect(() => {
    if (!accessToken) {
      return
    }

    const controller = new AbortController()

    void fetchCart(accessToken, controller.signal)
      .then(setCart)
      .catch((reason: unknown) => {
        if (!(reason instanceof DOMException && reason.name === 'AbortError')) {
          setCartError('We could not load your cart. Please try again.')
        }
      })

    void fetchPickupLocations(controller.signal)
      .then(setPickupLocations)
      .catch((reason: unknown) => {
        if (!(reason instanceof DOMException && reason.name === 'AbortError')) {
          setCartError('We could not load the pickup locations. Please try again.')
        }
      })

    return () => controller.abort()
  }, [accessToken])

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

  async function addMeal(mealId: string) {
    if (!accessToken) {
      return
    }
    await runCartMutation(`meal-${mealId}`, () => addCartItem(accessToken, mealId))
  }

  async function changeQuantity(itemId: string, quantity: number) {
    if (!accessToken) {
      return
    }
    await runCartMutation(itemId, () =>
      updateCartItem(accessToken, itemId, quantity),
    )
  }

  async function removeItem(itemId: string) {
    if (!accessToken) {
      return
    }
    setCartMutationKey(itemId)
    setCartError(null)
    try {
      await removeCartItem(accessToken, itemId)
      setCart(await fetchCart(accessToken))
    } catch {
      setCartError('We could not update your cart. Please try again.')
    } finally {
      setCartMutationKey(null)
    }
  }

  async function runCartMutation(
    key: string,
    mutation: () => Promise<Cart>,
  ) {
    setCartMutationKey(key)
    setCartError(null)
    try {
      setCart(await mutation())
    } catch (reason: unknown) {
      setCartError(
        reason instanceof CartRequestError && reason.status === 409
          ? 'That meal is no longer available.'
          : 'We could not update your cart. Please try again.',
      )
    } finally {
      setCartMutationKey(null)
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Prepwise home">
          Prepwise
        </a>
        <AuthControls
          apiScope={apiScope}
          onAccessTokenChange={handleAccessTokenChange}
        />
      </header>
      <section className="hero">
        <p className="eyebrow">Pickup meals in Oslo</p>
        <h1>Ready meals, without the guesswork.</h1>
        <p className="summary">
          Pick balanced meals with clear nutrition and collect them from a
          convenient location in Oslo.
        </p>
      </section>

      {accessToken && (
        <CartPanel
          cart={cart}
          error={cartError}
          mutationKey={cartMutationKey}
          pickupLocations={pickupLocations}
          selectedPickupId={selectedPickupId}
          onPickupChange={setSelectedPickupId}
          onQuantityChange={changeQuantity}
          onRemove={removeItem}
        />
      )}

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
            canAdd={Boolean(accessToken)}
            isAdding={
              mealDetail ? cartMutationKey === `meal-${mealDetail.id}` : false
            }
            onAdd={addMeal}
            onClose={closeMealDetails}
          />
        )}

        {filteredMeals.length > 0 && (
          <div className="meal-grid">
            {filteredMeals.map((meal) => (
              <MealCard
                key={meal.id}
                meal={meal}
                canAdd={Boolean(accessToken)}
                isAdding={cartMutationKey === `meal-${meal.id}`}
                onAdd={() => void addMeal(meal.id)}
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
  canAdd: boolean
  isAdding: boolean
  onAdd: () => void
  onOpen: () => void
}

function MealCard({ meal, canAdd, isAdding, onAdd, onOpen }: MealCardProps) {
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
        <div className="meal-actions">
          <button className="detail-button" type="button" onClick={onOpen}>
            View details
          </button>
          <button
            className="add-button"
            type="button"
            disabled={!canAdd || isAdding}
            onClick={onAdd}
          >
            {isAdding ? 'Adding…' : canAdd ? 'Add to cart' : 'Sign in to add'}
          </button>
        </div>
      </div>
    </article>
  )
}

interface MealDetailPanelProps {
  detail: MealDetail | null
  error: string | null
  canAdd: boolean
  isAdding: boolean
  onAdd: (mealId: string) => Promise<void>
  onClose: () => void
}

function MealDetailPanel({
  detail,
  error,
  canAdd,
  isAdding,
  onAdd,
  onClose,
}: MealDetailPanelProps) {
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
            <button
              className="add-button add-button--detail"
              type="button"
              disabled={!canAdd || !detail.available || isAdding}
              onClick={() => void onAdd(detail.id)}
            >
              {isAdding
                ? 'Adding…'
                : !detail.available
                  ? 'Currently unavailable'
                  : canAdd
                    ? 'Add to cart'
                    : 'Sign in to add'}
            </button>
          </div>
        </div>
      )}
    </section>
  )
}

interface CartPanelProps {
  cart: Cart | null
  error: string | null
  mutationKey: string | null
  pickupLocations: PickupLocation[] | null
  selectedPickupId: string
  onPickupChange: (locationId: string) => void
  onQuantityChange: (itemId: string, quantity: number) => Promise<void>
  onRemove: (itemId: string) => Promise<void>
}

function CartPanel({
  cart,
  error,
  mutationKey,
  pickupLocations,
  selectedPickupId,
  onPickupChange,
  onQuantityChange,
  onRemove,
}: CartPanelProps) {
  return (
    <section className="cart-panel" aria-labelledby="cart-heading">
      <div className="cart-panel__heading">
        <div>
          <p className="eyebrow">Your order</p>
          <h2 id="cart-heading">Shopping cart</h2>
        </div>
        {cart && (
          <span className="cart-count">
            {cart.total_quantity} {cart.total_quantity === 1 ? 'meal' : 'meals'}
          </span>
        )}
      </div>

      {!cart && !error && (
        <div className="cart-state" role="status">
          Loading your cart…
        </div>
      )}
      {error && (
        <div className="cart-state cart-state--error" role="alert">
          {error}
        </div>
      )}
      {cart && cart.items.length === 0 && (
        <div className="cart-state">Your cart is empty. Add a meal below.</div>
      )}

      {cart && cart.items.length > 0 && (
        <div className="cart-layout">
          <div className="cart-items">
            {cart.items.map((item) => {
              const isMutating = mutationKey === item.id
              return (
                <article className="cart-item" key={item.id}>
                  <div>
                    <h3>{item.meal.name}</h3>
                    <p>
                      {nokFormatter.format(Number(item.meal.price_nok))} each
                      {!item.meal.available && (
                        <span className="cart-item__unavailable">
                          {' '}· unavailable
                        </span>
                      )}
                    </p>
                  </div>
                  <div className="quantity-control" aria-label={`Quantity for ${item.meal.name}`}>
                    <button
                      type="button"
                      disabled={isMutating || item.quantity <= 1}
                      aria-label={`Decrease ${item.meal.name}`}
                      onClick={() =>
                        void onQuantityChange(item.id, item.quantity - 1)
                      }
                    >
                      −
                    </button>
                    <span>{item.quantity}</span>
                    <button
                      type="button"
                      disabled={
                        isMutating || !item.meal.available || item.quantity >= 99
                      }
                      aria-label={`Increase ${item.meal.name}`}
                      onClick={() =>
                        void onQuantityChange(item.id, item.quantity + 1)
                      }
                    >
                      +
                    </button>
                  </div>
                  <strong>{nokFormatter.format(Number(item.line_total_nok))}</strong>
                  <button
                    className="remove-button"
                    type="button"
                    disabled={isMutating}
                    onClick={() => void onRemove(item.id)}
                  >
                    Remove
                  </button>
                </article>
              )
            })}
          </div>

          <aside className="cart-summary">
            <div className="cart-total">
              <span>Total</span>
              <strong>{nokFormatter.format(Number(cart.total_nok))}</strong>
            </div>
            <label className="pickup-field">
              <span>Pickup location</span>
              <select
                value={selectedPickupId}
                disabled={!pickupLocations || pickupLocations.length === 0}
                onChange={(event) => onPickupChange(event.target.value)}
              >
                <option value="">Choose a pickup location</option>
                {pickupLocations?.map((location) => (
                  <option key={location.id} value={location.id}>
                    {location.name} — {location.address_line}, {location.postal_code}{' '}
                    {location.city}
                  </option>
                ))}
              </select>
            </label>
            <p className="checkout-note">
              Your cart and quantities are saved to your account. Checkout is the
              next step.
            </p>
          </aside>
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
