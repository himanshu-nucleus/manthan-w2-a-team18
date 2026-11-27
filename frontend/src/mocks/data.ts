import { faker } from '@faker-js/faker'
import type { User } from '@/features/users/api'

// Fixed seed so mock data is stable across reloads and test runs.
faker.seed(18)

export function createUser(overrides: Partial<User> = {}): User {
  return {
    id: faker.string.uuid(),
    name: faker.person.fullName(),
    email: faker.internet.email().toLowerCase(),
    avatar: faker.image.avatar(),
    jobTitle: faker.person.jobTitle(),
    ...overrides,
  }
}

export const users: User[] = Array.from({ length: 8 }, () => createUser())
