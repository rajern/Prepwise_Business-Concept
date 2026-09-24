import { useEffect, useState, type FormEvent } from 'react'

import {
  type AdminPickupLocation,
  type AdminPickupLocationWrite,
  AdminPickupLocationRequestError,
  createAdminPickupLocation,
  fetchAdminPickupLocations,
  updateAdminPickupLocation,
} from '../api/adminPickupLocations'

interface PickupLocationsPanelProps {
  accessToken: string
}

const emptyForm: AdminPickupLocationWrite = {
  name: '',
  address_line: '',
  postal_code: '',
  city: 'Oslo',
  active: true,
}

export function PickupLocationsPanel({
  accessToken,
}: PickupLocationsPanelProps) {
  const [locations, setLocations] = useState<AdminPickupLocation[] | null>(null)
  const [form, setForm] = useState<AdminPickupLocationWrite>(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    void fetchAdminPickupLocations(accessToken, controller.signal)
      .then(setLocations)
      .catch((reason: unknown) => {
        if (!(reason instanceof DOMException && reason.name === 'AbortError')) {
          setLoadError('Pickup locations could not be loaded.')
        }
      })
    return () => controller.abort()
  }, [accessToken])

  function startCreate() {
    setEditingId(null)
    setForm(emptyForm)
    setSaveError(null)
    setSaveMessage(null)
  }

  function startEdit(location: AdminPickupLocation) {
    setEditingId(location.id)
    setForm({
      name: location.name,
      address_line: location.address_line,
      postal_code: location.postal_code,
      city: location.city,
      active: location.active,
    })
    setSaveError(null)
    setSaveMessage(null)
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setSaveError(null)
    setSaveMessage(null)
    try {
      const saved = editingId
        ? await updateAdminPickupLocation(accessToken, editingId, form)
        : await createAdminPickupLocation(accessToken, form)
      setLocations((current) =>
        [...(current ?? []).filter((location) => location.id !== saved.id), saved].sort(
          (left, right) => left.name.localeCompare(right.name, 'nb'),
        ),
      )
      setEditingId(saved.id)
      setForm({
        name: saved.name,
        address_line: saved.address_line,
        postal_code: saved.postal_code,
        city: saved.city,
        active: saved.active,
      })
      setSaveMessage(editingId ? 'Pickup location saved.' : 'Pickup location created.')
    } catch (reason: unknown) {
      setSaveError(
        reason instanceof AdminPickupLocationRequestError
          ? reason.detail ?? 'The pickup location could not be saved.'
          : 'The pickup location could not be saved.',
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="admin-section" aria-labelledby="pickup-admin-heading">
      <div className="admin-heading">
        <div>
          <p className="eyebrow">Fulfilment setup</p>
          <h2 id="pickup-admin-heading">Pickup locations</h2>
          <p>Create locations and control whether customers can select them.</p>
        </div>
        <button type="button" onClick={startCreate}>
          New location
        </button>
      </div>

      {loadError && (
        <div className="admin-state admin-state--error" role="alert">
          {loadError}
        </div>
      )}
      {!locations && !loadError && (
        <div className="admin-state" role="status">
          Loading pickup locations…
        </div>
      )}

      {locations && (
        <div className="admin-layout">
          <div className="admin-record-list" aria-label="Pickup locations">
            {locations.map((location) => (
              <article
                className={`admin-record-card ${
                  editingId === location.id ? 'admin-record-card--selected' : ''
                }`}
                key={location.id}
              >
                <div>
                  <span
                    className={`availability ${
                      location.active ? '' : 'availability--unavailable'
                    }`}
                  >
                    {location.active ? 'Active' : 'Inactive'}
                  </span>
                  <h3>{location.name}</h3>
                  <p>
                    {location.address_line}, {location.postal_code} {location.city}
                  </p>
                </div>
                <button type="button" onClick={() => startEdit(location)}>
                  Edit
                </button>
              </article>
            ))}
          </div>

          <form className="admin-form" onSubmit={(event) => void submit(event)}>
            <div className="admin-form__heading">
              <div>
                <p className="eyebrow">{editingId ? 'Edit location' : 'New location'}</p>
                <h2>{editingId ? form.name : 'Create a pickup location'}</h2>
              </div>
              {editingId && (
                <button type="button" onClick={startCreate}>
                  Cancel edit
                </button>
              )}
            </div>

            <TextField
              label="Name"
              value={form.name}
              maxLength={200}
              onChange={(name) => setForm({ ...form, name })}
            />
            <TextField
              label="Address"
              value={form.address_line}
              maxLength={255}
              onChange={(address_line) => setForm({ ...form, address_line })}
            />
            <div className="admin-form__numbers">
              <TextField
                label="Postal code"
                value={form.postal_code}
                maxLength={4}
                pattern="[0-9]{4}"
                onChange={(postal_code) => setForm({ ...form, postal_code })}
              />
              <TextField
                label="City"
                value={form.city}
                maxLength={100}
                onChange={(city) => setForm({ ...form, city })}
              />
            </div>
            <label className="admin-availability">
              <input
                type="checkbox"
                checked={form.active}
                onChange={(event) => setForm({ ...form, active: event.target.checked })}
              />
              <span>Active and selectable during checkout</span>
            </label>

            {saveError && (
              <div className="admin-state admin-state--error" role="alert">
                {saveError}
              </div>
            )}
            {saveMessage && (
              <div className="admin-state admin-state--success" role="status">
                {saveMessage}
              </div>
            )}
            <button className="admin-save" type="submit" disabled={saving}>
              {saving ? 'Saving…' : editingId ? 'Save location' : 'Create location'}
            </button>
          </form>
        </div>
      )}
    </section>
  )
}

function TextField({
  label,
  value,
  maxLength,
  pattern,
  onChange,
}: {
  label: string
  value: string
  maxLength: number
  pattern?: string
  onChange: (value: string) => void
}) {
  return (
    <label>
      <span>{label}</span>
      <input
        required
        value={value}
        maxLength={maxLength}
        pattern={pattern}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}
