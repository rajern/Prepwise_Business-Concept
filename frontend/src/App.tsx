import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  addCartItem,
  type Cart,
  fetchCart,
  removeCartItem,
  updateCartItem,
} from './api/cart'
import { ApiRequestError } from './api/errors'
import {
  fetchMeal,
  fetchMeals,
  type Meal,
  type MealDetail,
} from './api/meals'
import {
  fetchPickupLocations,
  type PickupLocation,
} from './api/pickupLocations'
import {
  createOrder,
  fetchOrder,
  fetchOrders,
  type OrderDetail,
  type OrderSummary,
} from './api/orders'
import type { CurrentUser } from './api/me'
import { AdminPage } from './admin/AdminPage'
import { AssistantPanel } from './assistant/AssistantPanel'
import { AuthControls } from './auth/AuthControls'
import { fetchPickupOptions, type PickupOptions } from './api/pickupOptions'
import { LanguageProvider, useLanguage, formatNok, formatPickup } from './i18n'
import { CartDrawer } from './components/CartDrawer'
import { MealArtwork } from './components/MealArtwork'

type CatalogueFilter = 'all' | 'high-protein' | 'under-600'

interface AppProps {
  apiScope: string
  initialAccessToken?: string | null
  initialCurrentUser?: CurrentUser | null
  isE2ESession?: boolean
}

export function App(props: AppProps) {
  return <LanguageProvider><AppContent {...props} /></LanguageProvider>
}

