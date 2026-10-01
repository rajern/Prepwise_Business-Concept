import { useState } from 'react'
import type { Cart, CartGroup, CartItem, GroupSelection } from '../api/cart'
import type { PickupLocation } from '../api/pickupLocations'
import type { PickupOptions } from '../api/pickupOptions'
import { formatNok, useLanguage } from '../i18n'

export interface CheckoutSelection { groupId: string | null; location: string; date: string; slot: string }
interface Props {
  cart: Cart | null; error: string | null; busy: boolean
  pickupLocations: PickupLocation[] | null; pickupOptions: PickupOptions | null
  onCreateGroup: () => Promise<void>
  onDeleteGroup: (id: string) => Promise<void>
  onSaveGroup: (id: string, fields: GroupSelection) => Promise<void>
  onMove: (item: CartItem, groupId: string | null) => Promise<void>
  onQuantityChange: (id: string, quantity: number) => Promise<void>
  onRemove: (id: string) => Promise<void>
  onCheckout: (selection: CheckoutSelection) => Promise<void>
}

export function GroupedCart(props: Props) {
  const { t, language } = useLanguage()
  const { cart } = props
  const unassigned = cart?.items.filter((item) => !item.group_id) ?? []
  const groups = cart?.groups ?? []
  return <section className="cart-panel" aria-labelledby="cart-heading">
    <div className="cart-panel__heading"><h2 id="cart-heading">{t('Shopping cart')}</h2><span className="cart-count">{cart?.total_quantity ?? 0} {language === 'en' && cart?.total_quantity === 1 ? 'meal' : t('meals')}</span></div>
    {!cart && !props.error && <p role="status">{t('Loading your cart…')}</p>}
    {props.error && <p role="alert">{props.error}</p>}
    {cart && cart.items.length === 0 && <p>{t('Your cart is empty. Add a meal below.')}</p>}
    <p className="checkout-note">{t('Each pickup group becomes a separate order. You can choose different days and locations.')}</p>
    <button className="close-button" type="button" disabled={props.busy || !cart} onClick={() => void props.onCreateGroup()}>{t('Add pickup group')}</button>
    {unassigned.length > 0 && cart && <PickupGroup key="unassigned" {...props} group={null} items={unassigned} index={0} groups={groups} />}
    {groups.map((group, index) => <PickupGroup key={group.id} {...props} group={group} items={group.items} index={index + 1} groups={groups} />)}
  </section>
}

