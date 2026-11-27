import { delay, http, HttpResponse } from 'msw'
import { users } from './data'

export const handlers = [
  http.get('/api/users', async () => {
    await delay()
    return HttpResponse.json(users)
  }),
]
