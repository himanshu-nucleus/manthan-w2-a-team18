import type { QueryClient } from '@tanstack/react-query'
import { createRouter } from '@tanstack/react-router'
import { routeTree } from './routeTree.gen'

type RouterOptions = Omit<
  Parameters<typeof createRouter<typeof routeTree>>[0],
  'routeTree' | 'context'
>

export function createAppRouter(queryClient: QueryClient, options: Partial<RouterOptions> = {}) {
  return createRouter({
    routeTree,
    context: { queryClient },
    defaultPreload: 'intent',
    // Let TanStack Query own data freshness.
    defaultPreloadStaleTime: 0,
    scrollRestoration: true,
    ...options,
  })
}

declare module '@tanstack/react-router' {
  interface Register {
    router: ReturnType<typeof createAppRouter>
  }
}
