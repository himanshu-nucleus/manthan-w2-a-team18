import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createQueryClient } from '@/lib/query-client'
import { createAppRouter } from '@/router'
import './index.css'

// Mocks run in dev only; set VITE_ENABLE_MOCKS=false to hit a real API.
if (import.meta.env.DEV && import.meta.env.VITE_ENABLE_MOCKS !== 'false') {
  const { worker } = await import('@/mocks/browser')
  await worker.start({ onUnhandledFrame: 'bypass' })
}

const queryClient = createQueryClient()
const router = createAppRouter(queryClient)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
