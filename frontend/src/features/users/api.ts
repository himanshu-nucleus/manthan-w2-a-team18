import { queryOptions } from '@tanstack/react-query'
import { z } from 'zod'

export const userSchema = z.object({
  id: z.uuid(),
  name: z.string(),
  email: z.email(),
  avatar: z.url(),
  jobTitle: z.string(),
})

export type User = z.infer<typeof userSchema>

export async function fetchUsers(): Promise<User[]> {
  const res = await fetch('/api/users')
  if (!res.ok) throw new Error(`Failed to fetch users: ${res.status}`)
  return z.array(userSchema).parse(await res.json())
}

export const usersQueryOptions = queryOptions({
  queryKey: ['users'],
  queryFn: fetchUsers,
})
