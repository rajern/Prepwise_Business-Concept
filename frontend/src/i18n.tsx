/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export type Language = 'no' | 'en'

const norwegian: Record<string, string> = {
  'Your order was placed, but order history could not be refreshed.': 'Bestillingen er registrert, men vi kunne ikke oppdatere ordrehistorikken.',
  'Meals': 'Måltider',
  'Primary navigation': 'Hovedmeny',
  'Prepwise home': 'Prepwise hjem',
  'Sign in or create account': 'Logg inn eller opprett konto',
  'Sign-in could not be started. Please try again.': 'Kunne ikke starte innlogging. Prøv igjen.',
  'Preparing secure API access…': 'Logger deg inn…',
  'Signed in': 'Innlogget',
  'Additional confirmation is required for API access.': 'Bekreft innloggingen for å fortsette.',
  'API access could not be prepared. Please try again.': 'Kunne ikke fullføre innloggingen. Prøv igjen.',
  'Continue': 'Fortsett',
  'Sign out': 'Logg ut',
  'Authentication could not be completed. Please try again.': 'Kunne ikke fullføre innloggingen. Prøv igjen.',
  'Pickup meals in Oslo': 'Ferdige måltider i Oslo',
  'Ready meals, without the guesswork.': 'Ferdige måltider. Full oversikt.',
  'Pick balanced meals with clear nutrition and collect them from a convenient location in Oslo.': 'Velg balanserte måltider med tydelig næringsinnhold, og hent dem på et hentested i Oslo.',
  'This week': 'Menyen',
  'Choose your meals': 'Velg dine måltider',
  'Filter meals': 'Filtrer måltider',
  'Search': 'Søk',
  'Meal or ingredient': 'Måltid eller ingrediens',
  'Nutrition': 'Næringsinnhold',
  'All meals': 'Alle måltider',
  '40 g+ protein': 'Minst 40 g protein',
  'Under 600 kcal': 'Under 600 kcal',
  'Loading the menu…': 'Laster menyen…',
  'Try again': 'Prøv igjen',
  'No meals are available right now.': 'Ingen måltider er tilgjengelige akkurat nå.',
  'No meals match those filters. Try a different search or nutrition filter.': 'Ingen måltider passer filtrene. Prøv et annet søk eller næringsfilter.',
  'Allergens': 'Allergener',
  'No declared allergens': 'Ingen oppgitte allergener',
  'View details': 'Se detaljer',
  'Adding…': 'Legger til…',
  'Add to cart': 'Legg i handlekurv',
  'Sign in to add': 'Logg inn for å legge til',
  'Meal details': 'Måltidsdetaljer',
  'Close': 'Lukk',
  'Loading meal details…': 'Laster måltidsdetaljer…',
  'Available this week': 'Tilgjengelig',
  'Currently unavailable': 'Ikke tilgjengelig',
  'Ingredients': 'Ingredienser',
  'Your order': 'Din bestilling',
  'Shopping cart': 'Handlekurv',
  'Loading your cart…': 'Laster handlekurven…',
  'Your cart is empty. Add a meal below.': 'Handlekurven er tom. Velg et måltid fra menyen.',
  'each': 'per stk.',
  'unavailable': 'ikke tilgjengelig',
  'Quantity for': 'Antall for',
  'Decrease': 'Reduser antall',
  'Increase': 'Øk antall',
  'Remove': 'Fjern',
  'Total': 'Totalt',
  'Pickup location': 'Hentested',
  'Choose a pickup location': 'Velg hentested',
  'Pickup date': 'Hentedato',
  'Choose a pickup date': 'Velg hentedato',
  'Pickup time': 'Hentetid',
  'Choose a pickup time': 'Velg hentetid',
  'Pickup is available from tomorrow. All times are local to Oslo.': 'Henting er tilgjengelig fra i morgen. Alle tidspunkter er i norsk tid.',
  'Placing order…': 'Bestiller…',
  'Review and place order': 'Se over og bestill',
  'You will be asked to confirm before the order is created. No payment is required for this demo.': 'Du må bekrefte før bestillingen opprettes. Ingen betaling kreves i denne demoen.',
  'Order history': 'Ordrehistorikk',
  'Your previous orders': 'Dine tidligere bestillinger',
  'Loading your orders…': 'Laster bestillingene…',
  'You have not placed any orders yet.': 'Du har ikke bestilt noe ennå.',
  'View order': 'Se bestilling',
  'Order details': 'Ordredetaljer',
  'Received': 'Mottatt',
  'Preparing': 'Under tilberedning',
  'Ready For Pickup': 'Klar for henting',
  'Completed': 'Fullført',
  'Pickup': 'Henting',
  'Carbs': 'Karbohydrater',
  'Fat': 'Fett',
  'Prepwise kitchen': 'Prepwise-kjøkkenet',
  'No image available for': 'Bilde mangler for',
  'AI assistant': 'AI-assistent',
  'Ask Prepwise': 'Spør Prepwise',
  'Open chat': 'Åpne chat',
  'Close chat': 'Lukk chat',
  'Signed-in customers': 'For innloggede kunder',
  'Ask about meals, or let me help with your cart.': 'Spør om måltider, eller få hjelp med handlekurven.',
  'Sign in to chat about meals, your cart, orders and pickup.': 'Logg inn for å chatte om måltider, handlekurven, bestillinger og henting.',
  'Go to sign in': 'Gå til innlogging',
  'Ask about available meals, your cart and orders, pickup, storage, reheating, allergens, or other Prepwise guidance.': 'Spør om måltider, handlekurven, bestillinger, henting, oppbevaring, oppvarming og allergener hos Prepwise.',
  'Message': 'Melding',
  'What can you help me with?': 'Hva vil du ha hjelp med?',
  'Send message': 'Send melding',
  'Sending…': 'Svarer…',
  'You': 'Deg',
  'New chat': 'Ny samtale',
  'This conversation stays in this tab and is cleared when you sign out.': 'Samtalen beholdes i denne fanen og slettes når du logger ut.',
  'Added to your cart': 'Lagt i handlekurven',
  'Open cart': 'Åpne handlekurv',
  'Close cart': 'Lukk handlekurv',
  'Sign in to use your cart.': 'Logg inn for å bruke handlekurven.',
  'A portfolio project by Rajvir Singh Aujla.': 'Et porteføljeprosjekt av Rajvir Singh Aujla.',
  'Prepwise is a demonstration project, not a commercial meal service.': 'Prepwise er et demonstrasjonsprosjekt og ikke en kommersiell måltidstjeneste.',
  'Email': 'E-post',
  'Source code': 'Kildekode',
  'Your session has expired. Sign in again.': 'Økten er utløpt. Logg inn igjen.',
  'You do not have permission to perform this action.': 'Du har ikke tilgang til å utføre denne handlingen.',
  'We could not load the menu. Please try again.': 'Kunne ikke laste menyen. Prøv igjen.',
  'This meal could not be found. It may have been removed.': 'Fant ikke måltidet. Det kan ha blitt fjernet.',
  'We could not load the meal details. Please try again.': 'Kunne ikke laste måltidsdetaljene. Prøv igjen.',
  'We could not load your cart. Please try again.': 'Kunne ikke laste handlekurven. Prøv igjen.',
  'We could not load the pickup locations. Please try again.': 'Kunne ikke laste hentestedene. Prøv igjen.',
  'We could not load the pickup times. Please try again.': 'Kunne ikke laste hentetidene. Prøv igjen.',
  'We could not load your order history. Please try again.': 'Kunne ikke laste ordrehistorikken. Prøv igjen.',
  'We could not update your cart. Please try again.': 'Kunne ikke oppdatere handlekurven. Prøv igjen.',
  'That meal is no longer available.': 'Måltidet er ikke lenger tilgjengelig.',
  'Choose an active pickup location before checkout.': 'Velg et tilgjengelig hentested før du bestiller.',
  'Checkout failed. Your cart has not been changed.': 'Bestillingen kunne ikke fullføres. Handlekurven er ikke endret.',
  'Check your cart and choose a valid pickup time.': 'Kontroller handlekurven og velg en tilgjengelig hentetid.',
  'We could not load that order. Please try again.': 'Kunne ikke laste bestillingen. Prøv igjen.',
  'The AI assistant is unavailable right now. Please try again.': 'AI-assistenten er utilgjengelig akkurat nå. Prøv igjen.',
  'You have reached the chat limit. Please try again later.': 'Du har nådd grensen for chatten. Prøv igjen senere.',
  'A message is already being processed. Please wait.': 'En melding behandles allerede. Vent til den er ferdig.',
  'We could not refresh your cart and orders. Open the cart to try again.': 'Kunne ikke oppdatere handlekurven og bestillingene. Åpne handlekurven for å prøve igjen.',
}

