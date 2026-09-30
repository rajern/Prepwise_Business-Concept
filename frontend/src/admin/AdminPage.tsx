import { useEffect, useState, type FormEvent } from 'react'

import {
  type AdminMealWrite,
  type AdminMeal,
  createAdminMeal,
  fetchAdminAllergens,
  fetchAdminMeals,
  updateAdminMeal,
} from '../api/adminMeals'
import { ApiRequestError, apiErrorMessage } from '../api/errors'
import type { Allergen } from '../api/meals'
import { OrdersPanel } from './OrdersPanel'
import { PickupLocationsPanel } from './PickupLocationsPanel'

interface AdminPageProps {
  accessToken: string
}

type AdminSection = 'meals' | 'pickup-locations' | 'orders'

interface MealFormState {
  name: string
  description: string
  nameEn: string
  descriptionEn: string
  imageUrl: string
  priceNok: string
  calories: string
  proteinGrams: string
  carbohydrateGrams: string
  fatGrams: string
  ingredients: string
  ingredientsEn: string[]
  allergenCodes: string[]
  available: boolean
}

const emptyForm: MealFormState = {
  name: '',
  description: '',
  nameEn: '',
  descriptionEn: '',
  imageUrl: '',
  priceNok: '',
  calories: '',
  proteinGrams: '',
  carbohydrateGrams: '',
  fatGrams: '',
  ingredients: '',
  ingredientsEn: [],
  allergenCodes: [],
  available: true,
}

export function AdminPage({ accessToken }: AdminPageProps) {
  const [section, setSection] = useState<AdminSection>('meals')

  return (
    <section className="admin-page" aria-labelledby="admin-heading">
      <div className="admin-shell-heading">
        <p className="eyebrow">Protected workspace</p>
        <h1 id="admin-heading">Admin</h1>
        <p>Manage the catalogue, pickup network and order fulfilment.</p>
      </div>
      <nav className="admin-tabs" aria-label="Admin sections">
        <AdminTab
          active={section === 'meals'}
          label="Meals"
          onClick={() => setSection('meals')}
        />
        <AdminTab
          active={section === 'pickup-locations'}
          label="Pickup locations"
          onClick={() => setSection('pickup-locations')}
        />
        <AdminTab
          active={section === 'orders'}
          label="Orders"
          onClick={() => setSection('orders')}
        />
      </nav>
      {section === 'meals' && <MealAdministration accessToken={accessToken} />}
      {section === 'pickup-locations' && (
        <PickupLocationsPanel accessToken={accessToken} />
      )}
      {section === 'orders' && <OrdersPanel accessToken={accessToken} />}
    </section>
  )
}

function AdminTab({
  active,
  label,
  onClick,
}: {
  active: boolean
  label: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      aria-current={active ? 'page' : undefined}
      onClick={onClick}
    >
      {label}
    </button>
  )
}

