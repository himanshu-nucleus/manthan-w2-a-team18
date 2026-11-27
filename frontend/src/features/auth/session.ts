import type { QueryClient } from '@tanstack/react-query'
import { meQueryOptions, type Role, type User } from './api'
import { clearToken, getToken } from './token-storage'

/** Landing page per role after sign-in. Dashboards (E1/M1/A0/F0) have no API yet. */
const ROLE_HOME: Record<Role, string> = {
  employee: '/claims',
  line_manager: '/approvals',
  finance_auditor: '/approvals',
  finance_head: '/approvals',
}

export function roleHome(role: Role) {
  return ROLE_HOME[role]
}

/** Accept only same-origin app paths, so `?redirect=` can't send users off-site. */
export function safeRedirect(path: string | undefined) {
  return path && path.startsWith('/') && !path.startsWith('//') ? path : undefined
}

/** The signed-in user, or `null` when there is no valid session. */
export async function loadSession(queryClient: QueryClient): Promise<User | null> {
  if (!getToken()) return null
  try {
    return await queryClient.ensureQueryData(meQueryOptions)
  } catch {
    clearToken()
    queryClient.removeQueries({ queryKey: meQueryOptions.queryKey })
    return null
  }
}

export function signOut(queryClient: QueryClient) {
  clearToken()
  queryClient.clear()
}
