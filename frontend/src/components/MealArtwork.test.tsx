import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { LanguageProvider } from '../i18n'
import { MealArtwork } from './MealArtwork'

const meal = { name: 'Kylling teriyaki med ris', image_url: '/images/meals/chicken-teriyaki-v1.webp' }
afterEach(() => { cleanup(); localStorage.clear() })

describe('MealArtwork', () => {
  it('discloses generated images in Norwegian and defers card loading', () => {
    localStorage.clear()
    render(<LanguageProvider><MealArtwork meal={meal} /></LanguageProvider>)
    expect(screen.getByRole('img')).toHaveAttribute('alt', `${meal.name} — AI-generert illustrasjon`)
    expect(screen.getByRole('img')).toHaveAttribute('loading', 'lazy')
    expect(screen.getByText('AI-generert illustrasjon. Anretningen kan variere.')).toBeVisible()
  })
  it('uses English disclosure and eager loading for details', () => {
    localStorage.setItem('prepwise-language', 'en')
    render(<LanguageProvider><MealArtwork meal={meal} detail /></LanguageProvider>)
    expect(screen.getByRole('img')).toHaveAttribute('loading', 'eager')
    expect(screen.getByText('AI-generated illustration. Actual presentation may vary.')).toBeVisible()
  })
  it('does not label an authored image as AI-generated', () => {
    render(<MealArtwork meal={{ ...meal, image_url: 'https://example.invalid/real.jpg' }} />)
    expect(screen.getByRole('img')).toHaveAttribute('alt', meal.name)
    expect(screen.queryByText(/AI-generated illustration/)).not.toBeInTheDocument()
  })
  it('falls back after a failed load and retries when the source changes', () => {
    const { rerender } = render(<MealArtwork meal={meal} />)
    fireEvent.error(screen.getByRole('img'))
    expect(screen.getByRole('img')).toHaveAccessibleName(`No image available for ${meal.name}`)
    expect(screen.queryByText(/AI-generated illustration/)).not.toBeInTheDocument()
    rerender(<MealArtwork meal={{ ...meal, image_url: '/images/meals/taco-beef-v1.webp' }} />)
    expect(screen.getByRole('img')).toHaveAttribute('src', '/images/meals/taco-beef-v1.webp')
  })
  it('renders the existing placeholder for a meal without artwork', () => {
    render(<MealArtwork meal={{ ...meal, image_url: null }} />)
    expect(screen.getByRole('img')).toHaveAccessibleName(`No image available for ${meal.name}`)
  })
})
