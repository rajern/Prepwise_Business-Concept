import { useEffect, useState } from 'react'

import {
  type AdminOrderDetail,
  type AdminOrderSummary,
  AdminOrderRequestError,
  fetchAdminOrder,
  fetchAdminOrders,
  updateAdminOrderStatus,
} from '../api/adminOrders'
import type { OrderStatus } from '../api/orders'

interface OrdersPanelProps {
  accessToken: string
}

const nextStatus: Partial<Record<OrderStatus, OrderStatus>> = {
  received: 'preparing',
  preparing: 'ready_for_pickup',
  ready_for_pickup: 'completed',
}

const dateTimeFormatter = new Intl.DateTimeFormat('nb-NO', {
  dateStyle: 'medium',
  timeStyle: 'short',
  timeZone: 'Europe/Oslo',
})
const nokFormatter = new Intl.NumberFormat('nb-NO', {
  style: 'currency',
  currency: 'NOK',
})

export function OrdersPanel({ accessToken }: OrdersPanelProps) {
  const [orders, setOrders] = useState<AdminOrderSummary[] | null>(null)
  const [selectedOrder, setSelectedOrder] = useState<AdminOrderDetail | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [updating, setUpdating] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    void fetchAdminOrders(accessToken, controller.signal)
      .then(setOrders)
      .catch((reason: unknown) => {
        if (!(reason instanceof DOMException && reason.name === 'AbortError')) {
          setLoadError('Orders could not be loaded.')
        }
      })
    return () => controller.abort()
  }, [accessToken])

  async function inspectOrder(orderId: string) {
    setDetailError(null)
    setSelectedOrder(null)
    try {
      setSelectedOrder(await fetchAdminOrder(accessToken, orderId))
    } catch {
      setDetailError('The order details could not be loaded.')
    }
  }

  async function advanceStatus() {
    if (!selectedOrder) {
      return
    }
    const status = nextStatus[selectedOrder.status]
    if (!status) {
      return
    }
    setUpdating(true)
    setDetailError(null)
    try {
      const saved = await updateAdminOrderStatus(accessToken, selectedOrder.id, status)
      setSelectedOrder(saved)
      setOrders((current) =>
        current?.map((order) =>
          order.id === saved.id ? { ...order, status: saved.status } : order,
        ) ?? null,
      )
    } catch (reason: unknown) {
      setDetailError(
        reason instanceof AdminOrderRequestError
          ? reason.detail ?? 'The order status could not be updated.'
          : 'The order status could not be updated.',
      )
    } finally {
      setUpdating(false)
    }
  }

  return (
    <section className="admin-section" aria-labelledby="orders-admin-heading">
      <div className="admin-heading">
        <div>
          <p className="eyebrow">Fulfilment workflow</p>
          <h2 id="orders-admin-heading">Orders</h2>
          <p>Inspect incoming orders and move them through the fulfilment lifecycle.</p>
        </div>
      </div>

      {loadError && (
        <div className="admin-state admin-state--error" role="alert">
          {loadError}
        </div>
      )}
      {!orders && !loadError && (
        <div className="admin-state" role="status">
          Loading orders…
        </div>
      )}
      {orders && orders.length === 0 && (
        <div className="admin-state">No orders have been placed yet.</div>
      )}

      {orders && orders.length > 0 && (
        <div className="admin-layout">
          <div className="admin-record-list" aria-label="Orders">
            {orders.map((order) => (
              <article
                className={`admin-record-card ${
                  selectedOrder?.id === order.id ? 'admin-record-card--selected' : ''
                }`}
                key={order.id}
              >
                <div>
                  <span className={`order-status order-status--${order.status}`}>
                    {formatStatus(order.status)}
                  </span>
                  <h3>{order.customer_display_name ?? order.customer_email ?? 'Customer'}</h3>
                  <p>
                    {dateTimeFormatter.format(new Date(order.created_at))} ·{' '}
                    {nokFormatter.format(Number(order.total_nok))}
                  </p>
                </div>
                <button type="button" onClick={() => void inspectOrder(order.id)}>
                  Inspect
                </button>
              </article>
            ))}
          </div>

          <div className="admin-order-detail">
            {!selectedOrder && !detailError && (
              <div className="admin-state">Select an order to inspect it.</div>
            )}
            {detailError && (
              <div className="admin-state admin-state--error" role="alert">
                {detailError}
              </div>
            )}
            {selectedOrder && (
              <article aria-labelledby="admin-order-detail-heading">
                <div className="admin-order-detail__heading">
                  <div>
                    <p className="eyebrow">Order details</p>
                    <h2 id="admin-order-detail-heading">
                      {selectedOrder.customer_display_name ??
                        selectedOrder.customer_email ??
                        'Customer'}
                    </h2>
                    {selectedOrder.customer_email && <p>{selectedOrder.customer_email}</p>}
                  </div>
                  <span
                    className={`order-status order-status--${selectedOrder.status}`}
                  >
                    {formatStatus(selectedOrder.status)}
                  </span>
                </div>
                <p>
                  <strong>{selectedOrder.pickup_location_name}</strong>
                  <br />
                  {selectedOrder.pickup_location_address}
                  <br />
                  Pickup {dateTimeFormatter.format(new Date(selectedOrder.pickup_start_at))}
                </p>
                <div className="admin-order-items">
                  {selectedOrder.items.map((item) => (
                    <div key={item.meal_id}>
                      <span>
                        {item.quantity} × {item.meal_name}
                      </span>
                      <strong>{nokFormatter.format(Number(item.line_total_nok))}</strong>
                    </div>
                  ))}
                </div>
                <div className="admin-order-total">
                  <span>Total</span>
                  <strong>{nokFormatter.format(Number(selectedOrder.total_nok))}</strong>
                </div>
                {nextStatus[selectedOrder.status] ? (
                  <button
                    className="admin-save"
                    type="button"
                    disabled={updating}
                    onClick={() => void advanceStatus()}
                  >
                    {updating
                      ? 'Updating…'
                      : `Move to ${formatStatus(nextStatus[selectedOrder.status]!)}`}
                  </button>
                ) : (
                  <div className="admin-state admin-state--success">
                    Fulfilment completed.
                  </div>
                )}
              </article>
            )}
          </div>
        </div>
      )}
    </section>
  )
}

function formatStatus(status: OrderStatus): string {
  return status
    .split('_')
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(' ')
}
