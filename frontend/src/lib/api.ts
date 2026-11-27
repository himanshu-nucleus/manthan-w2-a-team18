import { z } from 'zod'
import { clearToken, getToken } from '@/features/auth/token-storage'

/** Error envelope every backend failure uses: `{ "error": { "code", "message" } }`. */
const errorEnvelopeSchema = z.object({
  error: z.object({ code: z.string(), message: z.string() }),
})

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

interface ApiRequest<T> {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  /** JSON-serialisable body, or `FormData` for multipart uploads. */
  body?: unknown
  schema: z.ZodType<T>
}

async function send(path: string, method: string, body: unknown) {
  const token = getToken()
  const headers = new Headers({ Accept: 'application/json' })
  const isForm = body instanceof FormData
  if (body !== undefined && !isForm) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const res = await fetch(`/api/v1${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
  })

  if (!res.ok) {
    const payload: unknown = await res.json().catch(() => null)
    // A stored token the server rejects is expired or forged: drop it.
    if (res.status === 401 && token) clearToken()
    const envelope = errorEnvelopeSchema.safeParse(payload)
    throw envelope.success
      ? new ApiError(res.status, envelope.data.error.code, envelope.data.error.message)
      : new ApiError(res.status, 'http_error', `Request failed with status ${res.status}`)
  }
  return res
}

/**
 * Calls the ExpenseFlow API under `/api/v1`, attaching the bearer token when one is stored,
 * and validates the response with `schema`. Throws `ApiError` for non-2xx responses.
 */
export async function apiRequest<T>(path: string, { method = 'GET', body, schema }: ApiRequest<T>) {
  const res = await send(path, method, body)
  if (res.status === 204) return schema.parse(undefined)
  return schema.parse(await res.json())
}

/** Downloads a protected file (e.g. a receipt) as a Blob, with the bearer token attached. */
export async function apiBlob(path: string) {
  const res = await send(path, 'GET', undefined)
  return res.blob()
}

/** Human-readable message for any error thrown by the API layer. */
export function errorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message
  return 'Something went wrong. Check your connection and try again.'
}
