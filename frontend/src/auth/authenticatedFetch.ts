import { ApiRequestError } from '../api/errors'

type TokenResolver = () => Promise<string>
let session: { token: string; resolve: TokenResolver } | null = null
const retiredTokens = new Set<string>()

/** Bind silent renewal to this account. An in-flight acquisition cannot cross logout. */
export function bindApiToken(token: string, resolve: TokenResolver): () => void {
  const binding = { token, resolve }
  session = binding
  retiredTokens.delete(token)
  return () => {
    if (session === binding) { session = null; retiredTokens.add(token) }
    else if (session?.token !== token) retiredTokens.add(token)
  }
}

export async function authenticatedFetch(url: string, token: string, init: RequestInit = {}, timeoutMs = 20000): Promise<Response> {
  const timeout = AbortSignal.timeout(timeoutMs)
  const signal = init.signal ? AbortSignal.any([init.signal, timeout]) : timeout
  if (retiredTokens.has(token)) throw expiredSession()
  const binding = session?.token === token ? session : null
  let currentToken = token
  if (binding) {
    try { currentToken = await withAbort(binding.resolve(), signal) } catch (reason) {
      if (signal.aborted) throw signal.reason
      if (reason instanceof DOMException && reason.name === 'AbortError') throw reason
      throw expiredSession()
    }
    if (session !== binding || retiredTokens.has(token)) throw expiredSession()
  }
  if (signal.aborted) throw signal.reason
  const headers: Record<string, string> = init.headers instanceof Headers || Array.isArray(init.headers)
    ? Object.fromEntries(new Headers(init.headers).entries()) : { ...init.headers }
  for (const key of Object.keys(headers)) if (key.toLowerCase() === 'authorization') delete headers[key]
  headers.Authorization = `Bearer ${currentToken}`
  // Never retry here: a failed mutation may already have committed.
  return withAbort(fetch(url, { ...init, signal, headers }), signal)
}

function expiredSession() { return new ApiRequestError(401, 'session_expired', null, null, []) }

function withAbort<T>(promise: Promise<T>, signal: AbortSignal): Promise<T> {
  if (signal.aborted) return Promise.reject(signal.reason)
  return new Promise<T>((resolve, reject) => {
    const aborted = () => reject(signal.reason)
    signal.addEventListener('abort', aborted, { once: true })
    promise.then(resolve, reject).finally(() => signal.removeEventListener('abort', aborted))
  })
}