function MealAdministration({ accessToken }: AdminPageProps) {
  const [meals, setMeals] = useState<AdminMeal[] | null>(null)
  const [allergens, setAllergens] = useState<Allergen[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [form, setForm] = useState<MealFormState>(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    void Promise.all([
      fetchAdminMeals(accessToken, controller.signal),
      fetchAdminAllergens(accessToken, controller.signal),
    ])
      .then(([loadedMeals, loadedAllergens]) => {
        setMeals(loadedMeals)
        setAllergens(loadedAllergens)
      })
      .catch((reason: unknown) => {
        if (!(reason instanceof DOMException && reason.name === 'AbortError')) {
          setLoadError(
            reason instanceof ApiRequestError && reason.status === 403
              ? 'Your account does not have admin access.'
              : apiErrorMessage(reason, 'The admin catalogue could not be loaded.'),
          )
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

  function startEdit(meal: AdminMeal) {
    setEditingId(meal.id)
    setForm(mealToForm(meal))
    setSaveError(null)
    setSaveMessage(null)
  }

  function toggleAllergen(code: string, checked: boolean) {
    setForm((current) => ({
      ...current,
      allergenCodes: checked
        ? [...current.allergenCodes, code]
        : current.allergenCodes.filter((candidate) => candidate !== code),
    }))
  }

  function changeIngredients(value: string) {
    setForm((current) => {
      const previous = new Map(parseIngredients(current.ingredients).map((name, index) => [
        name.toLocaleLowerCase('nb'), current.ingredientsEn[index] ?? '',
      ]))
      return {
        ...current,
        ingredients: value,
        ingredientsEn: parseIngredients(value).map((name) =>
          previous.get(name.toLocaleLowerCase('nb')) ?? '',
        ),
      }
    })
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setSaveError(null)
    setSaveMessage(null)
    const payload: AdminMealWrite = {
      name: form.name,
      description: form.description,
      name_en: form.nameEn.trim() || null,
      description_en: form.descriptionEn.trim() || null,
      image_url: form.imageUrl.trim() || null,
      price_nok: Number(form.priceNok),
      calories: Number(form.calories),
      protein_grams: Number(form.proteinGrams),
      carbohydrate_grams: Number(form.carbohydrateGrams),
      fat_grams: Number(form.fatGrams),
      ingredients: parseIngredients(form.ingredients),
      ingredients_en: parseIngredients(form.ingredients).map((_, index) =>
        form.ingredientsEn[index]?.trim() || null,
      ),
      allergen_codes: form.allergenCodes,
      available: form.available,
    }

    try {
      const saved = editingId
        ? await updateAdminMeal(accessToken, editingId, payload)
        : await createAdminMeal(accessToken, payload)
      setMeals((current) =>
        [...(current ?? []).filter((meal) => meal.id !== saved.id), saved].sort(
          (left, right) => left.name.localeCompare(right.name, 'nb'),
        ),
      )
      setEditingId(saved.id)
      setForm(mealToForm(saved))
      setSaveMessage(editingId ? 'Meal changes saved.' : 'Meal created.')
    } catch (reason: unknown) {
      setSaveError(
        apiErrorMessage(reason, 'The meal could not be saved.'),
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="admin-section" aria-labelledby="meal-admin-heading">
      <div className="admin-heading">
        <div>
          <p className="eyebrow">Catalogue</p>
          <h2 id="meal-admin-heading">Meal administration</h2>
          <p>
            Create meals, update product information and control customer
            availability.
          </p>
        </div>
        <button type="button" onClick={startCreate}>
          New meal
        </button>
      </div>

      {loadError && (
        <div className="admin-state admin-state--error" role="alert">
          {loadError}
        </div>
      )}
      {(!meals || !allergens) && !loadError && (
        <div className="admin-state" role="status">
          Loading admin catalogue…
        </div>
      )}

      {meals && allergens && (
        <div className="admin-layout">
          <div className="admin-meal-list" aria-label="Meals">
            {meals.map((meal) => (
              <article
                className={`admin-meal-card ${
                  editingId === meal.id ? 'admin-meal-card--selected' : ''
                }`}
                key={meal.id}
              >
                <div>
                  <span
                    className={`availability ${
                      meal.available ? '' : 'availability--unavailable'
                    }`}
                  >
                    {meal.available ? 'Available' : 'Unavailable'}
                  </span>
                  <h2>{meal.name}</h2>
                  <p>{Number(meal.price_nok).toLocaleString('nb-NO')} kr</p>
                </div>
                <button type="button" onClick={() => startEdit(meal)}>
                  Edit
                </button>
              </article>
            ))}
          </div>

          <form className="admin-form" onSubmit={(event) => void submit(event)}>
            <div className="admin-form__heading">
              <div>
                <p className="eyebrow">{editingId ? 'Edit meal' : 'New meal'}</p>
                <h2>{editingId ? form.name : 'Create a meal'}</h2>
              </div>
              {editingId && (
                <button type="button" onClick={startCreate}>
                  Cancel edit
                </button>
              )}
            </div>

            <label>
              <span>Name (Norwegian)</span>
              <input
                required
                maxLength={200}
                value={form.name}
                onChange={(event) =>
                  setForm({ ...form, name: event.target.value, nameEn: '' })
                }
              />
            </label>
            <label>
              <span>Name (English)</span>
              <input
                maxLength={200}
                value={form.nameEn}
                onChange={(event) => setForm({ ...form, nameEn: event.target.value })}
              />
            </label>
            <label>
              <span>Description (Norwegian)</span>
              <textarea
                required
                maxLength={5000}
                rows={4}
                value={form.description}
                onChange={(event) =>
                  setForm({ ...form, description: event.target.value, descriptionEn: '' })
                }
              />
            </label>
            <label>
              <span>Description (English)</span>
              <textarea
                maxLength={5000}
                rows={4}
                value={form.descriptionEn}
                aria-describedby="english-translation-help"
                onChange={(event) => setForm({ ...form, descriptionEn: event.target.value })}
              />
            </label>
            <small id="english-translation-help">
              Empty English fields use the Norwegian text. Changing a Norwegian
              source clears its translation so it can be reviewed.
            </small>
            <label>
              <span>Image URL</span>
              <input
                type="url"
                value={form.imageUrl}
                placeholder="https://…"
                onChange={(event) =>
                  setForm({ ...form, imageUrl: event.target.value })
                }
              />
            </label>

            <div className="admin-form__numbers">
              <NumberField
                label="Price NOK"
                value={form.priceNok}
                step="0.01"
                onChange={(priceNok) => setForm({ ...form, priceNok })}
              />
              <NumberField
                label="Calories"
                value={form.calories}
                step="1"
                onChange={(calories) => setForm({ ...form, calories })}
              />
              <NumberField
                label="Protein grams"
                value={form.proteinGrams}
                step="0.01"
                onChange={(proteinGrams) => setForm({ ...form, proteinGrams })}
              />
              <NumberField
                label="Carbohydrate grams"
                value={form.carbohydrateGrams}
                step="0.01"
                onChange={(carbohydrateGrams) =>
                  setForm({ ...form, carbohydrateGrams })
                }
              />
              <NumberField
                label="Fat grams"
                value={form.fatGrams}
                step="0.01"
                onChange={(fatGrams) => setForm({ ...form, fatGrams })}
              />
            </div>

            <label>
              <span>Ingredients (Norwegian)</span>
              <textarea
                required
                rows={3}
                value={form.ingredients}
                aria-describedby="ingredient-help"
                placeholder="Kylling, ris, brokkoli"
                onChange={(event) => changeIngredients(event.target.value)}
              />
            </label>
            <small id="ingredient-help">Separate ingredients with commas.</small>
            {parseIngredients(form.ingredients).map((ingredient, index) => (
              <label key={index}>
                <span>English ingredient: {ingredient}</span>
                <input
                  maxLength={200}
                  value={form.ingredientsEn[index] ?? ''}
                  onChange={(event) => {
                    const ingredientsEn = [...form.ingredientsEn]
                    ingredientsEn[index] = event.target.value
                    setForm({ ...form, ingredientsEn })
                  }}
                />
              </label>
            ))}

            <fieldset>
              <legend>Allergens</legend>
              <div className="admin-allergens">
                {allergens.map((allergen) => (
                  <label key={allergen.code}>
                    <input
                      type="checkbox"
                      checked={form.allergenCodes.includes(allergen.code)}
                      onChange={(event) =>
                        toggleAllergen(allergen.code, event.target.checked)
                      }
                    />
                    <span>{allergen.name}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            <label className="admin-availability">
              <input
                type="checkbox"
                checked={form.available}
                onChange={(event) =>
                  setForm({ ...form, available: event.target.checked })
                }
              />
              <span>Available in the customer catalogue</span>
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
              {saving ? 'Saving…' : editingId ? 'Save changes' : 'Create meal'}
            </button>
          </form>
        </div>
      )}
    </section>
  )
}

function NumberField({
  label,
  value,
  step,
  onChange,
}: {
  label: string
  value: string
  step: string
  onChange: (value: string) => void
}) {
  return (
    <label>
      <span>{label}</span>
      <input
        required
        type="number"
        min="0"
        step={step}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}

function mealToForm(meal: AdminMeal): MealFormState {
  return {
    name: meal.name,
    description: meal.description,
    nameEn: meal.name_en ?? '',
    descriptionEn: meal.description_en ?? '',
    imageUrl: meal.image_url ?? '',
    priceNok: meal.price_nok,
    calories: String(meal.calories),
    proteinGrams: meal.protein_grams,
    carbohydrateGrams: meal.carbohydrate_grams,
    fatGrams: meal.fat_grams,
    ingredients: meal.ingredients.join(', '),
    ingredientsEn: meal.ingredients.map((_, index) => meal.ingredients_en?.[index] ?? ''),
    allergenCodes: meal.allergens.map((allergen) => allergen.code),
    available: meal.available,
  }
}

function parseIngredients(value: string): string[] {
  const seen = new Set<string>()
  return value.split(',').map((name) => name.trim()).filter((name) => {
    const key = name.toLocaleLowerCase('nb')
    if (!name || seen.has(key)) return false
    seen.add(key)
    return true
  })
}
