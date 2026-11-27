import { zodResolver } from '@hookform/resolvers/zod'
import { WarningCircleIcon } from '@phosphor-icons/react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { approvalKeys, createDelegation } from '@/features/approvals/api'
import { errorMessage } from '@/lib/api'
import { formatDate } from '@/lib/format'
import { todayIso } from './dates'

const delegationFormSchema = z
  .object({
    delegateId: z
      .string()
      .trim()
      .min(1, 'Enter the user ID of your delegate')
      .regex(/^\d+$/, 'User ID must be a whole number'),
    fromDate: z.string().min(1, 'Pick a start date'),
    toDate: z.string().min(1, 'Pick an end date'),
    reason: z.string().trim().max(500, 'Reason must be at most 500 characters'),
  })
  .refine((v) => !v.fromDate || v.fromDate >= todayIso(), {
    path: ['fromDate'],
    message: 'Start date cannot be in the past',
  })
  .refine((v) => !v.fromDate || !v.toDate || v.toDate >= v.fromDate, {
    path: ['toDate'],
    message: 'End date must be on or after the start date',
  })

type DelegationFormValues = z.infer<typeof delegationFormSchema>

export function DelegationForm({ currentUserId }: { currentUserId: number }) {
  const queryClient = useQueryClient()
  const form = useForm<DelegationFormValues>({
    resolver: zodResolver(delegationFormSchema),
    defaultValues: { delegateId: '', fromDate: todayIso(), toDate: '', reason: '' },
  })
  const { errors } = form.formState

  const mutation = useMutation({
    mutationFn: (values: DelegationFormValues) =>
      createDelegation({
        delegate_id: Number(values.delegateId),
        from_date: values.fromDate,
        to_date: values.toDate,
        reason: values.reason || null,
      }),
    onSuccess: (d) => {
      toast.success(
        `Approvals delegated to User #${d.delegate_id} from ${formatDate(d.from_date)} to ${formatDate(d.to_date)}`,
      )
      form.reset({ delegateId: '', fromDate: todayIso(), toDate: '', reason: '' })
      void queryClient.invalidateQueries({ queryKey: approvalKeys.delegations })
      void queryClient.invalidateQueries({ queryKey: ['approvals'] })
    },
    onError: (err) => form.setError('root', { message: errorMessage(err) }),
  })

  const onSubmit = form.handleSubmit((values) => {
    if (Number(values.delegateId) === currentUserId) {
      form.setError('delegateId', { message: 'You cannot delegate to yourself' })
      return
    }
    mutation.mutate(values)
  })
  const isPending = mutation.isPending

  return (
    <form noValidate onSubmit={onSubmit} className="flex flex-col gap-5">
      <FieldGroup className="gap-4">
        <Field data-invalid={!!errors.delegateId}>
          <FieldLabel htmlFor="delegate-id">Delegate user ID</FieldLabel>
          <Input
            id="delegate-id"
            inputMode="numeric"
            placeholder="e.g. 4"
            className="bg-card"
            aria-invalid={!!errors.delegateId}
            disabled={isPending}
            {...form.register('delegateId')}
          />
          <FieldDescription>Must have the same or a higher role than you.</FieldDescription>
          <FieldError errors={[errors.delegateId]} />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field data-invalid={!!errors.fromDate}>
            <FieldLabel htmlFor="from-date">From</FieldLabel>
            <Input
              id="from-date"
              type="date"
              min={todayIso()}
              className="bg-card"
              aria-invalid={!!errors.fromDate}
              disabled={isPending}
              {...form.register('fromDate')}
            />
            <FieldError errors={[errors.fromDate]} />
          </Field>
          <Field data-invalid={!!errors.toDate}>
            <FieldLabel htmlFor="to-date">To</FieldLabel>
            <Input
              id="to-date"
              type="date"
              min={todayIso()}
              className="bg-card"
              aria-invalid={!!errors.toDate}
              disabled={isPending}
              {...form.register('toDate')}
            />
            <FieldError errors={[errors.toDate]} />
          </Field>
        </div>
        <Field data-invalid={!!errors.reason}>
          <FieldLabel htmlFor="reason">Reason (optional)</FieldLabel>
          <Textarea
            id="reason"
            rows={3}
            placeholder="On leave"
            className="bg-card"
            aria-invalid={!!errors.reason}
            disabled={isPending}
            {...form.register('reason')}
          />
          <FieldError errors={[errors.reason]} />
        </Field>
      </FieldGroup>

      {errors.root && (
        <Alert variant="destructive">
          <WarningCircleIcon />
          <AlertDescription>{errors.root.message}</AlertDescription>
        </Alert>
      )}

      <Button type="submit" className="w-fit" disabled={isPending}>
        {isPending ? 'Saving…' : 'Delegate approvals'}
      </Button>
    </form>
  )
}
