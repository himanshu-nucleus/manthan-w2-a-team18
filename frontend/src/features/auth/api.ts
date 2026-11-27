import { queryOptions } from '@tanstack/react-query'
import { z } from 'zod'
import { apiRequest } from '@/lib/api'

export const roleSchema = z.enum(['employee', 'line_manager', 'finance_auditor', 'finance_head'])
export type Role = z.infer<typeof roleSchema>

/** `UserOut` in docs/openapi.json. */
export const userSchema = z.object({
  id: z.number().int(),
  username: z.string(),
  full_name: z.string(),
  email: z.string().nullable(),
  role: roleSchema,
  manager_id: z.number().int().nullable(),
  is_active: z.boolean(),
  created_at: z.string(),
})
export type User = z.infer<typeof userSchema>

/** `LoginResponse` in docs/openapi.json. */
export const loginResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.literal('bearer'),
  expires_in: z.number().int(),
  user: userSchema,
})
export type LoginResponse = z.infer<typeof loginResponseSchema>

/** `LoginRequest` in docs/openapi.json. */
export interface LoginRequest {
  username: string
  password: string
}

export function login(body: LoginRequest) {
  return apiRequest('/auth/login', { method: 'POST', body, schema: loginResponseSchema })
}

export function fetchMe() {
  return apiRequest('/auth/me', { schema: userSchema })
}

export const meQueryOptions = queryOptions({
  queryKey: ['auth', 'me'],
  queryFn: fetchMe,
  staleTime: 5 * 60 * 1000,
  retry: false,
})
