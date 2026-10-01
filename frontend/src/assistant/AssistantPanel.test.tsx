import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AssistantPanel } from './AssistantPanel'

afterEach(() => {
  cleanup()
  sessionStorage.clear()
  vi.unstubAllGlobals()
})

describe('AssistantPanel', () => {
  it('shows streamed text as a draft, stores only confirmation and refreshes the cart', async () => {
    let producer!: ReadableStreamDefaultController<Uint8Array>
    const body = new ReadableStream<Uint8Array>({ start(controller) { producer = controller } })
    const refresh = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, { headers: { 'Content-Type': 'text/event-stream' } })))
    render(<AssistantPanel accessToken="token" userId="stream-user" onStateChange={refresh} />)
    fireEvent.click(screen.getByRole('button', { name: 'Open chat' }))
    fireEvent.change(screen.getByLabelText('Message'), { target: { value: 'Add a meal' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
    const send = (event: unknown) => producer.enqueue(new TextEncoder().encode(`data: ${JSON.stringify(event)}\n\n`))
    await act(async () => send({ type: 'delta', text: 'Possible result' }))
    expect(await screen.findByText('Possible result')).toBeInTheDocument()
    expect(screen.getByText('Draft — checking before confirmation')).toBeInTheDocument()
    expect(sessionStorage.getItem('prepwise-chat')).not.toContain('Possible result')
    await act(async () => send({ type: 'reset' }))
    await waitFor(() => expect(screen.queryByText('Possible result')).not.toBeInTheDocument())
    await act(async () => { send({ type: 'done', reply: 'Verified cart', model: 'offline', response_id: 'id' }); producer.close() })
    expect(await screen.findByText('Verified cart')).toBeInTheDocument()
    await waitFor(() => expect(refresh).toHaveBeenCalledOnce())
    expect(sessionStorage.getItem('prepwise-chat')).toContain('Verified cart')
    expect(screen.queryByText('Draft — checking before confirmation')).not.toBeInTheDocument()
  })

  it('withdraws failed drafts and does not retry a possibly executed write', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('data: {"type":"delta","text":"Unverified success"}\n\ndata: {"type":"error","status":"503"}\n\n'))
        controller.close()
      },
    }), { headers: { 'Content-Type': 'text/event-stream' } }))
    vi.stubGlobal('fetch', fetchMock)
    const refresh = vi.fn().mockResolvedValue(undefined)
    render(<AssistantPanel accessToken="token" userId="stream-user" onStateChange={refresh} />)
    fireEvent.click(screen.getByRole('button', { name: 'Open chat' }))
    fireEvent.change(screen.getByLabelText('Message'), { target: { value: 'Add a meal' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
    await screen.findByRole('alert')
    expect(screen.queryByText('Unverified success')).not.toBeInTheDocument()
    expect(sessionStorage.getItem('prepwise-chat')).not.toContain('Unverified success')
    await waitFor(() => expect(refresh).toHaveBeenCalledOnce())
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('describes both live data and service guidance capabilities', () => {
    render(<AssistantPanel accessToken="customer-token" />)
    fireEvent.click(screen.getByRole('button', { name: 'Open chat' }))

    expect(
      screen.getByText(/Ask about available meals, your cart and orders/),
    ).toHaveTextContent('storage, reheating, allergens')
  })

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
    fireEvent.click(screen.getByRole('button', { name: 'Open chat' }))

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
        body: JSON.stringify({ message: 'What can you do?', lang: 'en', history: [] }),
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
    fireEvent.click(screen.getByRole('button', { name: 'Open chat' }))

    fireEvent.change(screen.getByLabelText('Message'), {
      target: { value: 'Hello' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The AI assistant is unavailable right now. Please try again.',
    )
  })

  it('keeps the current tab transcript and sends bounded conversational history', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ reply: 'Here are the available meals.' }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const first = render(<AssistantPanel accessToken="customer-token" userId="customer-1" />)
    fireEvent.click(screen.getByRole('button', { name: 'Open chat' }))
    fireEvent.change(screen.getByLabelText('Message'), { target: { value: 'Show the menu' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
    await screen.findByText('Here are the available meals.')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled())
    first.unmount()

    render(<AssistantPanel accessToken="customer-token" userId="customer-1" />)
    fireEvent.click(screen.getByRole('button', { name: 'Open chat' }))
    expect(screen.getByText('Show the menu')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Message'), { target: { value: 'Which have fish?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    const body = JSON.parse(fetchMock.mock.calls[1][1].body as string)
    expect(body.history).toEqual([
      { role: 'user', content: 'Show the menu' },
      { role: 'assistant', content: 'Here are the available meals.' },
    ])
  })

  it('honors quota Retry-After without immediately retrying', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      headers: { get: (name: string) => name === 'Retry-After' ? '120' : null },
      json: async () => ({ code: 'rate_limit_exceeded' }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const refresh = vi.fn().mockResolvedValue(undefined)
    render(<AssistantPanel accessToken="customer-token" onStateChange={refresh} />)
    fireEvent.click(screen.getByRole('button', { name: 'Open chat' }))
    fireEvent.change(screen.getByLabelText('Message'), { target: { value: 'Show the menu' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('You have reached the chat limit')
    await waitFor(() => expect(refresh).toHaveBeenCalledOnce())
    expect(screen.getByLabelText('Message')).toHaveValue('Show the menu')
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled()
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('clears stored history on logout and prevents signed-out use', () => {
    sessionStorage.setItem('prepwise-chat', JSON.stringify({ userId: 'customer-1', messages: [{ role: 'assistant', content: 'Private order details' }] }))
    render(<AssistantPanel accessToken={null} />)
    fireEvent.click(screen.getByRole('button', { name: 'Open chat' }))
    expect(screen.getByText('Signed-in customers')).toBeInTheDocument()
    expect(screen.queryByLabelText('Message')).not.toBeInTheDocument()
    expect(screen.queryByText('Private order details')).not.toBeInTheDocument()
    expect(sessionStorage.getItem('prepwise-chat')).toBeNull()
  })

  it('refreshes authoritative state when the last assistant call fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 504, json: async () => ({}) }))
    const refresh = vi.fn().mockResolvedValue(undefined)
    render(<AssistantPanel accessToken="customer-token" onStateChange={refresh} />)
    fireEvent.click(screen.getByRole('button', { name: 'Open chat' }))
    fireEvent.change(screen.getByLabelText('Message'), { target: { value: 'Add one meal' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
    await screen.findByRole('alert')
    await waitFor(() => expect(refresh).toHaveBeenCalledOnce())
    expect(screen.getByRole('log')).not.toHaveTextContent('Add one meal')
    expect(screen.getByLabelText('Message')).toHaveValue('Add one meal')
  })
})
