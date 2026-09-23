import { AuthError } from '@azure/msal-browser'

export function reportAuthError(operation: string, error: unknown) {
  if (error instanceof AuthError) {
    console.error(
      `[Prepwise auth] ${operation} failed: ${JSON.stringify({
        correlationId: error.correlationId || undefined,
        errorCode: error.errorCode,
        name: error.name,
        subError: error.subError || undefined,
      })}`,
    )
    return
  }

  console.error(
    `[Prepwise auth] ${operation} failed: ${JSON.stringify({
      name: error instanceof Error ? error.name : 'UnknownError',
    })}`,
  )
}