function AppContent({
  apiScope,
  initialAccessToken = null,
  initialCurrentUser = null,
  isE2ESession = false,
}: AppProps) {
  const { language, setLanguage, t } = useLanguage()
  const customerError = useCallback((reason: unknown, fallback: string): string => {
    const message = reason instanceof ApiRequestError && reason.status === 401
      ? t('Your session has expired. Sign in again.')
      : reason instanceof ApiRequestError && reason.status === 403
        ? t('You do not have permission to perform this action.') : t(fallback)
    return reason instanceof ApiRequestError && reason.status >= 500 && reason.requestId
      ? `${message} ${language === 'no' ? 'Referanse' : 'Reference'}: ${reason.requestId}` : message
  }, [language, t])
  const isAdminRoute = window.location.pathname.startsWith('/admin')
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
  const [pickupOptions, setPickupOptions] = useState<PickupOptions | null>(null)
  const [selectedPickupDate, setSelectedPickupDate] = useState('')
  const [selectedPickupSlot, setSelectedPickupSlot] = useState('')
  const [cartOpen, setCartOpen] = useState(false)
  const [cartNotice, setCartNotice] = useState(false)
  const sessionRef = useRef({ token: accessToken, language })
  useEffect(() => { sessionRef.current = { token: accessToken, language } }, [accessToken, language])
  const [orders, setOrders] = useState<OrderSummary[] | null>(null)
  const [ordersError, setOrdersError] = useState<string | null>(null)
  const [selectedOrder, setSelectedOrder] = useState<OrderDetail | null>(null)
  const [orderDetailError, setOrderDetailError] = useState<string | null>(null)
  const [isCheckingOut, setIsCheckingOut] = useState(false)
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(
    initialCurrentUser,
  )

  const handleAccessTokenChange = useCallback((nextAccessToken: string | null) => {
    setAccessToken(nextAccessToken)
    setCart(null)
    setCartError(null)
    setPickupLocations(null)
    setSelectedPickupId('')
    setSelectedPickupDate('')
    setSelectedPickupSlot('')
    setOrders(null)
    setOrdersError(null)
    setSelectedOrder(null)
    setOrderDetailError(null)
    if (!nextAccessToken) {
      setCartOpen(false)
      setCartNotice(false)
      setCurrentUser(null)
    }
  }, [])

  useEffect(() => {
    if (isAdminRoute) {
      return
    }
    const controller = new AbortController()

    void fetchMeals(controller.signal, language)
      .then(setMeals)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === 'AbortError') {
          return
        }
        setError(customerError(reason, t('We could not load the menu. Please try again.')))
      })

    return () => controller.abort()
  }, [isAdminRoute, requestNumber, language, customerError, t])

  useEffect(() => {
    if (!selectedMealId) {
      return
    }

    const controller = new AbortController()

    void fetchMeal(selectedMealId, controller.signal, language)
      .then(setMealDetail)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === 'AbortError') {
          return
        }
        setDetailError(
          reason instanceof ApiRequestError && reason.status === 404
            ? t('This meal could not be found. It may have been removed.')
            : customerError(
                reason,
                t('We could not load the meal details. Please try again.'),
              ),
        )
      })

    return () => controller.abort()
  }, [selectedMealId, language, customerError, t])

  useEffect(() => {
    if (!accessToken || isAdminRoute) {
      return
    }

    const controller = new AbortController()

    void fetchCart(accessToken, controller.signal, language)
      .then(setCart)
      .catch((reason: unknown) => {
        if (!(reason instanceof DOMException && reason.name === 'AbortError')) {
          setCartError(
            customerError(reason, t('We could not load your cart. Please try again.')),
          )
        }
      })

    void fetchPickupLocations(controller.signal)
      .then(setPickupLocations)
      .catch((reason: unknown) => {
        if (!(reason instanceof DOMException && reason.name === 'AbortError')) {
          setCartError(
            customerError(
              reason,
              t('We could not load the pickup locations. Please try again.'),
            ),
          )
        }
      })

    void fetchPickupOptions(controller.signal).then(setPickupOptions).catch((reason: unknown) => {
      if (!(reason instanceof DOMException && reason.name === 'AbortError')) {
        setCartError(t('We could not load the pickup times. Please try again.'))
      }
    })

    void fetchOrders(accessToken, controller.signal, language)
      .then(setOrders)
      .catch((reason: unknown) => {
        if (!(reason instanceof DOMException && reason.name === 'AbortError')) {
          setOrdersError(
            customerError(
              reason,
              t('We could not load your order history. Please try again.'),
            ),
          )
        }
      })

    return () => controller.abort()
  }, [accessToken, isAdminRoute, language, customerError, t])

  const selectedOrderId = selectedOrder?.id
  useEffect(() => {
    if (!accessToken || !selectedOrderId) return
    const controller = new AbortController()
    void fetchOrder(accessToken, selectedOrderId, controller.signal, language)
      .then(setSelectedOrder)
      .catch((reason: unknown) => {
        if (!(reason instanceof DOMException && reason.name === 'AbortError')) {
          setOrderDetailError(customerError(reason, 'We could not load that order. Please try again.'))
        }
      })
    return () => controller.abort()
  }, [accessToken, selectedOrderId, language, customerError])

  useEffect(() => {
    if (!cartNotice) return
    const timer = window.setTimeout(() => setCartNotice(false), 4000)
    return () => window.clearTimeout(timer)
  }, [cartNotice])

  async function refreshCustomerState() {
    if (!accessToken) return
    const expected = { token: accessToken, language }
    const results = await Promise.allSettled([
      fetchCart(accessToken, undefined, language), fetchOrders(accessToken, undefined, language),
    ])
    if (sessionRef.current.token !== expected.token || sessionRef.current.language !== expected.language) return
    if (results[0].status === 'fulfilled') setCart(results[0].value)
    if (results[1].status === 'fulfilled') setOrders(results[1].value)
    if (results.some((result) => result.status === 'rejected')) {
      setCartError(t('We could not refresh your cart and orders. Open the cart to try again.'))
    }
  }

  async function openCart() {
    setCartOpen(true)
    if (!accessToken) return
    setCartError(null)
    await Promise.all([
      refreshCustomerState(),
      fetchPickupOptions().then((options) => {
        setPickupOptions(options)
        if (!options.days.some((day) => day.date === selectedPickupDate)) {
          setSelectedPickupDate(''); setSelectedPickupSlot('')
        }
      }).catch(() => setCartError(t('We could not load the pickup times. Please try again.'))),
    ])
  }

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
    await runCartMutation(`meal-${mealId}`, () => addCartItem(accessToken, mealId, language), true)
  }

  async function changeQuantity(itemId: string, quantity: number) {
    if (!accessToken) {
      return
    }
    await runCartMutation(itemId, () =>
      updateCartItem(accessToken, itemId, quantity, language),
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
      setCart(await fetchCart(accessToken, undefined, language))
    } catch (reason: unknown) {
      setCartError(
        customerError(reason, t('We could not update your cart. Please try again.')),
      )
    } finally {
      setCartMutationKey(null)
    }
  }

  async function runCartMutation(
    key: string,
    mutation: () => Promise<Cart>,
    announce = false,
  ) {
    setCartMutationKey(key)
    setCartError(null)
    try {
      setCart(await mutation())
      if (announce) setCartNotice(true)
    } catch (reason: unknown) {
      setCartError(
        reason instanceof ApiRequestError && reason.status === 409
          ? t('That meal is no longer available.')
          : customerError(
              reason,
              t('We could not update your cart. Please try again.'),
            ),
      )
    } finally {
      setCartMutationKey(null)
    }
  }

  async function checkout() {
    if (!accessToken || !cart || !selectedPickupId || !selectedPickupDate || !selectedPickupSlot) {
      return
    }
    const location = pickupLocations?.find(
      (candidate) => candidate.id === selectedPickupId,
    )
    if (!location) {
      setCartError(t('Choose an active pickup location before checkout.'))
      return
    }
    const confirmed = window.confirm(
      language === 'no'
        ? `Bestill for ${formatNok(cart.total_nok, language)} med henting på ${location.name}, ${selectedPickupDate} kl. ${selectedPickupSlot.replace('-', ':00–')}:00?`
        : `Place this order for ${formatNok(cart.total_nok, language)} with pickup at ${location.name}, ${selectedPickupDate} ${selectedPickupSlot.replace('-', ':00–')}:00?`,
    )
    if (!confirmed) {
      return
    }

    setIsCheckingOut(true)
    setCartError(null)
    try {
      const order = await createOrder(accessToken, selectedPickupId, selectedPickupDate, selectedPickupSlot, language)
      setCart({ items: [], total_quantity: 0, total_nok: '0.00' })
      setSelectedPickupId('')
      setSelectedPickupDate('')
      setSelectedPickupSlot('')
      setCartOpen(false)
      setSelectedOrder(order)
      setOrders((previous) => [order, ...(previous ?? []).filter((item) => item.id !== order.id)])
      setOrderDetailError(null)
      // Order creation has already committed. A history refresh failure must not
      // describe the checkout as failed or encourage duplicate ordering.
      try {
        setOrders(await fetchOrders(accessToken, undefined, language))
        setOrdersError(null)
      } catch (reason: unknown) {
        setOrdersError(customerError(reason, 'Your order was placed, but order history could not be refreshed.'))
      }
    } catch (reason: unknown) {
      setCartError(
        reason instanceof ApiRequestError && reason.status === 409
          ? t('Check your cart and choose a valid pickup time.')
          : customerError(
              reason,
              t('Checkout failed. Your cart has not been changed.'),
            ),
      )
    } finally {
      setIsCheckingOut(false)
    }
  }

  async function openOrder(orderId: string) {
    if (!accessToken) {
      return
    }
    setSelectedOrder(null)
    setOrderDetailError(null)
    try {
      setSelectedOrder(await fetchOrder(accessToken, orderId, undefined, language))
    } catch (reason: unknown) {
      setOrderDetailError(
        customerError(reason, t('We could not load that order. Please try again.')),
      )
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="site-navigation">
          <a className="brand" href="/" aria-label={t('Prepwise home')}>
            Prepwise
          </a>
          <nav aria-label={t('Primary navigation')}>
            <a href="/">{t('Meals')}</a>
            {currentUser?.role === 'admin' && <a href="/admin">Admin</a>}
          </nav>
        </div>
        <div className="topbar-actions">
        {!isAdminRoute && <button className="cart-toggle" type="button" onClick={() => void openCart()} aria-label={`${t('Open cart')} (${cart?.total_quantity ?? 0})`}>
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M3 3h2l2 12h12l2-9H6M9 20h.01M18 20h.01" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
          {t('Shopping cart')} <span className="cart-badge" aria-live="polite">{cart?.total_quantity ?? 0}</span>
        </button>}
        <div className="language-switch" role="group" aria-label="Language / Språk">
          <button type="button" lang="nb" aria-pressed={language === 'no'} onClick={() => setLanguage('no')}>NO</button>
          <button type="button" lang="en" aria-pressed={language === 'en'} onClick={() => setLanguage('en')}>EN</button>
        </div>
        {isE2ESession && currentUser ? (
          <div className="auth-controls auth-controls--signed-in">
            <div>
              <p className="auth-account">{currentUser.display_name}</p>
              <p className="auth-status">Signed in · test session · {currentUser.role}</p>
            </div>
          </div>
        ) : (
          <AuthControls
            apiScope={apiScope}
            onAccessTokenChange={handleAccessTokenChange}
            onCurrentUserChange={setCurrentUser}
          />
        )}
        </div>
      </header>
      {isAdminRoute ? (
        <AdminRoute accessToken={accessToken} currentUser={currentUser} />
      ) : (
        <>
      <section className="hero">
        <p className="eyebrow">{t('Pickup meals in Oslo')}</p>
        <h1>{t('Ready meals, without the guesswork.')}</h1>
        <p className="summary">{t('Pick balanced meals with clear nutrition and collect them from a convenient location in Oslo.')}</p>
      </section>

      <AssistantPanel key={currentUser?.id ?? (accessToken ? 'signed-in' : 'signed-out')} accessToken={accessToken} userId={currentUser?.id ?? null} onStateChange={refreshCustomerState} />

      <CartDrawer open={cartOpen} onClose={() => setCartOpen(false)}>
      {accessToken ? (
        <CartPanel
          cart={cart}
          error={cartError}
          mutationKey={cartMutationKey}
          pickupLocations={pickupLocations}
          selectedPickupId={selectedPickupId}
          pickupOptions={pickupOptions}
          selectedPickupDate={selectedPickupDate}
          selectedPickupSlot={selectedPickupSlot}
          isCheckingOut={isCheckingOut}
          onPickupChange={setSelectedPickupId}
          onDateChange={(date) => { setSelectedPickupDate(date); setSelectedPickupSlot('') }}
          onSlotChange={setSelectedPickupSlot}
          onCheckout={checkout}
          onQuantityChange={changeQuantity}
          onRemove={removeItem}
        />
      ) : <div className="cart-panel"><h2 id="cart-heading">{t('Shopping cart')}</h2><p>{t('Sign in to use your cart.')}</p></div>}
      </CartDrawer>

      {accessToken && ((orders?.length ?? 0) > 0 || ordersError || orderDetailError) && (
        <OrdersPanel
          orders={orders}
          error={ordersError}
          selectedOrder={selectedOrder}
          detailError={orderDetailError}
          onOpenOrder={openOrder}
        />
      )}

      <section className="catalogue" aria-labelledby="catalogue-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">{t('This week')}</p>
            <h2 id="catalogue-heading">{t('Choose your meals')}</h2>
          </div>
          {meals && (
            <p className="meal-count" aria-live="polite">
              {language === 'no'
                ? (filteredMeals.length === meals.length ? `${meals.length} måltider tilgjengelig` : `${filteredMeals.length} av ${meals.length} måltider vises`)
                : (filteredMeals.length === meals.length ? `${meals.length} meals available` : `${filteredMeals.length} of ${meals.length} meals shown`)}
            </p>
          )}
        </div>

        {meals && meals.length > 0 && (
          <div className="catalogue-tools" aria-label={t('Filter meals')}>
            <label className="filter-field filter-field--search">
              <span>{t('Search')}</span>
              <input
                type="search"
                value={searchQuery}
                placeholder={t('Meal or ingredient')}
                onChange={(event) => setSearchQuery(event.target.value)}
              />
            </label>
            <label className="filter-field">
              <span>{t('Nutrition')}</span>
              <select
                value={catalogueFilter}
                onChange={(event) =>
                  setCatalogueFilter(event.target.value as CatalogueFilter)
                }
              >
                <option value="all">{t('All meals')}</option>
                <option value="high-protein">{t('40 g+ protein')}</option>
                <option value="under-600">{t('Under 600 kcal')}</option>
              </select>
            </label>
          </div>
        )}

        {meals === null && error === null && (
          <div className="state-panel" role="status">{t('Loading the menu…')}</div>
        )}

        {error && (
          <div className="state-panel state-panel--error" role="alert">
            <p>{error}</p>
            <button type="button" onClick={retryLoadingMeals}>{t('Try again')}</button>
          </div>
        )}

        {meals && meals.length === 0 && (
          <div className="state-panel">{t('No meals are available right now.')}</div>
        )}

        {meals && meals.length > 0 && filteredMeals.length === 0 && (
          <div className="state-panel">{t('No meals match those filters. Try a different search or nutrition filter.')}</div>
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
        </>
      )}
      <footer className="site-footer">
        <div><a className="brand" href="/">Prepwise</a><p>{t('A portfolio project by Rajvir Singh Aujla.')}</p><p>{t('Prepwise is a demonstration project, not a commercial meal service.')}</p></div>
        <nav aria-label={language === 'no' ? 'Lenker' : 'Footer links'}>
          <a href="https://www.linkedin.com/in/rajvir-singh-aujla-6869912b8" target="_blank" rel="noreferrer">LinkedIn</a>
          <a href="mailto:rajvir2206@gmail.com">{t('Email')}</a>
          <a href="https://github.com/rajern/Prepwise_Business-Concept" target="_blank" rel="noreferrer">{t('Source code')}</a>
        </nav>
        <small>© {new Date().getFullYear()} Rajvir Singh Aujla</small>
      </footer>
      {cartNotice && <div className="cart-notice" role="status">{t('Added to your cart')} <button type="button" onClick={() => void openCart()}>{t('Open cart')}</button></div>}
    </main>
  )
}

function AdminRoute({
  accessToken,
  currentUser,
}: {
  accessToken: string | null
  currentUser: CurrentUser | null
}) {
  if (!accessToken || !currentUser) {
    return (
      <section className="admin-access" aria-labelledby="admin-access-heading">
        <p className="eyebrow">Protected workspace</p>
        <h1 id="admin-access-heading">Admin access</h1>
        <p>Sign in with an admin account to continue.</p>
      </section>
    )
  }

  if (currentUser.role !== 'admin') {
    return (
      <section className="admin-access" aria-labelledby="admin-access-heading">
        <p className="eyebrow">Protected workspace</p>
        <h1 id="admin-access-heading">Access denied</h1>
        <p role="alert">Your account does not have permission to use admin tools.</p>
        <a href="/">Return to the meal catalogue</a>
      </section>
    )
  }

  return <AdminPage accessToken={accessToken} />
}

interface MealCardProps {
  meal: Meal
  canAdd: boolean
  isAdding: boolean
  onAdd: () => void
  onOpen: () => void
}

function MealCard({ meal, canAdd, isAdding, onAdd, onOpen }: MealCardProps) {
  const { t, language } = useLanguage()
  return (
    <article className="meal-card">
      <MealArtwork meal={meal} />
      <div className="meal-card__body">
        <div className="meal-card__topline">
          <span>{meal.calories} kcal</span>
          <strong>{formatNok(meal.price_nok, language)}</strong>
        </div>
        <h3>{meal.name}</h3>
        <p className="meal-description">{meal.description}</p>
        <Nutrition meal={meal} />
        <div className="allergens" aria-label={t('Allergens')}>
          {meal.allergens.length > 0 ? (
            meal.allergens.map((allergen) => (
              <span key={allergen.code}>{allergen.name}</span>
            ))
          ) : (
            <span className="allergens__none">{t('No declared allergens')}</span>
          )}
        </div>
        <div className="meal-actions">
          <button className="detail-button" type="button" onClick={onOpen}>{t('View details')}</button>
          <button
            className="add-button"
            type="button"
            disabled={!canAdd || isAdding}
            onClick={onAdd}
          >
            {isAdding ? t('Adding…') : canAdd ? t('Add to cart') : t('Sign in to add')}
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
  const { t, language } = useLanguage()
  return (
    <section className="meal-detail" aria-labelledby="meal-detail-heading">
      <div className="meal-detail__header">
        <p className="eyebrow">{t('Meal details')}</p>
        <button className="close-button" type="button" onClick={onClose}>{t('Close')}</button>
      </div>

      {!detail && !error && (
        <div className="meal-detail__state" role="status">{t('Loading meal details…')}</div>
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
                {detail.available ? t('Available this week') : t('Currently unavailable')}
              </span>
              <strong>{formatNok(detail.price_nok, language)}</strong>
            </div>
            <h3 id="meal-detail-heading">{detail.name}</h3>
            <p className="meal-detail__description">{detail.description}</p>
            <Nutrition meal={detail} />
            <div className="meal-detail__facts">
              <div>
                <h4>{t('Ingredients')}</h4>
                <p>{detail.ingredients.join(', ')}</p>
              </div>
              <div>
                <h4>{t('Allergens')}</h4>
                <p>
                  {detail.allergens.length > 0
                    ? detail.allergens.map((allergen) => allergen.name).join(', ')
                    : t('No declared allergens')}
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
                ? t('Adding…')
                : !detail.available
                  ? t('Currently unavailable')
                  : canAdd
                    ? t('Add to cart')
                    : t('Sign in to add')}
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
  pickupOptions: PickupOptions | null
  selectedPickupDate: string
  selectedPickupSlot: string
  onDateChange: (date: string) => void
  onSlotChange: (slot: string) => void
  isCheckingOut: boolean
  onPickupChange: (locationId: string) => void
  onCheckout: () => Promise<void>
  onQuantityChange: (itemId: string, quantity: number) => Promise<void>
  onRemove: (itemId: string) => Promise<void>
}

function CartPanel({
  cart,
  error,
  mutationKey,
  pickupLocations,
  selectedPickupId,
  pickupOptions,
  selectedPickupDate,
  selectedPickupSlot,
  onDateChange,
  onSlotChange,
  isCheckingOut,
  onPickupChange,
  onCheckout,
  onQuantityChange,
  onRemove,
}: CartPanelProps) {
  const { t, language } = useLanguage()
  return (
    <section className="cart-panel" aria-labelledby="cart-heading">
      <div className="cart-panel__heading">
        <div>
          <p className="eyebrow">{t('Your order')}</p>
          <h2 id="cart-heading">{t('Shopping cart')}</h2>
        </div>
        {cart && (
          <span className="cart-count">
            {cart.total_quantity} {language === 'no' ? 'måltider' : cart.total_quantity === 1 ? 'meal' : 'meals'}
          </span>
        )}
      </div>

      {!cart && !error && (
        <div className="cart-state" role="status">{t('Loading your cart…')}</div>
      )}
      {error && (
        <div className="cart-state cart-state--error" role="alert">
          {error}
        </div>
      )}
      {cart && cart.items.length === 0 && (
        <div className="cart-state">{t('Your cart is empty. Add a meal below.')}</div>
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
                      {formatNok(item.meal.price_nok, language)} {t('each')}
                      {!item.meal.available && (
                        <span className="cart-item__unavailable">
                          {' '}· {t('unavailable')}
                        </span>
                      )}
                    </p>
                  </div>
                  <div className="quantity-control" aria-label={`${t('Quantity for')} ${item.meal.name}`}>
                    <button
                      type="button"
                      disabled={isMutating || item.quantity <= 1}
                      aria-label={`${t('Decrease')} ${item.meal.name}`}
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
                      aria-label={`${t('Increase')} ${item.meal.name}`}
                      onClick={() =>
                        void onQuantityChange(item.id, item.quantity + 1)
                      }
                    >
                      +
                    </button>
                  </div>
                  <strong>{formatNok(item.line_total_nok, language)}</strong>
                  <button
                    className="remove-button"
                    type="button"
                    disabled={isMutating}
                    onClick={() => void onRemove(item.id)}
                  >{t('Remove')}</button>
                </article>
              )
            })}
          </div>

          <aside className="cart-summary">
            <div className="cart-total">
              <span>{t('Total')}</span>
              <strong>{formatNok(cart.total_nok, language)}</strong>
            </div>
            <label className="pickup-field">
              <span id="pickup-location-label">{t('Pickup location')}</span>
              <select
                aria-labelledby="pickup-location-label"
                value={selectedPickupId}
                disabled={!pickupLocations || pickupLocations.length === 0}
                onChange={(event) => onPickupChange(event.target.value)}
              >
                <option value="">{t('Choose a pickup location')}</option>
                {pickupLocations?.map((location) => (
                  <option key={location.id} value={location.id}>
                    {location.name} — {location.address_line}, {location.postal_code}{' '}
                    {location.city}
                  </option>
                ))}
              </select>
            </label>
            <label className="pickup-field">
              <span id="pickup-date-label">{t('Pickup date')}</span>
              <select aria-labelledby="pickup-date-label" value={selectedPickupDate} disabled={!pickupOptions} onChange={(event) => onDateChange(event.target.value)}>
                <option value="">{t('Choose a pickup date')}</option>
                {pickupOptions?.days.map((day) => <option key={day.date} value={day.date}>
                  {new Intl.DateTimeFormat(language === 'no' ? 'nb-NO' : 'en-GB', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'Europe/Oslo' }).format(new Date(`${day.date}T12:00:00Z`))}
                </option>)}
              </select>
            </label>
            <label className="pickup-field">
              <span id="pickup-time-label">{t('Pickup time')}</span>
              <select aria-labelledby="pickup-time-label" value={selectedPickupSlot} disabled={!selectedPickupDate} onChange={(event) => onSlotChange(event.target.value)}>
                <option value="">{t('Choose a pickup time')}</option>
                {pickupOptions?.days.find((day) => day.date === selectedPickupDate)?.slots.map((slot) => <option key={slot.id} value={slot.id}>
                  {slot.id.replace('-', ':00–')}:00
                </option>)}
              </select>
            </label>
            <p className="checkout-note">{t('Pickup is available from tomorrow. All times are local to Oslo.')}</p>
            <button
              className="checkout-button"
              type="button"
              disabled={
                !selectedPickupId ||
                !selectedPickupDate ||
                !selectedPickupSlot ||
                isCheckingOut ||
                Boolean(mutationKey) ||
                cart.items.some((item) => !item.meal.available)
              }
              onClick={() => void onCheckout()}
            >
              {isCheckingOut ? t('Placing order…') : t('Review and place order')}
            </button>
            <p className="checkout-note">
              {t('You will be asked to confirm before the order is created. No payment is required for this demo.')}
            </p>
          </aside>
        </div>
      )}
    </section>
  )
}

