import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AssistantPanel } from './AssistantPanel'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('AssistantPanel', () => {
  it('sends an authenticated message and displays the reply', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        reply: 'I can help with Prepwise.',
        model: 'gpt-5.6-terra',
        response_id: 'resp_123',
      }),
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<AssistantPanel accessToken="customer-token" />)

    fireEvent.change(screen.getByLabelText('Message'), {
      target: { value: 'What can you do?' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))

    expect(await screen.findByText('I can help with Prepwise.')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/assistant/messages',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Authorization: 'Bearer customer-token',
        }),
        body: JSON.stringify({ message: 'What can you do?' }),
      }),
    )
  })

  it('shows a safe API failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 504,
        headers: { get: () => 'request-123' },
        json: async () => ({
          code: 'gateway_timeout',
          detail: 'The AI assistant timed out. Please try again.',
          request_id: 'request-123',
        }),
      }),
    )
    render(<AssistantPanel accessToken="customer-token" />)

    fireEvent.change(screen.getByLabelText('Message'), {
      target: { value: 'Hello' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The AI assistant timed out. Please try again. Reference: request-123.',
    )
  })
})
