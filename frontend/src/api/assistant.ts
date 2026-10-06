import { apiUrl } from './config'
import { ApiRequestError, apiRequestError } from './errors'
import type { Language } from '../i18n'
import { authenticatedFetch } from '../auth/authenticatedFetch'

export interface ChatMessage { role: 'user' | 'assistant'; content: string }

export interface AssistantResponse {
  reply: string
  model: string
  response_id: string
}
export type AssistantEvent =
  | { type: 'mutation'; mutation_status: 'none' | 'unknown' | 'applied'; request_id?: string }
  | { type: 'progress'; stage: 'thinking' | 'tools' | 'writing'; mutation_status?: 'none' | 'unknown' | 'applied' }
  | { type: 'delta'; text: string }
  | { type: 'reset' }

export async function sendAssistantMessage(
  accessToken: string,
  message: string,
  signal?: AbortSignal,
  language: Language = 'no',
  history: ChatMessage[] = [],
  onEvent?: (event: AssistantEvent) => void,
  idempotencyKey?: string,
): Promise<AssistantResponse> {
  const controller = new AbortController()
  const combined = signal ? AbortSignal.any([signal, controller.signal]) : controller.signal
  const timer = window.setTimeout(() => controller.abort(new DOMException('Assistant request timed out', 'TimeoutError')), 60000)
  try {
    return await abortable(readAssistantResponse(accessToken, message, combined, language, history, onEvent, idempotencyKey), combined)
  } finally { window.clearTimeout(timer) }
}

async function readAssistantResponse(
  accessToken: string, message: string, signal: AbortSignal,
  language: Language, history: ChatMessage[], onEvent?: (event: AssistantEvent) => void, idempotencyKey?: string,
): Promise<AssistantResponse> {
  const response = await authenticatedFetch(apiUrl('/api/assistant/messages'), accessToken, {
    method: 'POST',
    headers: {
      Accept: onEvent ? 'text/event-stream' : 'application/json',
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ message, lang: language, history, ...(idempotencyKey ? { idempotency_key: idempotencyKey } : {}) }),
    signal,
  }, 65000)

  if (!response.ok) {
    throw await apiRequestError(response)
  }

  if (!response.headers?.get?.('Content-Type')?.includes('text/event-stream')) {
    return (await response.json()) as AssistantResponse
  }
  if (!response.body) throw new Error('Missing assistant stream')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { value, done } = await abortable(reader.read(), signal)
      buffer = (buffer + decoder.decode(value, { stream: !done })).replace(/\r\n/g, '\n')
      let boundary: number
      while ((boundary = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, boundary)
        if (frame.length > 65536) throw new Error('Assistant event too large')
        buffer = buffer.slice(boundary + 2)
        const data = frame.split('\n').filter((line) => line.startsWith('data:'))
          .map((line) => line.slice(5).trimStart()).join('\n')
        if (!data) continue
        const event = JSON.parse(data) as Record<string, unknown>
        if (event.type === 'done' && typeof event.reply === 'string' &&
          typeof event.model === 'string' && typeof event.response_id === 'string') {
          return { reply: event.reply, model: event.model, response_id: event.response_id }
        }
        if (event.type === 'error') {
          throw new ApiRequestError(Number(event.status) || 503,
            typeof event.code === 'string' ? event.code : 'assistant_stream_failed',
            typeof event.detail === 'string' ? event.detail : null,
            typeof event.request_id === 'string' ? event.request_id : response.headers?.get?.('X-Request-ID') ?? null,
            [], null,
            event.mutation_status === 'none' || event.mutation_status === 'applied' ? event.mutation_status : 'unknown',
            event.retry_safe === true)
        }
        if (event.type === 'delta' && typeof event.text === 'string') onEvent?.({ type: 'delta', text: event.text })
        if (event.type === 'reset') onEvent?.({ type: 'reset' })
        if (event.type === 'mutation' && (event.mutation_status === 'none' || event.mutation_status === 'unknown' || event.mutation_status === 'applied')) {
          onEvent?.({ type: 'mutation', mutation_status: event.mutation_status, ...(typeof event.request_id === 'string' ? { request_id: event.request_id } : {}) })
        }
        if (event.type === 'progress' && (event.stage === 'thinking' || event.stage === 'tools' || event.stage === 'writing')) {
          onEvent?.({ type: 'progress', stage: event.stage, ...(event.mutation_status === 'unknown' || event.mutation_status === 'applied' ? { mutation_status: event.mutation_status } : {}) })
        }
      }
      if (buffer.length > 65536) throw new Error('Assistant event too large')
      if (done) throw new Error('Assistant stream ended without a confirmed answer')
    }
  } finally {
    void reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}

function abortable<T>(promise: Promise<T>, signal: AbortSignal): Promise<T> {
  if (signal.aborted) return Promise.reject(signal.reason ?? new DOMException('Aborted', 'AbortError'))
  return new Promise<T>((resolve, reject) => {
    const aborted = () => reject(signal.reason ?? new DOMException('Aborted', 'AbortError'))
    signal.addEventListener('abort', aborted, { once: true })
    promise.then(resolve, reject).finally(() => signal.removeEventListener('abort', aborted))
  })
}