interface OrdersPanelProps {
  orders: OrderSummary[] | null
  error: string | null
  selectedOrder: OrderDetail | null
  detailError: string | null
  onOpenOrder: (orderId: string) => Promise<void>
}

function OrdersPanel({
  orders,
  error,
  selectedOrder,
  detailError,
  onOpenOrder,
}: OrdersPanelProps) {
  const { t, language } = useLanguage()
  return (
    <section className="orders-panel" aria-labelledby="orders-heading">
      <div className="orders-panel__heading">
        <div>
          <p className="eyebrow">{language === 'no' ? 'Din konto' : 'Your account'}</p>
          <h2 id="orders-heading">{t('Order history')}</h2>
        </div>
      </div>

      {!orders && !error && (
        <div className="order-state" role="status">{t('Loading your orders…')}</div>
      )}
      {error && (
        <div className="order-state order-state--error" role="alert">
          {error}
        </div>
      )}
      {orders && orders.length === 0 && (
        <div className="order-state">{t('You have not placed any orders yet.')}</div>
      )}

      {orders && orders.length > 0 && (
        <div className="order-list">
          {orders.map((order) => (
            <article className="order-card" key={order.id}>
              <div>
                <span className={`order-status order-status--${order.status}`}>
                  {t(formatOrderStatus(order.status))}
                </span>
                <h3>{order.pickup_location_name}</h3>
                <p>{formatPickup(order.pickup_start_at, order.pickup_end_at, language)}</p>
              </div>
              <strong>{formatNok(order.total_nok, language)}</strong>
              <button type="button" onClick={() => void onOpenOrder(order.id)}>{t('View order')}</button>
            </article>
          ))}
        </div>
      )}

      {detailError && (
        <div className="order-state order-state--error" role="alert">
          {detailError}
        </div>
      )}
      {selectedOrder && (
        <article className="order-detail" aria-labelledby="order-detail-heading">
          <div className="order-detail__heading">
            <div>
              <p className="eyebrow">{t('Order details')}</p>
              <h3 id="order-detail-heading">
                {selectedOrder.pickup_location_name}
              </h3>
            </div>
            <span
              className={`order-status order-status--${selectedOrder.status}`}
            >
              {t(formatOrderStatus(selectedOrder.status))}
            </span>
          </div>
          <p className="order-detail__pickup">
            {selectedOrder.pickup_location_address}<br />
            {formatPickup(selectedOrder.pickup_start_at, selectedOrder.pickup_end_at, language)}
          </p>
          <div className="order-detail__items">
            {selectedOrder.items.map((item) => (
              <div key={item.meal_id}>
                <span>
                  {item.quantity} × {item.meal_name}
                </span>
                <strong>{formatNok(item.line_total_nok, language)}</strong>
              </div>
            ))}
          </div>
          <div className="order-detail__total">
            <span>{t('Total')}</span>
            <strong>{formatNok(selectedOrder.total_nok, language)}</strong>
          </div>
        </article>
      )}
    </section>
  )
}

function formatOrderStatus(status: OrderSummary['status']): string {
  return status
    .split('_')
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(' ')
}

function Nutrition({ meal }: { meal: Meal }) {
  const { t } = useLanguage()
  return (
    <dl className="nutrition" aria-label={`${t('Nutrition')} · ${meal.name}`}>
      <div>
        <dt>Protein</dt>
        <dd>{Number(meal.protein_grams)} g</dd>
      </div>
      <div>
        <dt>{t('Carbs')}</dt>
        <dd>{Number(meal.carbohydrate_grams)} g</dd>
      </div>
      <div>
        <dt>{t('Fat')}</dt>
        <dd>{Number(meal.fat_grams)} g</dd>
      </div>
    </dl>
  )
}
