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
  body?: unknown
  schema: z.ZodType<T>
}

/**
 * Calls the ExpenseFlow API under `/api/v1`, attaching the bearer token when one is stored,
 * and validates the response with `schema`. Throws `ApiError` for non-2xx responses.
 */
export async function apiRequest<T>(path: string, { method = 'GET', body, schema }: ApiRequest<T>) {
  const token = getToken()
  const headers = new Headers({ Accept: 'application/json' })
  if (body !== undefined) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const res = await fetch(`/api/v1${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const payload: unknown = await res.json().catch(() => null)

  if (!res.ok) {
    // A stored token the server rejects is expired or forged: drop it.
    if (res.status === 401 && token) clearToken()
    const envelope = errorEnvelopeSchema.safeParse(payload)
    throw envelope.success
      ? new ApiError(res.status, envelope.data.error.code, envelope.data.error.message)
      : new ApiError(res.status, 'http_error', `Request failed with status ${res.status}`)
  }

  return schema.parse(payload)
}
