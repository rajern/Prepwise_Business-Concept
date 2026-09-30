import { apiUrl } from './config'
import { apiRequestError } from './errors'
import type { Language } from '../i18n'

export interface ChatMessage { role: 'user' | 'assistant'; content: string }

export interface AssistantResponse {
  reply: string
  model: string
  response_id: string
}

export async function sendAssistantMessage(
  accessToken: string,
  message: string,
  signal?: AbortSignal,
  language: Language = 'no',
  history: ChatMessage[] = [],
): Promise<AssistantResponse> {
  const response = await fetch(apiUrl('/api/assistant/messages'), {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ message, lang: language, history }),
    signal,
  })

  if (!response.ok) {
    throw await apiRequestError(response)
  }

  return (await response.json()) as AssistantResponse
}
