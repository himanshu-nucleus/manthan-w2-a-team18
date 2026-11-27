import { QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router'
import { render } from '@testing-library/react'
import { createQueryClient } from '@/lib/query-client'
import { createAppRouter } from '@/router'

/** Renders the full app at the given URL with an in-memory router and a fresh query cache. */
export function renderRoute(url: string) {
  const queryClient = createQueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createAppRouter(queryClient, {
    history: createMemoryHistory({ initialEntries: [url] }),
  })
  return {
    router,
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    ),
  }
}
