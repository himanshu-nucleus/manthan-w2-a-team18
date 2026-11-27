import { ArrowUUpLeftIcon, CheckIcon, XIcon } from '@phosphor-icons/react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  type ApprovalStep,
  approveClaim,
  claimKeys,
  rejectClaim,
  sendBackClaim,
} from '@/features/claims/api'
import { errorMessage } from '@/lib/api'

type Decision = 'approve' | 'send-back' | 'reject'

const DECISION: Record<
  Decision,
  { title: string; description: string; confirm: string; success: string; required: boolean }
> = {
  approve: {
    title: 'Approve claim',
    description: 'Approve this step. A comment is optional.',
    confirm: 'Approve',
    success: 'Claim approved',
    required: false,
  },
  'send-back': {
    title: 'Send back for clarification',
    description: 'The employee can edit and resubmit. Tell them what to fix.',
    confirm: 'Send back',
    success: 'Claim sent back to the employee',
    required: true,
  },
  reject: {
    title: 'Reject claim',
    description: 'Rejection is final. Explain why.',
    confirm: 'Reject',
    success: 'Claim rejected',
    required: true,
  },
}

export function ReviewActions({ claimId, step }: { claimId: number; step: ApprovalStep }) {
  const queryClient = useQueryClient()
  const [decision, setDecision] = useState<Decision | null>(null)
  const [comment, setComment] = useState('')
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: ({ kind, text }: { kind: Decision; text: string }) => {
      if (kind === 'approve')
        return approveClaim(claimId, { step_id: step.id, ...(text ? { comment: text } : {}) })
      if (kind === 'reject') return rejectClaim(claimId, { step_id: step.id, comment: text })
      return sendBackClaim(claimId, { step_id: step.id, comment: text })
    },
    onSuccess: (_data, { kind }) => {
      toast.success(DECISION[kind].success)
      setDecision(null)
      setComment('')
      void queryClient.invalidateQueries({ queryKey: claimKeys.all })
      void queryClient.invalidateQueries({ queryKey: ['approvals'] })
    },
    onError: (err) => {
      setError(errorMessage(err))
      toast.error(errorMessage(err))
    },
  })

  function open(kind: Decision) {
    setDecision(kind)
    setComment('')
    setError(null)
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!decision) return
    const text = comment.trim()
    if (DECISION[decision].required && !text) {
      setError('A comment is required')
      return
    }
    setError(null)
    mutation.mutate({ kind: decision, text })
  }

  const meta = decision ? DECISION[decision] : null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Your review</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-2">
        <Button onClick={() => open('approve')}>
          <CheckIcon /> Approve
        </Button>
        <Button variant="outline" onClick={() => open('send-back')}>
          <ArrowUUpLeftIcon /> Send back
        </Button>
        <Button variant="destructive" onClick={() => open('reject')}>
          <XIcon /> Reject
        </Button>
      </CardContent>

      <Dialog open={decision !== null} onOpenChange={(next) => !next && setDecision(null)}>
        <DialogContent>
          {meta && (
            <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
              <DialogHeader>
                <DialogTitle>{meta.title}</DialogTitle>
                <DialogDescription>{meta.description}</DialogDescription>
              </DialogHeader>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="review-comment">Comment{meta.required ? '' : ' (optional)'}</Label>
                <Textarea
                  id="review-comment"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  aria-invalid={error ? true : undefined}
                  rows={3}
                />
                {error && (
                  <p role="alert" className="text-xs text-destructive">
                    {error}
                  </p>
                )}
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setDecision(null)}>
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant={decision === 'reject' ? 'destructive' : 'default'}
                  disabled={mutation.isPending}
                >
                  {mutation.isPending ? 'Saving…' : meta.confirm}
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </Card>
  )
}
