import { apiUrl } from './config'
import { apiRequestError } from './errors'

export interface AssistantResponse {
  reply: string
  model: string
  response_id: string
}

export async function sendAssistantMessage(
  accessToken: string,
  message: string,
  signal?: AbortSignal,
): Promise<AssistantResponse> {
  const response = await fetch(apiUrl('/api/assistant/messages'), {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ message }),
    signal,
  })

  if (!response.ok) {
    throw await apiRequestError(response)
  }

  return (await response.json()) as AssistantResponse
}
