import { useState } from 'react'
import type { Meal } from '../api/meals'
import { useLanguage } from '../i18n'

export function MealArtwork({ meal, detail = false }: { meal: Pick<Meal, 'name' | 'image_url'>; detail?: boolean }) {
  const { t } = useLanguage()
  const [failedSource, setFailedSource] = useState<string | null>(null)
  const source = meal.image_url
  const className = `meal-artwork ${detail ? 'meal-artwork--detail' : ''}`
  if (source && source !== failedSource) {
    const illustrative = /^\/images\/meals\/[a-z-]+-v1\.webp$/.test(source)
    return <figure className="meal-artwork-frame">
      <img
        className={className}
        src={source}
        alt={illustrative ? `${meal.name} — ${t('AI-generated illustration')}` : meal.name}
        loading={detail ? 'eager' : 'lazy'}
        decoding="async"
        onError={() => setFailedSource(source)}
      />
      {illustrative && <figcaption>{t('AI-generated illustration. Actual presentation may vary.')}</figcaption>}
    </figure>
  }
  return <div className={`${className} meal-artwork--placeholder`} role="img" aria-label={`${t('No image available for')} ${meal.name}`}>
    <span>{t('Prepwise kitchen')}</span>
  </div>
}
