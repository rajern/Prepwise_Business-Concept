import { describe, expect, it, vi, afterEach } from 'vitest'
import { sendAssistantMessage, type AssistantEvent } from './assistant'
import { ApiRequestError } from './errors'

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })

function streamResponse(events: unknown[], splitBytes = false) {
  const bytes = new TextEncoder().encode(events.map((event) => `data: ${JSON.stringify(event)}\r\n\r\n`).join(''))
  return new Response(new ReadableStream<Uint8Array>({
    start(controller) {
      if (splitBytes) for (const byte of bytes) controller.enqueue(Uint8Array.of(byte))
      else controller.enqueue(bytes)
      controller.close()
    },
  }), { headers: { 'Content-Type': 'text/event-stream' } })
}

describe('assistant stream transport', () => {
  it('preserves mutation/error references and prevents unbounded wait on a stalled stream', async () => {
    vi.useFakeTimers()
    const events: AssistantEvent[] = []
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(streamResponse([
      { type: 'mutation', mutation_status: 'unknown', request_id: 'correlation' },
      { type: 'error', status: 503, code: 'assistant_outcome_unknown', request_id: 'correlation', mutation_status: 'unknown', retry_safe: false },
    ])))
    await expect(sendAssistantMessage('token', 'Add', undefined, 'en', [], (event) => events.push(event), 'key')).rejects.toMatchObject({ code: 'assistant_outcome_unknown', requestId: 'correlation', mutationStatus: 'unknown', retrySafe: false })
    expect(events).toEqual([{ type: 'mutation', mutation_status: 'unknown', request_id: 'correlation' }])
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(new ReadableStream(), { headers: { 'Content-Type': 'text/event-stream' } })))
    const pending = sendAssistantMessage('token', 'Add', undefined, 'en', [], () => undefined)
    const rejected = expect(pending).rejects.toMatchObject({ name: 'TimeoutError' })
    await vi.advanceTimersByTimeAsync(60000)
    await rejected
  })
  it('accepts the compatible JSON recovery endpoint without retrying a message', async () => {
    const reply = { reply: 'Bekreftet', model: 'offline', response_id: 'recovery' }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(reply), {
      headers: { 'Content-Type': 'application/json' },
    }))
    const onEvent = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    expect(await sendAssistantMessage('token', 'Hei', undefined, 'no', [], onEvent)).toEqual(reply)
    expect(onEvent).not.toHaveBeenCalled()
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('parses split UTF-8 and CRLF frames and waits for confirmed done', async () => {
    const events: AssistantEvent[] = []
    const fetchMock = vi.fn().mockResolvedValue(streamResponse([
      { type: 'progress', stage: 'tools' }, { type: 'delta', text: 'Kjøtt' },
      { type: 'reset' }, { type: 'delta', text: 'Måltider' },
      { type: 'done', reply: 'Bekreftet', model: 'offline', response_id: 'id' },
    ], true))
    vi.stubGlobal('fetch', fetchMock)
    const result = await sendAssistantMessage('token', 'Hei', undefined, 'no', [], (event) => events.push(event))
    expect(result.reply).toBe('Bekreftet')
    expect(events).toEqual([
      { type: 'progress', stage: 'tools' }, { type: 'delta', text: 'Kjøtt' },
      { type: 'reset' }, { type: 'delta', text: 'Måltider' },
    ])
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('does not turn a partial stream into success or retry', async () => {
    const fetchMock = vi.fn().mockResolvedValue(streamResponse([{ type: 'delta', text: 'Added' }]))
    vi.stubGlobal('fetch', fetchMock)
    await expect(sendAssistantMessage('token', 'Add', undefined, 'en', [], () => undefined)).rejects.toThrow('without a confirmed answer')
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('surfaces a safe terminal error rather than partial text', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(streamResponse([
      { type: 'delta', text: 'Not confirmed' }, { type: 'error', status: '504', detail: 'Timeout' },
    ])))
    await expect(sendAssistantMessage('token', 'Add', undefined, 'en', [], () => undefined)).rejects.toBeInstanceOf(ApiRequestError)
  })
})