interface LanguageContextValue {
  language: Language
  setLanguage: (language: Language) => void
  t: (english: string) => string
}

// Standalone admin and auth components retain English outside the customer provider.
const LanguageContext = createContext<LanguageContextValue>({
  language: 'en', setLanguage: () => undefined, t: (text) => text,
})

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, updateLanguage] = useState<Language>(() => {
    try { return localStorage.getItem('prepwise-language') === 'en' ? 'en' : 'no' }
    catch { return 'no' }
  })
  const setLanguage = useCallback((next: Language) => {
    updateLanguage(next)
    try { localStorage.setItem('prepwise-language', next) } catch { /* Optional persistence. */ }
  }, [])
  const t = useCallback((text: string) => translate(text, language), [language])
  const value = useMemo(() => ({ language, setLanguage, t }), [language, setLanguage, t])
  useEffect(() => { document.documentElement.lang = language === 'no' ? 'nb' : 'en' }, [language])
  return <LanguageContext value={value}>{children}</LanguageContext>
}

export function translate(text: string, language: Language): string {
  return language === 'no' ? norwegian[text] ?? text : text
}

export function useLanguage() { return useContext(LanguageContext) }

export function formatNok(value: string | number, language: Language): string {
  return new Intl.NumberFormat(language === 'no' ? 'nb-NO' : 'en-GB', { style: 'currency', currency: 'NOK', maximumFractionDigits: 0 }).format(Number(value))
}

export function formatPickup(start: string, end: string, language: Language): string {
  const locale = language === 'no' ? 'nb-NO' : 'en-GB'
  return `${new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Oslo' }).format(new Date(start))}–${new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Oslo' }).format(new Date(end))}`
}
