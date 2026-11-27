import type { QueryClient } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { createRootRouteWithContext, Link, Outlet } from '@tanstack/react-router'
import { TanStackRouterDevtools } from '@tanstack/react-router-devtools'

interface RouterContext {
  queryClient: QueryClient
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
})

function RootLayout() {
  return (
    <div className="min-h-svh">
      <header className="border-b">
        <nav className="mx-auto flex max-w-4xl items-center gap-4 p-4 text-sm font-medium">
          <Link
            to="/"
            className="text-muted-foreground hover:text-foreground"
            activeProps={{ className: 'text-foreground' }}
            activeOptions={{ exact: true }}
          >
            Home
          </Link>
          <Link
            to="/users"
            className="text-muted-foreground hover:text-foreground"
            activeProps={{ className: 'text-foreground' }}
          >
            Users
          </Link>
        </nav>
      </header>
      <Outlet />
      {import.meta.env.DEV && import.meta.env.MODE !== 'test' && (
        <>
          <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-left" />
          <TanStackRouterDevtools position="bottom-right" />
        </>
      )}
    </div>
  )
}
