import { useState, type FormEvent } from 'react'

import { sendAssistantMessage, type AssistantResponse } from '../api/assistant'
import { apiErrorMessage } from '../api/errors'

interface AssistantPanelProps {
  accessToken: string
}

export function AssistantPanel({ accessToken }: AssistantPanelProps) {
  const [message, setMessage] = useState('')
  const [response, setResponse] = useState<AssistantResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSending, setIsSending] = useState(false)

  async function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmedMessage = message.trim()
    if (!trimmedMessage || isSending) {
      return
    }

    setIsSending(true)
    setError(null)
    try {
      setResponse(await sendAssistantMessage(accessToken, trimmedMessage))
      setMessage('')
    } catch (reason: unknown) {
      setError(
        apiErrorMessage(
          reason,
          'The AI assistant is unavailable right now. Please try again.',
        ),
      )
    } finally {
      setIsSending(false)
    }
  }

  return (
    <section className="assistant-panel" aria-labelledby="assistant-heading">
      <div className="assistant-panel__heading">
        <div>
          <p className="eyebrow">AI assistant</p>
          <h2 id="assistant-heading">Ask Prepwise</h2>
        </div>
        <span className="assistant-panel__status">Signed-in customers</span>
      </div>
      <p className="assistant-panel__intro">
        The assistant is being connected to live Prepwise data. It will say when a
        question needs a capability that is not available yet.
      </p>

      {response && (
        <div className="assistant-response" aria-live="polite">
          <span>Prepwise</span>
          <p>{response.reply}</p>
        </div>
      )}
      {error && (
        <div className="assistant-error" role="alert">
          {error}
        </div>
      )}

      <form className="assistant-form" onSubmit={(event) => void submitMessage(event)}>
        <label htmlFor="assistant-message">Message</label>
        <textarea
          id="assistant-message"
          value={message}
          maxLength={4000}
          rows={3}
          placeholder="What can you help me with?"
          onChange={(event) => setMessage(event.target.value)}
        />
        <button type="submit" disabled={isSending || message.trim().length === 0}>
          {isSending ? 'Sending…' : 'Send message'}
        </button>
      </form>
    </section>
  )
}
