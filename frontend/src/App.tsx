import { RocketLaunchIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { z } from 'zod'
import { Button } from '@/components/ui/button'

const counterSchema = z.number().int().min(0).max(10)

function App() {
  const [count, setCount] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const increment = () => {
    const result = counterSchema.safeParse(count + 1)
    if (!result.success) {
      setError('Count cannot exceed 10')
      return
    }
    setError(null)
    setCount(result.data)
  }

  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-4 p-6">
      <h1 className="text-3xl font-semibold tracking-tight">manthan-w2-a-team18</h1>
      <p className="text-muted-foreground">
        React + Vite + Tailwind + shadcn (Base UI) + TanStack Query + Zod
      </p>
      <Button onClick={increment}>
        <RocketLaunchIcon weight="bold" />
        Count is {count}
      </Button>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </main>
  )
}

export default App
