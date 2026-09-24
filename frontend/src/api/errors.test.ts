import { describe, expect, it } from 'vitest'

import { ApiRequestError, apiErrorMessage, apiRequestError } from './errors'

describe('API errors', () => {
  it('parses the consistent backend error format', async () => {
    const error = await apiRequestError(
      new Response(
        JSON.stringify({
          code: 'not_found',
          detail: 'Meal not found',
          request_id: 'request-123',
        }),
        { status: 404, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    expect(error).toBeInstanceOf(ApiRequestError)
    expect(error).toMatchObject({
      status: 404,
      code: 'not_found',
      detail: 'Meal not found',
      requestId: 'request-123',
    })
  })

  it('turns validation issues into a clear message', async () => {
    const error = await apiRequestError(
      new Response(
        JSON.stringify({
          code: 'validation_error',
          detail: 'Invalid request data',
          request_id: 'validation-123',
          errors: [
            {
              location: 'body.price_nok',
              message: 'Input should be greater than 0',
              type: 'greater_than',
            },
          ],
        }),
        { status: 422, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    expect(apiErrorMessage(error, 'Save failed.')).toBe(
      'Invalid request data: Input should be greater than 0',
    )
  })

  it('includes the request reference for a server failure', async () => {
    const error = await apiRequestError(
      new Response('not-json', {
        status: 503,
        headers: { 'X-Request-ID': 'server-123' },
      }),
    )

    expect(apiErrorMessage(error, 'Service unavailable.')).toBe(
      'Service unavailable. Reference: server-123.',
    )
  })
})
