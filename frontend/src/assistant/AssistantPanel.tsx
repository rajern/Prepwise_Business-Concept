import { useEffect, useRef, useState, type FormEvent } from 'react'
import { sendAssistantMessage, type ChatMessage } from '../api/assistant'
import { ApiRequestError } from '../api/errors'
import { useLanguage } from '../i18n'

interface AssistantPanelProps {
  accessToken: string | null
  userId?: string | null
  onStateChange?: () => Promise<void>
}
const storageKey = 'prepwise-chat'

function loadMessages(userId: string | null): ChatMessage[] {
  if (!userId) return []
  try {
    const saved: unknown = JSON.parse(sessionStorage.getItem(storageKey) ?? 'null')
    if (!saved || typeof saved !== 'object') return []
    const record = saved as Record<string, unknown>
    if (record.userId !== userId || !Array.isArray(record.messages)) return []
    return record.messages.filter((item: unknown): item is ChatMessage => {
      if (!item || typeof item !== 'object') return false
      const message = item as Record<string, unknown>
      return (message.role === 'user' || message.role === 'assistant') && typeof message.content === 'string' && message.content.length <= 10000
    }).slice(-40)
  } catch { return [] }
}
function boundedHistory(messages: ChatMessage[]): ChatMessage[] {
  let characters = 0
  const result: ChatMessage[] = []
  for (const item of messages.slice(-10).reverse()) {
    if (item.content.length > 2000 || characters + item.content.length > 8000) break
    result.unshift(item)
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
  const [message, setMessage] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadMessages(userId))
  const [error, setError] = useState<string | null>(null)
  const [isSending, setIsSending] = useState(false)
  const [draft, setDraft] = useState('')
  const [stage, setStage] = useState<'thinking' | 'tools'>('thinking')
  const [retryAt, setRetryAt] = useState(0)
  const [secondsLeft, setSecondsLeft] = useState(0)
  const viewport = useRef<HTMLDivElement>(null)
  const textarea = useRef<HTMLTextAreaElement>(null)
  const launcher = useRef<HTMLButtonElement>(null)
  const active = useRef(true)
  const pending = useRef<AbortController | null>(null)
  useEffect(() => {
    active.current = true
    return () => { active.current = false; pending.current?.abort() }
  }, [])
  useEffect(() => {
    try {
      if (!accessToken) sessionStorage.removeItem(storageKey)
      else if (userId) sessionStorage.setItem(storageKey, JSON.stringify({ userId, messages }))
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
    if (!trimmed || !accessToken || isSending || secondsLeft > 0) return
    const history = boundedHistory(messages)
    setMessages((previous) => [...previous, { role: 'user', content: trimmed } as ChatMessage].slice(-40))
    setMessage('')
    setIsSending(true)
    setDraft('')
    setStage('thinking')
    setError(null)
    const controller = new AbortController()
    pending.current = controller
    const current = () => active.current && pending.current === controller && !controller.signal.aborted
    try {
      const response = await sendAssistantMessage(accessToken, trimmed, controller.signal, language, history, (event) => {
        if (!current()) return
        if (event.type === 'delta') setDraft((previous) => (previous + event.text).slice(0, 20000))
        if (event.type === 'reset') setDraft('')
        if (event.type === 'progress') setStage(event.stage)
      })
      if (current()) {
        setDraft('')
        setMessages((previous) => [...previous, { role: 'assistant', content: response.reply } as ChatMessage].slice(-40))
      }
    } catch (reason: unknown) {
      if (!current()) return
      setDraft('')
      let text = t('The AI assistant is unavailable right now. Please try again.')
      if (reason instanceof ApiRequestError) {
        if (reason.status === 401) text = t('Your session has expired. Sign in again.')
        if (reason.status === 429) {
          text = reason.code === 'request_in_progress' ? t('A message is already being processed. Please wait.') : t('You have reached the chat limit. Please try again later.')
          const retrySeconds = reason.retryAfter ?? 30
          setSecondsLeft(retrySeconds)
          setRetryAt(Date.now() + retrySeconds * 1000)
        }
      }
      setError(text)
      setMessage(trimmed)
      setMessages((previous) => previous.slice(0, -1))
    } finally {
      // Partial writes must be reflected even if the last model call fails.
      if (current()) {
        try { await onStateChange?.() } catch { /* Parent reports refresh failures. */ }
        if (current()) { setIsSending(false); pending.current = null }
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
          {messages.map((item, index) => <div className={'chat-message chat-message--' + item.role} key={index}><span>{item.role === 'user' ? t('You') : 'Prepwise'}</span><p>{item.content}</p></div>)}
          {draft && <div className="chat-message chat-message--assistant"><span>{t('Draft — checking before confirmation')}</span><p>{draft}</p></div>}
          {isSending && <p className="chat-typing" role="status">{t(stage === 'tools' ? 'Checking current information…' : 'Thinking…')}</p>}
        </div>
        {error && <div className="assistant-error" role="alert">{error}{secondsLeft > 0 && <span> ({secondsLeft}s)</span>}</div>}
        <form className="assistant-form chat-form" onSubmit={(event) => void submitMessage(event)}>
          <label htmlFor="assistant-message">{t('Message')}</label>
          <textarea ref={textarea} id="assistant-message" value={message} maxLength={1000} rows={2} placeholder={t('What can you help me with?')} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }} />
          <div className="chat-actions"><button type="button" className="chat-reset" disabled={isSending} onClick={() => { setMessages([]); setError(null) }}>{t('New chat')}</button><button type="submit" disabled={isSending || secondsLeft > 0 || !message.trim()}>{t('Send message')}</button></div>
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
