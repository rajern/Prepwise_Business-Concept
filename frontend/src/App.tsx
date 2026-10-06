import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  addCartItem,
  createCartGroup,
  deleteCartGroup,
  saveCartGroup,
  type CartItem,
  type GroupSelection,
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
  reviewOrder,
  cancelOrder,
  fetchOrder,
  fetchOrders,
  type OrderDetail,
  type OrderSummary,
  type OrderPurchase,
  type OrderReview,
} from './api/orders'
import type { CurrentUser } from './api/me'
import { AdminPage } from './admin/AdminPage'
import { AssistantPanel } from './assistant/AssistantPanel'
import { AuthControls } from './auth/AuthControls'
import { fetchPickupOptions, type PickupOptions } from './api/pickupOptions'
import { LanguageProvider, useLanguage, formatNok, formatPickup } from './i18n'
import { CartDrawer } from './components/CartDrawer'
import { MealArtwork } from './components/MealArtwork'
import { GroupedCart, type CheckoutSelection } from './components/GroupedCart'
import { canCancelOrder, isUpcomingOrder, osloDate } from './orderState'

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
  const isHistoryRoute = window.location.pathname === '/orders'
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
  const cartVersion = useRef(0)
  const cartReadSequence = useRef(0)
  const orderReadSequence = useRef(0)
  const pickupReadSequence = useRef(0)
  const detailVersion = useRef(0)
  const readController = useRef<AbortController | null>(null)
  const pendingCheckout = useRef<{ token: string; language: typeof language; purchase: OrderPurchase; review: OrderReview } | null>(null)
  const [checkoutUncertain, setCheckoutUncertain] = useState(false)
  const cartWriteBusy = useRef(false)
  const [pickupLocations, setPickupLocations] = useState<PickupLocation[] | null>(
    null,
  )
  const [pickupOptions, setPickupOptions] = useState<PickupOptions | null>(null)
  const [targetGroupId, setTargetGroupId] = useState('')
  const [cartOpen, setCartOpen] = useState(false)
  const [cartNotice, setCartNotice] = useState(false)
  const sessionRef = useRef({ token: accessToken, language })
  useEffect(() => { sessionRef.current = { token: accessToken, language } }, [accessToken, language])
  const [orders, setOrders] = useState<OrderSummary[] | null>(null)
  const ordersVersion = useRef(0)
  const [ordersError, setOrdersError] = useState<string | null>(null)
  const [selectedOrder, setSelectedOrder] = useState<OrderDetail | null>(null)
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null)
  const [upcomingOpen, setUpcomingOpen] = useState(false)
  const [isCancelling, setIsCancelling] = useState(false)
  const [orderDetailError, setOrderDetailError] = useState<string | null>(null)
  const [isCheckingOut, setIsCheckingOut] = useState(false)
  const [now, setNow] = useState(Date.now)
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(
    initialCurrentUser,
  )

  const handleAccessTokenChange = useCallback((nextAccessToken: string | null) => {
    if (!nextAccessToken && sessionRef.current.token) { try { sessionStorage.removeItem('prepwise-checkout') } catch { /* Optional storage. */ } }
    cartVersion.current += 1
    ordersVersion.current += 1
    detailVersion.current += 1
    readController.current?.abort()
    pendingCheckout.current = null
    setCheckoutUncertain(false)
    cartWriteBusy.current = false
    sessionRef.current = { ...sessionRef.current, token: nextAccessToken }
    setAccessToken(nextAccessToken)
    setCart(null)
    setCartError(null)
    setPickupLocations(null)
    setTargetGroupId('')
    setOrders(null)
    setOrdersError(null)
    setSelectedOrder(null)
    setSelectedOrderId(null)
    setOrderDetailError(null)
    setCartMutationKey(null)
    setIsCheckingOut(false)
    setIsCancelling(false)
    if (!nextAccessToken) {
      setCartOpen(false)
      setCartNotice(false)
      setCurrentUser(null)
    }
  }, [])

  useEffect(() => {
    if (!accessToken || !currentUser?.id || pendingCheckout.current) return
    try {
      const saved = JSON.parse(sessionStorage.getItem('prepwise-checkout') ?? 'null')
      if (saved?.userId !== currentUser.id) { sessionStorage.removeItem('prepwise-checkout'); return }
      if (saved.purchase && typeof saved.purchase.idempotency_key === 'string' && typeof saved.purchase.review_fingerprint === 'string' && saved.review && (saved.language === 'no' || saved.language === 'en')) {
        pendingCheckout.current = { token: accessToken, language: saved.language, purchase: saved.purchase, review: saved.review }
        queueMicrotask(() => { if (sessionRef.current.token === accessToken) setCheckoutUncertain(true) })
      }
    } catch { /* Optional storage. */ }
  }, [accessToken, currentUser?.id])

  const refreshCustomerState = useCallback(async () => {
    if (!accessToken || isAdminRoute) return
    const expected = { token: accessToken, language }
    const cartSequence = ++cartReadSequence.current
    const orderSequence = ++orderReadSequence.current
    const expectedCartVersion = cartVersion.current
    const expectedOrdersVersion = ordersVersion.current
    readController.current?.abort()
    const controller = new AbortController()
    readController.current = controller
    let timedOut = false
    const timer = window.setTimeout(() => { timedOut = true; controller.abort() }, 15000)
    try {
      const results = await Promise.allSettled([
        fetchCart(accessToken, controller.signal, language), fetchOrders(accessToken, controller.signal, language),
      ])
      if (sessionRef.current.token !== expected.token || sessionRef.current.language !== expected.language) return
      if (cartSequence === cartReadSequence.current && cartVersion.current === expectedCartVersion) {
        if (results[0].status === 'fulfilled') { setCart(results[0].value); setCartError(null) }
        else if (!controller.signal.aborted || timedOut) setCartError(customerError(results[0].reason, 'We could not load your cart. Please try again.'))
      }
      if (orderSequence === orderReadSequence.current && ordersVersion.current === expectedOrdersVersion) {
        if (results[1].status === 'fulfilled') { setOrders(results[1].value); setOrdersError(null) }
        else if (!controller.signal.aborted || timedOut) setOrdersError(customerError(results[1].reason, 'We could not load your order history. Please try again.'))
      }
    } finally { window.clearTimeout(timer) }
  }, [accessToken, language, isAdminRoute, customerError])
  const latestRefresh = useRef(refreshCustomerState)
  useEffect(() => { latestRefresh.current = refreshCustomerState }, [refreshCustomerState])

  const refreshPickupOptions = useCallback(async () => {
    const sequence = ++pickupReadSequence.current
    const expected = { token: accessToken, language }
    try {
      const options = await fetchPickupOptions()
      if (sequence === pickupReadSequence.current && sessionRef.current.token === expected.token && sessionRef.current.language === expected.language) setPickupOptions(options)
    } catch {
      queueMicrotask(() => { if (sequence === pickupReadSequence.current && sessionRef.current.token === expected.token && sessionRef.current.language === expected.language) setCartError(t('We could not load the pickup times. Please try again.')) })
    }
  }, [accessToken, language, t])

  useEffect(() => {
    let day = osloDate(Date.now())
    const tick = () => {
      const value = Date.now()
      setNow(value)
      const nextDay = osloDate(value)
      if (nextDay !== day) { day = nextDay; void refreshCustomerState(); void refreshPickupOptions() }
    }
    const focus = () => { tick(); void refreshCustomerState(); void refreshPickupOptions() }
    const visibility = () => { if (document.visibilityState === 'visible') focus() }
    const timer = window.setInterval(tick, 30000)
    window.addEventListener('focus', focus)
    document.addEventListener('visibilitychange', visibility)
    return () => { window.clearInterval(timer); window.removeEventListener('focus', focus); document.removeEventListener('visibilitychange', visibility) }
  }, [refreshCustomerState, refreshPickupOptions])

  useEffect(() => {
    if (isAdminRoute) {
      return
    }
    const controller = new AbortController()

    void fetchMeals(controller.signal, language)
      .then((value) => { if (!controller.signal.aborted) setMeals(value) })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return
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
      .then((value) => { if (!controller.signal.aborted) setMealDetail(value) })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return
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

    void refreshCustomerState()

    void fetchPickupLocations(controller.signal)
      .then((value) => { if (!controller.signal.aborted) setPickupLocations(value) })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted && !(reason instanceof DOMException && reason.name === 'AbortError')) {
          setCartError(
            customerError(
              reason,
              t('We could not load the pickup locations. Please try again.'),
            ),
          )
        }
      })

    queueMicrotask(() => { if (!controller.signal.aborted) void refreshPickupOptions() })

    return () => { controller.abort(); readController.current?.abort() }
  }, [accessToken, isAdminRoute, language, customerError, t, refreshCustomerState, refreshPickupOptions])

  useEffect(() => {
    if (!accessToken || !selectedOrderId) return
    const controller = new AbortController()
    const version = detailVersion.current
    void fetchOrder(accessToken, selectedOrderId, controller.signal, language)
      .then((value) => { if (!controller.signal.aborted && detailVersion.current === version) { setSelectedOrder(value); setOrderDetailError(null) } })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted && detailVersion.current === version && !(reason instanceof DOMException && reason.name === 'AbortError')) {
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

  async function openCart() {
    setCartOpen(true)
    if (!accessToken) return
    setCartError(null)
    await Promise.all([
      refreshCustomerState(),
      refreshPickupOptions(),
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
    if (selectedMealId === mealId) { closeMealDetails(); return }
    setMealDetail(null)
    setDetailError(null)
    setSelectedMealId(mealId)
  }

  async function addMeal(mealId: string) {
    if (!accessToken) {
      return
    }
    const groupId = cart?.groups?.some((group) => group.id === targetGroupId) ? targetGroupId : null
    await runCartMutation(`meal-${mealId}`, () => addCartItem(accessToken, mealId, language, groupId), true)
  }

  async function changeQuantity(itemId: string, quantity: number) {
    if (!accessToken) {
      return
    }
    const original = cart?.items.find((item) => item.id === itemId)
    if (!original) return
    await runCartMutation(itemId, () =>
      updateCartItem(accessToken, itemId, quantity, language, undefined, original.quantity, original.group_id ?? null),
    )
  }

  async function removeItem(itemId: string) {
    if (!accessToken) {
      return
    }
    await runCartMutation(itemId, async () => {
      await removeCartItem(accessToken, itemId)
      return fetchCart(accessToken, undefined, language)
    })
  }

  async function runCartMutation(
    key: string,
    mutation: () => Promise<Cart>,
    announce = false,
  ) {
    if (cartWriteBusy.current) return
    cartWriteBusy.current = true
    cartVersion.current += 1
    const expected = { token: accessToken, language }
    const isCurrent = () => sessionRef.current.token === expected.token && sessionRef.current.language === expected.language
    setCartMutationKey(key)
    setCartError(null)
    try {
      const next = await mutation()
      if (!isCurrent()) return
      cartVersion.current += 1
      setCart(next)
      if (announce) setCartNotice(true)
    } catch (reason: unknown) {
      if (!isCurrent()) return
      const message =
        reason instanceof ApiRequestError && reason.status === 409
          ? t('Your cart changed. Review the refreshed cart before trying again.')
          : customerError(
              reason,
              t('We could not update your cart. Please try again.'),
            )
      await refreshCustomerState()
      if (isCurrent()) setCartError(message)
    } finally {
      if (sessionRef.current.token === expected.token) {
        cartVersion.current += 1
        cartWriteBusy.current = false; setCartMutationKey(null)
        if (sessionRef.current.language !== expected.language) void latestRefresh.current()
      }
    }
  }

  async function addPickupGroup() {
    if (!accessToken) return
    const known = new Set(cart?.groups?.map((group) => group.id))
    await runCartMutation('group-create', async () => {
      const next = await createCartGroup(accessToken, language)
      const added = next.groups?.find((group) => !known.has(group.id))
      if (sessionRef.current.token === accessToken && added) setTargetGroupId(added.id)
      return next
    })
  }

  async function savePickupGroup(id: string, fields: GroupSelection) {
    if (!accessToken) return
    const group = cart?.groups?.find((candidate) => candidate.id === id)
    if (!group) return
    await runCartMutation(`group-${id}`, () => saveCartGroup(accessToken, id, { ...fields, expected_version: group.version }, language))
  }

  async function removePickupGroup(id: string) {
    if (!accessToken) return
    await runCartMutation(`group-${id}`, async () => {
      await deleteCartGroup(accessToken, id)
      if (sessionRef.current.token === accessToken && targetGroupId === id) setTargetGroupId('')
      return fetchCart(accessToken, undefined, language)
    })
  }

  async function moveItem(item: CartItem, groupId: string | null) {
    if (!accessToken) return
    await runCartMutation(item.id, () => updateCartItem(accessToken, item.id, item.quantity, language, groupId, item.quantity, item.group_id ?? null))
  }

  async function checkout(selection: CheckoutSelection) {
    if (!accessToken || cartWriteBusy.current) return
    const { location: locationId, date, slot } = selection
    const expected = { token: accessToken, language }
    const isCurrent = () => sessionRef.current.token === expected.token && sessionRef.current.language === expected.language
    setIsCheckingOut(true)
    ordersVersion.current += 1
    cartWriteBusy.current = true
    cartVersion.current += 1
    setCartError(null)
    let committed = false
    let submitted = false
    try {
      let attempt = pendingCheckout.current
      if (attempt && attempt.token !== accessToken) return
      if (attempt && (attempt.purchase.pickup_location_id !== locationId || attempt.purchase.pickup_date !== date || attempt.purchase.pickup_slot !== slot || attempt.purchase.group_id !== selection.groupId)) {
        setCartError(t('Resolve the previous checkout before placing a different order.'))
        return
      }
      if (!attempt) {
        const orderSelection = { pickup_location_id: locationId, pickup_date: date, pickup_slot: slot, group_id: selection.groupId }
        const review = await reviewOrder(accessToken, orderSelection, language)
        if (!isCurrent()) return
        const prompt = `${review.items.map((item) => `${item.quantity} × ${item.meal_name}: ${formatNok(item.line_total_nok, language)}`).join('\n')}\n\n${t('Total')}: ${formatNok(review.total_nok, language)}\n${review.pickup_location_name}\n${review.pickup_location_address}\n${formatPickup(review.pickup_start_at, review.pickup_end_at, language)}\n\n${t('Confirm this order?')}`
        if (!window.confirm(prompt) || !isCurrent()) return
        attempt = { token: accessToken, language, review, purchase: { ...orderSelection, review_fingerprint: review.review_fingerprint, idempotency_key: crypto.randomUUID() } }
        pendingCheckout.current = attempt
        try { sessionStorage.setItem('prepwise-checkout', JSON.stringify({ userId: currentUser?.id, language, purchase: attempt.purchase, review })) } catch { /* Optional storage. */ }
      } else if (!window.confirm(t('Retry the previous checkout with the same request reference? No new order will be added if it already succeeded.')) || !isCurrent()) return
      submitted = true
      const order = await createOrder(accessToken, attempt.purchase, attempt.language)
      committed = true
      if (sessionRef.current.token !== expected.token) return
      pendingCheckout.current = null
      setCheckoutUncertain(false)
      try { sessionStorage.removeItem('prepwise-checkout') } catch { /* Optional storage. */ }
      if (!isCurrent()) return
      cartVersion.current += 1
      ordersVersion.current += 1
      detailVersion.current += 1
      setCartOpen(false)
      setSelectedOrderId(order.id)
      setSelectedOrder(order)
      setUpcomingOpen(true)
      setOrders((previous) => [order, ...(previous ?? []).filter((item) => item.id !== order.id)])
      setOrderDetailError(null)
      // Refresh errors must not imply a committed order failed or invite duplicate checkout.
      await refreshCustomerState()
    } catch (reason: unknown) {
      if (!isCurrent()) return
      if (reason instanceof ApiRequestError && reason.code === 'checkout_not_created') {
        pendingCheckout.current = null
        setCheckoutUncertain(false)
        try { sessionStorage.removeItem('prepwise-checkout') } catch { /* Optional storage. */ }
      } else if (submitted && !committed) setCheckoutUncertain(true)
      const message = committed
        ? t('Your order was placed, but order history could not be refreshed.')
        : reason instanceof ApiRequestError && reason.status === 409
          ? t('Check your cart and choose a valid pickup time.')
          : customerError(reason, 'We could not confirm checkout. Check your cart and upcoming orders before trying again.')
      if (!committed) await refreshCustomerState()
      if (isCurrent()) setCartError(message)
    } finally {
      if (sessionRef.current.token === expected.token) {
        cartVersion.current += 1; ordersVersion.current += 1
        cartWriteBusy.current = false; setIsCheckingOut(false)
        if (pendingCheckout.current && submitted && !committed) setCheckoutUncertain(true)
        if (sessionRef.current.language !== expected.language) void latestRefresh.current()
      }
    }
  }

  async function openOrder(orderId: string) {
    setSelectedOrder(null)
    setOrderDetailError(null)
    setSelectedOrderId((previous) => previous === orderId ? null : orderId)
  }

  async function cancelSelectedOrder() {
    if (!accessToken || !selectedOrder || !canCancelOrder(selectedOrder, Date.now()) || isCancelling) return
    const orderId = selectedOrder.id
    if (!window.confirm(t('Cancel this order? This cannot be undone.'))) return
    const expected = { token: accessToken, language }
    setIsCancelling(true)
    ordersVersion.current += 1
    detailVersion.current += 1
    setOrderDetailError(null)
    try {
      const cancelled = await cancelOrder(accessToken, orderId, language)
      if (sessionRef.current.token !== expected.token) return
      setSelectedOrderId(null)
      setSelectedOrder(null)
      if (sessionRef.current.language !== expected.language) return
      setOrders((previous) => previous?.map((order) => order.id === orderId ? cancelled : order) ?? [cancelled])
    } catch (reason: unknown) {
      await refreshCustomerState()
      if (sessionRef.current.token === expected.token && sessionRef.current.language === expected.language) {
        setSelectedOrderId(null); setSelectedOrder(null)
        setOrdersError(customerError(reason, 'This order could not be cancelled. Refresh the orders and check the cancellation deadline.'))
      }
    } finally {
      if (sessionRef.current.token === expected.token) {
        ordersVersion.current += 1
        detailVersion.current += 1
        setIsCancelling(false)
        if (sessionRef.current.language !== expected.language) void latestRefresh.current()
      }
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
            {!isAdminRoute && accessToken && <a href="/orders" aria-current={isHistoryRoute ? 'page' : undefined}>{t('Order history')}</a>}
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
        <p className="eyebrow">{t(isHistoryRoute ? 'Your account' : 'Pickup meals in Oslo')}</p>
        <h1>{t(isHistoryRoute ? 'Your previous orders' : 'Ready meals, without the guesswork.')}</h1>
        <p className="summary">{t(isHistoryRoute ? 'Completed, cancelled and past pickup windows. Upcoming orders are shown above the meal menu.' : 'Pick balanced meals with clear nutrition and collect them from a convenient location in Oslo.')}</p>
      </section>

      <AssistantPanel key={currentUser?.id ?? (accessToken ? 'signed-in' : 'signed-out')} accessToken={accessToken} userId={currentUser?.id ?? null} onStateChange={refreshCustomerState} />

      <CartDrawer open={cartOpen} onClose={() => setCartOpen(false)}>
      {checkoutUncertain && pendingCheckout.current && <div role="alert"><p>{t('The previous checkout outcome is unknown. Check your orders or retry the same checkout safely.')}</p><button type="button" disabled={isCheckingOut || Boolean(cartMutationKey)} onClick={() => {
        const purchase = pendingCheckout.current?.purchase
        if (purchase) void checkout({ groupId: purchase.group_id, location: purchase.pickup_location_id, date: purchase.pickup_date, slot: purchase.pickup_slot })
      }}>{t('Check previous checkout')}</button></div>}
      {accessToken ? (
        <GroupedCart
          key={currentUser?.id ?? accessToken}
          cart={cart}
          error={cartError}
          busy={Boolean(cartMutationKey) || isCheckingOut}
          pickupLocations={pickupLocations}
          pickupOptions={pickupOptions}
          onCreateGroup={addPickupGroup}
          onDeleteGroup={removePickupGroup}
          onSaveGroup={savePickupGroup}
          onMove={moveItem}
          onCheckout={checkout}
          onQuantityChange={changeQuantity}
          onRemove={removeItem}
        />
      ) : <div className="cart-panel"><h2 id="cart-heading">{t('Shopping cart')}</h2><p>{t('Sign in to use your cart.')}</p></div>}
      </CartDrawer>

      {isHistoryRoute && !accessToken && <p>{t('Sign in to view your orders.')}</p>}
      {accessToken && isHistoryRoute && (
        <OrdersPanel
          orders={orders?.filter((order) => !isUpcomingOrder(order, now)) ?? null}
          now={now}
          error={ordersError}
          selectedOrder={selectedOrder}
          selectedOrderId={selectedOrderId}
          detailError={orderDetailError}
          onOpenOrder={openOrder}
          onClose={() => { setSelectedOrderId(null); setSelectedOrder(null); setOrderDetailError(null) }}
          onCancel={cancelSelectedOrder}
          cancelling={isCancelling}
        />
      )}
      {accessToken && !isHistoryRoute && <section className="upcoming-orders">
        <button className="upcoming-toggle" type="button" aria-expanded={upcomingOpen} aria-controls="upcoming-orders-content" onClick={() => { if (!upcomingOpen) void refreshCustomerState(); setUpcomingOpen((open) => !open) }}>{t('Upcoming orders')} ({orders?.filter((order) => isUpcomingOrder(order, now)).length ?? 0}) <span aria-hidden="true">{upcomingOpen ? '−' : '+'}</span></button>
        {upcomingOpen && <div id="upcoming-orders-content"><OrdersPanel now={now} title="Upcoming orders" orders={orders?.filter((order) => isUpcomingOrder(order, now)) ?? null} error={ordersError} selectedOrder={selectedOrder} selectedOrderId={selectedOrderId} detailError={orderDetailError} onOpenOrder={openOrder} onClose={() => { setSelectedOrderId(null); setSelectedOrder(null); setOrderDetailError(null) }} onCancel={cancelSelectedOrder} cancelling={isCancelling} /></div>}
      </section>}
      {!isHistoryRoute && <>
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
            {accessToken && (cart?.groups?.length ?? 0) > 0 && <label className="filter-field"><span>{t('Add meals to')}</span><select aria-label={t('Add meals to')} value={targetGroupId} onChange={(event) => setTargetGroupId(event.target.value)}><option value="">{t('Unassigned meals')}</option>{cart?.groups?.map((group, index) => <option key={group.id} value={group.id}>{t('Pickup group')} {index + 1}{group.pickup_date ? ` · ${group.pickup_date}` : ''}</option>)}</select></label>}
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
                isAdding={Boolean(cartMutationKey) || isCheckingOut}
                onAdd={() => void addMeal(meal.id)}
                onOpen={() => openMealDetails(meal.id)}
              />
            ))}
          </div>
        )}
      </section>
      </>}
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
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const element = dialog.current
    if (!element) return
    const previousFocus = document.activeElement as HTMLElement | null
    element.showModal()
    return () => { element.close(); previousFocus?.focus() }
  }, [])
  return (
    <dialog ref={dialog} className="meal-detail meal-detail-dialog" aria-labelledby="meal-detail-heading" onCancel={(event) => { event.preventDefault(); onClose() }} onClick={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <div className="meal-detail__header">
        <h2 className="eyebrow" id="meal-detail-heading">{t('Meal details')}</h2>
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
            <h3>{detail.name}</h3>
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
    </dialog>
  )
}


