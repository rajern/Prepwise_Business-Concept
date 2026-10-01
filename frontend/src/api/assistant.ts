import { apiUrl } from './config'
import { ApiRequestError, apiRequestError } from './errors'
import type { Language } from '../i18n'

export interface ChatMessage { role: 'user' | 'assistant'; content: string }

export interface AssistantResponse {
  reply: string
  model: string
  response_id: string
}
export type AssistantEvent =
  | { type: 'progress'; stage: 'thinking' | 'tools' }
  | { type: 'delta'; text: string }
  | { type: 'reset' }

export async function sendAssistantMessage(
  accessToken: string,
  message: string,
  signal?: AbortSignal,
  language: Language = 'no',
  history: ChatMessage[] = [],
  onEvent?: (event: AssistantEvent) => void,
): Promise<AssistantResponse> {
  const response = await fetch(apiUrl('/api/assistant/messages'), {
    method: 'POST',
    headers: {
      Accept: onEvent ? 'text/event-stream' : 'application/json',
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ message, lang: language, history }),
    signal,
  })

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
      const { value, done } = await reader.read()
      buffer = (buffer + decoder.decode(value, { stream: !done })).replace(/\r\n/g, '\n')
      if (buffer.length > 65536) throw new Error('Assistant event too large')
      let boundary: number
      while ((boundary = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, boundary)
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
          throw new ApiRequestError(Number(event.status) || 503, 'assistant_stream_failed',
            typeof event.detail === 'string' ? event.detail : null, null, [])
        }
        if (event.type === 'delta' && typeof event.text === 'string') onEvent?.({ type: 'delta', text: event.text })
        if (event.type === 'reset') onEvent?.({ type: 'reset' })
        if (event.type === 'progress' && (event.stage === 'thinking' || event.stage === 'tools')) {
          onEvent?.({ type: 'progress', stage: event.stage })
        }
      }
      if (done) throw new Error('Assistant stream ended without a confirmed answer')
    }
  } finally {
    await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}
