import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { addComment, claimKeys, commentsQuery } from '@/features/claims/api'
import { errorMessage } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import { personLabel } from './utils'

export function CommentsPanel({ claimId, userId }: { claimId: number; userId: number }) {
  const queryClient = useQueryClient()
  const comments = useQuery(commentsQuery(claimId))
  const [body, setBody] = useState('')
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (text: string) => addComment(claimId, text),
    onSuccess: async () => {
      setBody('')
      await queryClient.invalidateQueries({ queryKey: claimKeys.comments(claimId) })
      void queryClient.invalidateQueries({ queryKey: claimKeys.audit(claimId) })
    },
    onError: (err) => toast.error(errorMessage(err)),
  })

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    const text = body.trim()
    if (!text) {
      setError('Write a comment first')
      return
    }
    setError(null)
    mutation.mutate(text)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Comments</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {comments.isPending ? (
          <Skeleton className="h-16 w-full" />
        ) : comments.isError ? (
          <p className="text-sm text-muted-foreground">Couldn't load comments.</p>
        ) : comments.data.length === 0 ? (
          <p className="text-sm text-muted-foreground">No comments yet.</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {comments.data.map((c) => (
              <li key={c.id} className="flex flex-col gap-0.5">
                <span className="text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">
                    {personLabel(c.author_id, userId)}
                  </span>{' '}
                  · {formatDateTime(c.created_at)}
                </span>
                <p className="text-sm whitespace-pre-wrap">{c.body}</p>
              </li>
            ))}
          </ul>
        )}
        <form onSubmit={onSubmit} className="flex flex-col gap-2" noValidate>
          <Textarea
            aria-label="Add a comment"
            placeholder="Add a comment"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            aria-invalid={error ? true : undefined}
            rows={2}
          />
          {error && <p className="text-xs text-destructive">{error}</p>}
          <Button type="submit" size="sm" className="self-end" disabled={mutation.isPending}>
            {mutation.isPending ? 'Posting…' : 'Post comment'}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