interface OrdersPanelProps {
  now: number
  title?: string
  orders: OrderSummary[] | null
  error: string | null
  selectedOrder: OrderDetail | null
  selectedOrderId: string | null
  detailError: string | null
  onOpenOrder: (orderId: string) => Promise<void>
  onClose: () => void
  onCancel: () => Promise<void>
  cancelling: boolean
}

function OrdersPanel({
  now,
  title = 'Order history',
  orders,
  error,
  selectedOrder,
  selectedOrderId,
  detailError,
  onOpenOrder,
  onClose,
  onCancel,
  cancelling,
}: OrdersPanelProps) {
  const { t, language } = useLanguage()
  return (
    <section className="orders-panel" aria-labelledby="orders-heading">
      <div className="orders-panel__heading">
        <div>
          <p className="eyebrow">{language === 'no' ? 'Din konto' : 'Your account'}</p>
          <h2 id="orders-heading">{t(title)}</h2>
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
            <article className="order-card" key={order.id} data-order-id={order.id}>
              <div>
                <span className={`order-status order-status--${order.status}`}>
                  {t(formatOrderStatus(order.status))}
                </span>
                <h3>{order.pickup_location_name}</h3>
                <p>{formatPickup(order.pickup_start_at, order.pickup_end_at, language)}</p>
                {!isUpcomingOrder(order, now) && order.status !== 'completed' && order.status !== 'cancelled' && <p>{t('Pickup time has passed — collection is not confirmed.')}</p>}
              </div>
              <strong>{formatNok(order.total_nok, language)}</strong>
              <button type="button" aria-expanded={selectedOrderId === order.id} disabled={cancelling} onClick={() => void onOpenOrder(order.id)}>{selectedOrderId === order.id ? t('Close order') : t('View order')}</button>
            </article>
          ))}
        </div>
      )}

      {detailError && (
        <div className="order-state order-state--error" role="alert">
          {detailError}
        </div>
      )}
      {selectedOrderId && orders?.some((order) => order.id === selectedOrderId) && !selectedOrder && !detailError && <p role="status">{t('Loading order details…')}</p>}
      {selectedOrder && orders?.some((order) => order.id === selectedOrder.id) && (
        <article className="order-detail" aria-labelledby="order-detail-heading">
          <div className="order-detail__heading">
            <button className="close-button" type="button" onClick={onClose}>{t('Close order')}</button>
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
          {selectedOrder.status !== 'completed' && selectedOrder.status !== 'cancelled' && <>
            <p className="checkout-note">{t('To change pickup after ordering, cancel and place a new order. Cancellation is only possible before the pickup day (Oslo time).')}</p>
            {canCancelOrder(selectedOrder, now) && <button type="button" className="cancel-order" disabled={cancelling} onClick={() => void onCancel()}>{cancelling ? t('Cancelling…') : t('Cancel order')}</button>}
          </>}
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
