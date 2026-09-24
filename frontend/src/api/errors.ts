export interface ApiValidationIssue {
  location: string
  message: string
  type: string
}

export class ApiRequestError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string | null,
    public readonly detail: string | null,
    public readonly requestId: string | null,
    public readonly validationIssues: ApiValidationIssue[],
  ) {
    super(detail ?? `API request failed with status ${status}`)
    this.name = 'ApiRequestError'
  }
}

export async function apiRequestError(response: Response): Promise<ApiRequestError> {
  let code: string | null = null
  let detail: string | null = null
  let requestId: string | null = response.headers?.get?.('X-Request-ID') ?? null
  let validationIssues: ApiValidationIssue[] = []

  try {
    const body = (await response.json()) as Record<string, unknown>
    code = typeof body.code === 'string' ? body.code : null
    detail = typeof body.detail === 'string' ? body.detail : null
    requestId = typeof body.request_id === 'string' ? body.request_id : requestId
    validationIssues = Array.isArray(body.errors)
      ? body.errors.flatMap((candidate) => {
          if (!candidate || typeof candidate !== 'object') {
            return []
          }
          const issue = candidate as Record<string, unknown>
          return typeof issue.location === 'string' &&
            typeof issue.message === 'string' &&
            typeof issue.type === 'string'
            ? [
                {
                  location: issue.location,
                  message: issue.message,
                  type: issue.type,
                },
              ]
            : []
        })
      : []
  } catch {
    // The status and response header still provide a safe fallback.
  }

  return new ApiRequestError(
    response.status,
    code,
    detail,
    requestId,
    validationIssues,
  )
}

export function apiErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof ApiRequestError)) {
    return fallback
  }

  if (error.status === 401) {
    return 'Your session has expired. Sign in again.'
  }
  if (error.status === 403) {
    return 'You do not have permission to perform this action.'
  }

  const validationMessage = error.validationIssues[0]?.message
  const message = validationMessage
    ? `${error.detail ?? 'Invalid request data'}: ${validationMessage}`
    : error.detail ?? fallback

  return error.status >= 500 && error.requestId
    ? `${message} Reference: ${error.requestId}.`
    : message
}
