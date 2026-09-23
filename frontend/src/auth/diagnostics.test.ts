import { AuthError } from '@azure/msal-browser'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { reportAuthError } from './diagnostics'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('auth diagnostics', () => {
  it('logs identifiers needed for diagnosis without the error object', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    const error = new AuthError(
      'endpoints_resolution_error',
      'correlation-id',
      'details that should not be logged',
      'issuer_validation_failed',
    )

    reportAuthError('login redirect', error)

    expect(consoleError).toHaveBeenCalledWith(
      '[Prepwise auth] login redirect failed: ' +
        '{"correlationId":"correlation-id","errorCode":"endpoints_resolution_error",' +
        '"name":"AuthError","subError":"issuer_validation_failed"}',
    )
  })

  it('does not log arbitrary error messages', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

    reportAuthError('login redirect', new Error('sensitive response data'))

    expect(consoleError).toHaveBeenCalledWith(
      '[Prepwise auth] login redirect failed: {"name":"Error"}',
    )
  })
})
