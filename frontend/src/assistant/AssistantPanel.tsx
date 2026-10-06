import { useEffect, useRef, useState, type FormEvent } from 'react'
import { sendAssistantMessage, type ChatMessage } from '../api/assistant'
import { ApiRequestError } from '../api/errors'
import { useLanguage, type Language } from '../i18n'

interface AssistantPanelProps {
  accessToken: string | null
  userId?: string | null
  onStateChange?: () => Promise<void>
}
const storageKey = 'prepwise-chat'
type TranscriptMessage = ChatMessage & { state?: 'pending' | 'failed' | 'uncertain' | 'applied'; requestKey?: string; attempt?: Attempt }
interface Attempt { key: string; message: string; language: Language; history: ChatMessage[] }

function loadMessages(userId: string | null): TranscriptMessage[] {
  if (!userId) return []
  try {
    const saved: unknown = JSON.parse(sessionStorage.getItem(storageKey) ?? 'null')
    if (!saved || typeof saved !== 'object') return []
    const record = saved as Record<string, unknown>
    if (record.userId !== userId || !Array.isArray(record.messages)) return []
    return record.messages.filter((item: unknown): item is TranscriptMessage => {
      if (!item || typeof item !== 'object') return false
      const message = item as Record<string, unknown>
      return (message.role === 'user' || message.role === 'assistant') && typeof message.content === 'string' && message.content.length <= 10000
    }).slice(-40).map((item) => item.state === 'pending' ? { ...item, state: 'uncertain' } : item)
  } catch { return [] }
}
function loadAttempt(userId: string | null): Attempt | null {
  if (!userId) return null
  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey) ?? 'null')
    const value = saved?.userId === userId ? saved.attempt : null
    return validatedAttempt(value)
  } catch { /* Optional storage. */ }
  return null
}
function validatedAttempt(value: unknown): Attempt | null {
  if (!value || typeof value !== 'object') return null
  const attempt = value as Record<string, unknown>
  if (typeof attempt.key !== 'string' || !/^[0-9a-f-]{36}$/i.test(attempt.key) || typeof attempt.message !== 'string' || attempt.message.length > 1000 || (attempt.language !== 'no' && attempt.language !== 'en') || !Array.isArray(attempt.history)) return null
  const history = attempt.history.filter((item): item is ChatMessage => item && (item.role === 'user' || item.role === 'assistant') && typeof item.content === 'string')
  return { key: attempt.key, message: attempt.message, language: attempt.language, history: boundedHistory(history) }
}
function boundedHistory(messages: TranscriptMessage[]): ChatMessage[] {
  let characters = 0
  const result: ChatMessage[] = []
  for (const item of messages.filter((item) => !item.state).slice(-10).reverse()) {
    if (item.content.length > 2000 || characters + item.content.length > 8000) break
    result.unshift({ role: item.role, content: item.content })
    characters += item.content.length
  }
  return result
}
export function AssistantPanel(props: AssistantPanelProps) {
  return <AssistantConversation key={props.userId ?? (props.accessToken ? 'signed-in' : 'signed-out')} {...props} />
}
function AssistantConversation({ accessToken, userId = null, onStateChange }: AssistantPanelProps) {
  const { t, language } = useLanguage()
  const [open, setOpen] = useState(false)
  const [message, setMessage] = useState(() => loadAttempt(userId)?.message ?? '')
  const [messages, setMessages] = useState<TranscriptMessage[]>(() => loadMessages(userId))
  const [error, setError] = useState<string | null>(null)
  const [isSending, setIsSending] = useState(false)
  const [draft, setDraft] = useState('')
  const [stage, setStage] = useState<'thinking' | 'tools' | 'writing'>('thinking')
  const [retryAt, setRetryAt] = useState(0)
  const [secondsLeft, setSecondsLeft] = useState(0)
  const viewport = useRef<HTMLDivElement>(null)
  const textarea = useRef<HTMLTextAreaElement>(null)
  const launcher = useRef<HTMLButtonElement>(null)
  const active = useRef(true)
  const pending = useRef<AbortController | null>(null)
  const attempt = useRef<Attempt | null>(loadAttempt(userId))
  const latestStateChange = useRef(onStateChange)
  useEffect(() => { latestStateChange.current = onStateChange }, [onStateChange])
  useEffect(() => {
    active.current = true
    return () => { active.current = false; pending.current?.abort() }
  }, [])
  useEffect(() => {
    try {
      if (!accessToken) sessionStorage.removeItem(storageKey)
      else if (userId) sessionStorage.setItem(storageKey, JSON.stringify({ userId, messages, attempt: attempt.current }))
    } catch { /* Optional browser storage. */ }
  }, [accessToken, userId, messages])
  useEffect(() => {
    if (!retryAt) return
    const update = () => setSecondsLeft(Math.max(0, Math.ceil((retryAt - Date.now()) / 1000)))
    update()
    const timer = window.setInterval(update, 1000)
    return () => window.clearInterval(timer)
  }, [retryAt])
  useEffect(() => { if (open) textarea.current?.focus() }, [open])
  useEffect(() => {
    if (viewport.current) viewport.current.scrollTop = viewport.current.scrollHeight
  }, [messages, draft, isSending, open])
  function closeChat() { setOpen(false); launcher.current?.focus() }
  async function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = message.trim()
    if (!trimmed || !accessToken || pending.current || secondsLeft > 0) return
    const older = [...messages].reverse().find((item) => item.content === trimmed && (item.state === 'uncertain' || item.state === 'failed'))
    const saved = validatedAttempt(older?.attempt)
    const request = attempt.current?.message === trimmed ? attempt.current : saved ?? {
      key: crypto.randomUUID(), message: trimmed, language, history: boundedHistory(messages),
    }
    attempt.current = request
    setMessages((previous) => [...previous.filter((item) => item.requestKey !== request.key), { role: 'user', content: trimmed, requestKey: request.key, state: 'pending', attempt: request } as TranscriptMessage].slice(-40))
    setMessage('')
    setIsSending(true)
    setDraft('')
    setStage('thinking')
    setError(null)
    const controller = new AbortController()
    pending.current = controller
    const observed: { mutation: 'none' | 'unknown' | 'applied'; requestId: string | null } = { mutation: 'none', requestId: null }
    const current = () => active.current && pending.current === controller && !controller.signal.aborted
    try {
      const response = await sendAssistantMessage(accessToken, request.message, controller.signal, request.language, request.history, (event) => {
        if (!current()) return
        if (event.type === 'delta') setDraft((previous) => (previous + event.text).slice(0, 20000))
        if (event.type === 'reset') setDraft('')
        if (event.type === 'progress') setStage(event.stage)
        if (event.type === 'mutation') {
          if (event.mutation_status !== 'none') { observed.mutation = event.mutation_status; setStage('writing') }
          if (event.request_id) observed.requestId = event.request_id
        }
      }, request.key)
      if (current()) {
        attempt.current = null
        setDraft('')
        setMessages((previous) => [...previous.map((item) => item.requestKey === request.key ? { ...item, state: undefined, attempt: undefined } : item), { role: 'assistant', content: response.reply } as ChatMessage].slice(-40))
      }
    } catch (reason: unknown) {
      if (!current()) return
      setDraft('')
      let text = t('The AI assistant is unavailable right now. Please try again.')
      const uncertain = !(reason instanceof ApiRequestError) || (reason.mutationStatus !== 'none' && reason.status !== 401 && reason.status !== 403 && reason.status !== 429 && reason.status !== 422)
      const applied = (reason instanceof ApiRequestError && reason.mutationStatus === 'applied') || observed.mutation === 'applied'
      const completedReadOnly = reason instanceof ApiRequestError && reason.code === 'assistant_request_completed' && reason.mutationStatus === 'none'
      if (uncertain) text = t('The message outcome is uncertain. Check your cart and orders before doing anything again. Retrying this exact message keeps the same request reference.')
      if (applied) text = t('Changes were applied. Check your cart and orders; do not repeat the request.')
      if (completedReadOnly) text = t('This message was already processed. Send a new message if you need more help.')
      if (reason instanceof ApiRequestError) {
        if (reason.status === 401) text = t('Your session has expired. Sign in again.')
        if (reason.status === 429 || reason.code === 'request_in_progress') {
          text = reason.code === 'request_in_progress' ? t('A message is already being processed. Please wait.') : t('You have reached the chat limit. Please try again later.')
          const retrySeconds = reason.retryAfter ?? 30
          setSecondsLeft(retrySeconds)
          setRetryAt(Date.now() + retrySeconds * 1000)
        }
      }
      const requestId = reason instanceof ApiRequestError ? reason.requestId ?? observed.requestId : observed.requestId
      if (requestId) text += ` ${t('Reference')}: ${requestId}`
      if (applied || completedReadOnly) attempt.current = null
      setError(text)
      setMessage(applied || completedReadOnly ? '' : trimmed)
      setMessages((previous) => previous.map((item) => item.requestKey === request.key ? { ...item, state: applied ? 'applied' : uncertain ? 'uncertain' : 'failed' } : item))
    } finally {
      // Partial writes must be reflected even if the last model call fails.
      if (current()) {
        // A hung refresh must not leave the composer permanently locked.
        try { void latestStateChange.current?.().catch(() => undefined) } catch { /* Parent reports refresh failures. */ }
        setIsSending(false); pending.current = null
      }
    }
  }
  return <div className="chat-widget">
    {open && <section id="prepwise-chat" className="chat-panel" aria-labelledby="assistant-heading" onKeyDown={(event) => { if (event.key === 'Escape') closeChat() }}>
      <header className="chat-header"><div><p className="eyebrow">{t('AI assistant')}</p><h2 id="assistant-heading">{t('Ask Prepwise')}</h2></div>
        <button className="chat-close" type="button" onClick={closeChat} aria-label={t('Close chat')}>×</button>
      </header>
      {!accessToken ? <div className="chat-sign-in"><h3>{t('Signed-in customers')}</h3><p>{t('Sign in to chat about meals, your cart, orders and pickup.')}</p><button className="auth-button" type="button" onClick={() => { closeChat(); const button = document.getElementById('sign-in-button'); button?.scrollIntoView?.({ block: 'center', behavior: 'smooth' }); button?.focus() }}>{t('Go to sign in')}</button></div> : <>
        <div className="chat-messages" ref={viewport} role="log" aria-label={t('Ask Prepwise')} aria-live="polite" aria-relevant="additions text">
          {messages.length === 0 && <div className="chat-welcome"><p>{t('Ask about meals, or let me help with your cart.')}</p><p>{t('Ask about available meals, your cart and orders, pickup, storage, reheating, allergens, or other Prepwise guidance.')}</p></div>}
          {messages.map((item, index) => <div className={'chat-message chat-message--' + item.role} key={index}><span>{item.role === 'user' ? t('You') : 'Prepwise'}</span><p>{item.content}</p>{item.state && <small>{t(item.state === 'pending' ? 'Awaiting confirmation' : item.state === 'applied' ? 'Changes applied — check your cart and orders' : item.state === 'uncertain' ? 'Outcome uncertain — not a confirmed action' : 'Message failed')}</small>}</div>)}
          {draft && <div className="chat-message chat-message--assistant"><span>{t('Draft — checking before confirmation')}</span><p>{draft}</p></div>}
          {isSending && <p className="chat-typing" role="status">{t(stage === 'writing' ? 'Updating your cart…' : stage === 'tools' ? 'Checking current information…' : 'Thinking…')}</p>}
        </div>
        {error && <div className="assistant-error" role="alert">{error}{secondsLeft > 0 && <span> ({secondsLeft}s)</span>}</div>}
        <form className="assistant-form chat-form" onSubmit={(event) => void submitMessage(event)}>
          <label htmlFor="assistant-message">{t('Message')}</label>
          <textarea ref={textarea} id="assistant-message" value={message} maxLength={1000} rows={2} placeholder={t('What can you help me with?')} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }} />
          <div className="chat-actions"><button type="button" className="chat-reset" disabled={isSending} onClick={() => { attempt.current = null; setMessages([]); setError(null) }}>{t('New chat')}</button><button type="submit" disabled={isSending || secondsLeft > 0 || !message.trim()}>{t('Send message')}</button></div>
          <p className="chat-privacy">{t('This conversation stays in this tab and is cleared when you sign out.')}</p>
        </form>
      </>}
    </section>}
    {!open && <span className="chat-hint">{t('Ask Prepwise')}</span>}
    <button ref={launcher} className="chat-launcher" type="button" aria-expanded={open} aria-controls="prepwise-chat" aria-label={open ? t('Close chat') : t('Open chat')} onClick={() => open ? closeChat() : setOpen(true)}>
      {open ? '×' : <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true"><path d="M20 11a8 8 0 0 1-8 8H5l-4 3V11a9 9 0 0 1 19 0Z" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="M7 10h.01M11 10h.01M15 10h.01" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" /></svg>}
    </button>
  </div>
}