function PickupGroup({ group, items, index, groups, ...props }: Props & {group: CartGroup | null; items: CartItem[]; index: number; groups: CartGroup[]}) {
  const { t, language } = useLanguage()
  // A date without a slot is a local draft, not a valid persisted pickup window.
  const [draft, setDraft] = useState<{date: string; slot: string} | null>(null)
  const date = draft?.date ?? group?.pickup_date ?? ''
  const slot = draft?.slot ?? group?.pickup_slot ?? ''
  const [legacyLocation, setLegacyLocation] = useState('')
  const location = group?.pickup_location_id ?? legacyLocation
  const validLocation = Boolean(props.pickupLocations?.some((candidate) => candidate.id === location))
  const total = items.reduce((sum, item) => sum + Number(item.line_total_nok), 0)
  const day = props.pickupOptions?.days.find((candidate) => candidate.date === date)
  const validSlot = Boolean(day?.slots.some((candidate) => candidate.id === slot))
  async function changeSlot(value: string) {
    setDraft({ date, slot: value })
    if (group) {
      await props.onSaveGroup(group.id, { pickup_date: value ? date : null, pickup_slot: value || null })
      // Retain draft on failure. The checkout save revalidates it authoritatively.
    }
  }
  return <section className="pickup-group" aria-labelledby={`group-${group?.id ?? 'unassigned'}`}>
    <h3 id={`group-${group?.id ?? 'unassigned'}`}>{group ? `${t('Pickup group')} ${index}` : t('Unassigned meals')}</h3>
    {items.length === 0 && <><p>{t('Add meals to this group from the menu or move them from another group.')}</p>{group && <button className="remove-button" type="button" disabled={props.busy} onClick={() => void props.onDeleteGroup(group.id)}>{t('Remove empty group')}</button>}</>}
    <div className="cart-items">{items.map((item) => <article className="cart-item" key={item.id}>
      <div><h4>{item.meal.name}</h4><p>{formatNok(item.meal.price_nok, language)} {t('each')}{!item.meal.available && ` · ${t('unavailable')}`}</p></div>
      <div className="quantity-control" aria-label={`${t('Quantity for')} ${item.meal.name}`}>
        <button type="button" aria-label={`${t('Decrease')} ${item.meal.name}`} disabled={props.busy || item.quantity <= 1} onClick={() => void props.onQuantityChange(item.id, item.quantity - 1)}>−</button>
        <span>{item.quantity}</span>
        <button type="button" aria-label={`${t('Increase')} ${item.meal.name}`} disabled={props.busy || !item.meal.available || item.quantity >= 99} onClick={() => void props.onQuantityChange(item.id, item.quantity + 1)}>+</button>
      </div>
      <strong>{formatNok(item.line_total_nok, language)}</strong>
      <button type="button" className="remove-button" disabled={props.busy} onClick={() => void props.onRemove(item.id)}>{t('Remove')}</button>
      {groups.length > 0 && <label className="pickup-field cart-item__group"><span>{t('Pickup group')} · {item.meal.name}</span><select aria-label={`${t('Pickup group')} · ${item.meal.name}`} disabled={props.busy} value={item.group_id ?? ''} onChange={(event) => void props.onMove(item, event.target.value || null)}>
        <option value="">{t('Unassigned meals')}</option>{groups.map((candidate, position) => <option key={candidate.id} value={candidate.id}>{t('Pickup group')} {position + 1}{candidate.pickup_date ? ` · ${candidate.pickup_date}` : ''}</option>)}
      </select></label>}
    </article>)}</div>
    <div className="cart-summary">
      <div className="cart-total"><span>{t('Total')}</span><strong>{formatNok(total, language)}</strong></div>
      <label className="pickup-field"><span>{t('Pickup location')}</span><select aria-label={t('Pickup location')} value={location} disabled={props.busy || !props.pickupLocations} onChange={(event) => {
        if (group) void props.onSaveGroup(group.id, { pickup_location_id: event.target.value || null })
        else setLegacyLocation(event.target.value)
      }}><option value="">{t('Choose a pickup location')}</option>{location && !validLocation && <option value={location}>{t('Previous pickup location is unavailable')}</option>}{props.pickupLocations?.map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.name} — {candidate.address_line}, {candidate.postal_code} {candidate.city}</option>)}</select></label>
      <label className="pickup-field"><span>{t('Pickup date')}</span><select aria-label={t('Pickup date')} value={date} disabled={props.busy || !props.pickupOptions} onChange={(event) => {
        setDraft({ date: event.target.value, slot: '' })
        if (group?.pickup_date) void props.onSaveGroup(group.id, { pickup_date: null, pickup_slot: null })
      }}><option value="">{t('Choose a pickup date')}</option>{date && !day && <option value={date}>{date} · {t('Choose a new pickup date')}</option>}{props.pickupOptions?.days.map((candidate) => <option key={candidate.date} value={candidate.date}>{new Intl.DateTimeFormat(language === 'no' ? 'nb-NO' : 'en-GB', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'Europe/Oslo' }).format(new Date(`${candidate.date}T12:00:00Z`))}</option>)}</select></label>
      <label className="pickup-field"><span>{t('Pickup time')}</span><select aria-label={t('Pickup time')} value={slot} disabled={props.busy || !day} onChange={(event) => void changeSlot(event.target.value)}><option value="">{t('Choose a pickup time')}</option>{day?.slots.map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.id.replace('-', ':00–')}:00</option>)}</select></label>
      <p className="checkout-note">{t('Pickup is available from tomorrow. All times are local to Oslo.')}</p>
      <button type="button" className="checkout-button" disabled={props.busy || items.length === 0 || !validLocation || !validSlot || items.some((item) => !item.meal.available)} onClick={() => void props.onCheckout({ groupId: group?.id ?? null, location, date, slot })}>{t('Review and place order')}</button>
      <p className="checkout-note">{t('You will be asked to confirm before the order is created. No payment is required for this demo.')}</p>
    </div>
  </section>
}
