/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export type Language = 'no' | 'en'

const norwegian: Record<string, string> = {
  'Previous pickup location is unavailable': 'Tidligere hentested er ikke tilgjengelig',
  'Your account': 'Din konto',
  'Completed and cancelled orders. Active orders are shown above the meal menu.': 'Fullførte og kansellerte bestillinger. Aktive bestillinger vises over måltidsmenyen.',
  'Choose a new pickup date': 'Velg en ny hentedato',
  'Remove empty group': 'Fjern tom hentegruppe',
  'We could not confirm checkout. Check your cart and upcoming orders before trying again.': 'Kunne ikke bekrefte bestillingen. Kontroller handlekurven og kommende bestillinger før du prøver igjen.',
  'Thinking…': 'Tenker…',
  'Checking current information…': 'Sjekker oppdaterte opplysninger…',
  'Draft — checking before confirmation': 'Utkast – kontrolleres før bekreftelse',
  'meals': 'måltider',
  'Upcoming orders': 'Kommende bestillinger',
  'Cancelled': 'Kansellert',
  'Close order': 'Lukk bestilling',
  'Loading order details…': 'Laster bestillingsdetaljer…',
  'Sign in to view your orders.': 'Logg inn for å se bestillingene dine.',
  'Cancel order': 'Kanseller bestilling',
  'Cancelling…': 'Kansellerer…',
  'Cancel this order? This cannot be undone.': 'Kansellere denne bestillingen? Dette kan ikke angres.',
  'This order could not be cancelled. Refresh the orders and check the cancellation deadline.': 'Kunne ikke kansellere bestillingen. Oppdater bestillingene og kontroller kanselleringsfristen.',
  'To change pickup after ordering, cancel and place a new order. Cancellation is only possible before the pickup day (Oslo time).': 'For å endre henting etter bestilling må du kansellere og bestille på nytt. Du kan bare kansellere før hentedagen begynner (norsk tid).',
  'Each pickup group becomes a separate order. You can choose different days and locations.': 'Hver hentegruppe blir en egen bestilling. Du kan velge ulike dager og hentesteder.',
  'Add pickup group': 'Legg til hentegruppe',
  'Pickup group': 'Hentegruppe',
  'Unassigned meals': 'Måltider uten hentegruppe',
  'Add meals to': 'Legg måltider i',
  'Add meals to this group from the menu or move them from another group.': 'Legg måltider i denne gruppen fra menyen, eller flytt dem fra en annen gruppe.',
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
  'AI-generated illustration': 'AI-generert illustrasjon',
  'AI-generated illustration. Actual presentation may vary.': 'AI-generert illustrasjon. Anretningen kan variere.',
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
  'Your cart changed. Review the refreshed cart before trying again.': 'Handlekurven er endret. Se over den oppdaterte handlekurven før du prøver igjen.',
  'Resolve the previous checkout before placing a different order.': 'Avklar den forrige bestillingen før du legger inn en ny.',
  'Confirm this order?': 'Bekreft denne bestillingen?',
  'Retry the previous checkout with the same request reference? No new order will be added if it already succeeded.': 'Prøv den forrige bestillingen igjen med samme referanse? Ingen ny ordre opprettes dersom den allerede lyktes.',
  'The previous checkout outcome is unknown. Check your orders or retry the same checkout safely.': 'Utfallet av forrige bestilling er ukjent. Sjekk bestillingene dine eller prøv samme bestilling igjen trygt.',
  'Check previous checkout': 'Kontroller forrige bestilling',
  'Pickup time has passed — collection is not confirmed.': 'Hentetiden er passert – henting er ikke bekreftet.',
  'The message outcome is uncertain. Check your cart and orders before doing anything again. Retrying this exact message keeps the same request reference.': 'Utfallet av meldingen er usikkert. Sjekk handlekurven og bestillingene før du gjør noe igjen. Gjentakelse av nøyaktig samme melding beholder samme referanse.',
  'Outcome uncertain — not a confirmed action': 'Usikkert utfall – ikke en bekreftet handling',
  'Message failed': 'Meldingen feilet',
  'Changes were applied. Check your cart and orders; do not repeat the request.': 'Endringer er gjennomført. Sjekk handlekurven og bestillingene; ikke gjenta forespørselen.',
  'Changes applied — check your cart and orders': 'Endringer gjennomført – sjekk handlekurven og bestillingene',
  'Updating your cart…': 'Oppdaterer handlekurven…',
  'Reference': 'Referanse',
  'Awaiting confirmation': 'Venter på bekreftelse',
  'This message was already processed. Send a new message if you need more help.': 'Denne meldingen er allerede behandlet. Send en ny melding hvis du trenger mer hjelp.',
  'Completed, cancelled and past pickup windows. Upcoming orders are shown above the meal menu.': 'Fullførte, kansellerte og bestillinger med passert hentetid. Kommende bestillinger vises over menyen.',
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
