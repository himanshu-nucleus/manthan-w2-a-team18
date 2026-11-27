import { faker } from '@faker-js/faker'
import type { User } from '@/features/auth/api'

// Fixed seed so mock data is stable across reloads and test runs.
faker.seed(18)

let nextId = 1

export function createUser(overrides: Partial<User> = {}): User {
  const firstName = faker.person.firstName()
  const lastName = faker.person.lastName()
  const email = faker.internet.email({ firstName, lastName, provider: 'expenseflow.example' })
  return {
    id: nextId++,
    username: email.toLowerCase(),
    full_name: `${firstName} ${lastName}`,
    email: email.toLowerCase(),
    role: 'employee',
    manager_id: null,
    is_active: true,
    created_at: faker.date.past({ refDate: '2026-11-27T00:00:00Z' }).toISOString(),
    ...overrides,
  }
}

/** Synthetic accounts the mock API accepts. Password for every account: `password`. */
export const MOCK_PASSWORD = 'password'

export const mockUsers: User[] = [
  createUser({ username: 'employee@expenseflow.example', email: 'employee@expenseflow.example' }),
  createUser({
    username: 'manager@expenseflow.example',
    email: 'manager@expenseflow.example',
    role: 'line_manager',
  }),
  createUser({
    username: 'auditor@expenseflow.example',
    email: 'auditor@expenseflow.example',
    role: 'finance_auditor',
  }),
  createUser({
    username: 'admin@expenseflow.example',
    email: 'admin@expenseflow.example',
    role: 'finance_head',
  }),
]
