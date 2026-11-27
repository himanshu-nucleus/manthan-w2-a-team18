import { zodResolver } from '@hookform/resolvers/zod'
import {
  FileArrowUpIcon,
  PaperclipIcon,
  PlusIcon,
  TrashIcon,
  WarningCircleIcon,
} from '@phosphor-icons/react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useRef, useState } from 'react'
import { useFieldArray, useForm, useWatch, type Control } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  CATEGORY_LABEL,
  claimKeys,
  createClaim,
  EXPENSE_CATEGORIES,
  updateClaim,
  uploadAttachment,
  type Attachment,
  type Claim,
  type ClaimWriteInput,
} from '@/features/claims/api'
import { ApiError, errorMessage } from '@/lib/api'
import { formatInr } from '@/lib/format'
import { cn } from '@/lib/utils'

// One page condensing N1–N4 / E3 / E4: title + expense lines, save draft or submit.
// Drafts may be partial (API: every line field optional); submit enforces required fields.

const RECEIPT_THRESHOLD = 500
const MAX_RECEIPT_BYTES = 5 * 1024 * 1024
const RECEIPT_TYPES = ['application/pdf', 'image/png', 'image/jpeg']

function today() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const lineSchema = z.object({
  category: z.union([z.enum(EXPENSE_CATEGORIES), z.literal('')]),
  amount: z
    .string()
    .trim()
    .refine(
      (v) => v === '' || (/^\d+(\.\d{1,2})?$/.test(v) && Number(v) > 0),
      'Enter an amount above 0 (up to 2 decimals)',
    ),
  expense_date: z.string().refine((v) => v === '' || v <= today(), 'Date cannot be in the future'),
  vendor: z.string().trim().max(200, 'At most 200 characters'),
  description: z.string().trim().max(1000, 'At most 1000 characters'),
  city: z.string().trim().max(100, 'At most 100 characters'),
  nights: z
    .string()
    .trim()
    .refine(
      (v) => v === '' || (/^\d+$/.test(v) && Number(v) >= 1 && Number(v) <= 365),
      'Nights must be 1–365',
    ),
  receipt_number: z.string().trim().max(100, 'At most 100 characters'),
  receipt_id: z.number().nullable(),
})

const baseSchema = z.object({
  title: z.string().trim().max(200, 'At most 200 characters'),
  lines: z.array(lineSchema).max(50, 'At most 50 expenses per claim'),
})

type FormValues = z.infer<typeof baseSchema>
type LineValues = FormValues['lines'][number]
type Mode = 'draft' | 'submit'

// Drafts use `baseSchema`; submit adds the API's required-field rules.
const submitSchema = baseSchema.superRefine((v, ctx) => {
  const required = (path: (string | number)[], message: string) =>
    ctx.addIssue({ code: 'custom', path, message })
  if (!v.title) required(['title'], 'Give the claim a title')
  if (v.lines.length === 0) required(['lines'], 'Add at least one expense to submit')
  v.lines.forEach((l, i) => {
    if (!l.category) required(['lines', i, 'category'], 'Choose a category')
    if (!l.amount) required(['lines', i, 'amount'], 'Enter the amount')
    if (!l.expense_date) required(['lines', i, 'expense_date'], 'Enter the date')
    if (!l.vendor) required(['lines', i, 'vendor'], 'Enter the vendor')
    if (Number(l.amount) > RECEIPT_THRESHOLD) {
      const msg = `Receipt number and receipt file are required above ₹${RECEIPT_THRESHOLD}`
      if (!l.receipt_number) required(['lines', i, 'receipt_number'], msg)
      if (l.receipt_id === null) required(['lines', i, 'receipt_id'], msg)
    }
    if (l.category === 'hotel') {
      if (!l.city) required(['lines', i, 'city'], 'City is required for hotel stays')
      if (!l.nights) required(['lines', i, 'nights'], 'Nights are required for hotel stays')
    }
  })
})

const emptyLine = (): LineValues => ({
  category: '',
  amount: '',
  expense_date: '',
  vendor: '',
  description: '',
  city: '',
  nights: '',
  receipt_number: '',
  receipt_id: null,
})

function toFormValues(claim?: Claim): FormValues {
  if (!claim) return { title: '', lines: [emptyLine()] }
  return {
    title: claim.title ?? '',
    lines: claim.lines
      .slice()
      .sort((a, b) => a.position - b.position)
      .map((l) => ({
        category: (EXPENSE_CATEGORIES as readonly string[]).includes(l.category ?? '')
          ? (l.category as LineValues['category'])
          : '',
        amount: l.amount ?? '',
        expense_date: l.expense_date ?? '',
        vendor: l.vendor ?? '',
        description: l.description ?? '',
        city: l.city ?? '',
        nights: l.nights === null ? '' : String(l.nights),
        receipt_number: l.receipt_number ?? '',
        receipt_id: l.receipt_id,
      })),
  }
}

const orNull = (v: string) => (v === '' ? null : v)

/**
 * Drops null fields. Workaround: the API answers 500 (not 422) when an optional,
 * length-limited text field is sent as explicit `null`; omitting it means the same thing.
 */
function withoutNulls<T extends object>(obj: T) {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== null)) as Partial<T>
}

function toWriteInput(values: FormValues, action: Mode): ClaimWriteInput {
  return withoutNulls({
    action,
    title: orNull(values.title),
    currency: 'INR',
    lines: values.lines.map((l) => {
      const hotel = l.category === 'hotel'
      return withoutNulls({
        category: l.category === '' ? null : l.category,
        amount: l.amount === '' ? null : Number(l.amount).toFixed(2),
        expense_date: orNull(l.expense_date),
        vendor: orNull(l.vendor),
        description: orNull(l.description),
        city: hotel ? orNull(l.city) : null,
        nights: hotel && l.nights !== '' ? Number(l.nights) : null,
        receipt_number: orNull(l.receipt_number),
        receipt_id: l.receipt_id,
      })
    }),
  })
}

/** Toast copy for the policy engine result after submit. */
function toastSubmitOutcome(claim: Claim) {
  switch (claim.status) {
    case 'AUTO_APPROVED':
      toast.success('Claim submitted and auto-approved')
      break
    case 'AUTO_REJECTED':
      toast.error('Claim submitted but auto-rejected by policy')
      break
    case 'PENDING_APPROVAL':
      toast.info('Claim submitted — it needs approval')
      break
    default:
      toast.success('Claim submitted')
  }
}

const selectClass =
  'h-9 w-full min-w-0 rounded-lg border border-input bg-card px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 disabled:opacity-50'

interface ClaimFormProps {
  /** Existing claim (edit). Omitted on /claims/new. */
  claim?: Claim
}

export function ClaimForm({ claim }: ClaimFormProps) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  // Mutable holder read by the resolver at validation time (draft vs submit rules).
  const modeRef = useRef<Mode>('draft')
  const [attachments, setAttachments] = useState<Attachment[]>(claim?.attachments ?? [])

  const form = useForm<FormValues>({
    resolver: (values, context, options) =>
      zodResolver(modeRef.current === 'submit' ? submitSchema : baseSchema)(
        values,
        context,
        options,
      ),
    defaultValues: toFormValues(claim),
  })
  const { errors } = form.formState
  const { fields, append, remove } = useFieldArray({ control: form.control, name: 'lines' })

  const mutation = useMutation({
    mutationFn: (body: ClaimWriteInput) =>
      claim ? updateClaim(claim.id, body) : createClaim(body),
    onSuccess: async (saved, body) => {
      queryClient.setQueryData(claimKeys.detail(saved.id), saved)
      await queryClient.invalidateQueries({ queryKey: claimKeys.all })
      if (body.action === 'submit') {
        toastSubmitOutcome(saved)
        void navigate({ to: '/claims/$claimId', params: { claimId: String(saved.id) } })
        return
      }
      toast.success('Draft saved')
      if (!claim) {
        void navigate({ to: '/claims/$claimId/edit', params: { claimId: String(saved.id) } })
      } else {
        form.reset(toFormValues(saved))
        setAttachments(saved.attachments)
      }
    },
    onError: (error) => {
      form.setError('root', { message: errorMessage(error) })
      if (!(error instanceof ApiError)) return
      // Map `lines.N.<name>` / `title` server issues onto the matching inputs.
      for (const issue of error.fields) {
        const m = /^lines\.(\d+)\.(\w+)$/.exec(issue.field)
        if (m && m[2] in emptyLine()) {
          form.setError(`lines.${Number(m[1])}.${m[2] as keyof LineValues}`, {
            message: issue.message,
          })
        } else if (issue.field === 'title') {
          form.setError('title', { message: issue.message })
        }
      }
    },
  })

  const run = (mode: Mode) => {
    modeRef.current = mode
    form.clearErrors('root')
    return form.handleSubmit((values) => mutation.mutate(toWriteInput(values, mode)))()
  }

  const busy = mutation.isPending || form.formState.isSubmitting

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        void run('submit')
      }}
      className="flex flex-col gap-6 pb-24"
    >
      <Card>
        <CardContent>
          <Field data-invalid={!!errors.title}>
            <FieldLabel htmlFor="claim-title">Claim title</FieldLabel>
            <Input
              id="claim-title"
              placeholder="e.g. Client visit — Pune"
              className="h-9 bg-card"
              aria-invalid={!!errors.title}
              disabled={busy}
              {...form.register('title')}
            />
            <FieldError errors={[errors.title]} />
          </Field>
        </CardContent>
      </Card>

      <section className="flex flex-col gap-4" aria-labelledby="expenses-heading">
        <div className="flex items-center justify-between gap-2">
          <h2 id="expenses-heading" className="text-base font-medium">
            Expenses
          </h2>
          <Button
            type="button"
            variant="outline"
            onClick={() => append(emptyLine())}
            disabled={busy || fields.length >= 50}
          >
            <PlusIcon data-icon="inline-start" />
            Add expense
          </Button>
        </div>

        {!claim && (
          <p className="text-sm text-muted-foreground">
            Receipts can be attached once the claim is saved as a draft. Expenses above ₹
            {RECEIPT_THRESHOLD} need a receipt number and file before you can submit.
          </p>
        )}

        {errors.lines?.root?.message || errors.lines?.message ? (
          <p className="text-sm text-destructive" role="alert">
            {errors.lines.root?.message ?? errors.lines.message}
          </p>
        ) : null}

        {fields.length === 0 && (
          <Card>
            <CardContent className="py-6 text-center text-sm text-muted-foreground">
              No expenses yet. Add your first expense.
            </CardContent>
          </Card>
        )}

        {fields.map((field, index) => (
          <ExpenseLineCard
            key={field.id}
            index={index}
            control={form.control}
            form={form}
            claimId={claim?.id}
            disabled={busy}
            attachments={attachments}
            onUploaded={(a) => setAttachments((prev) => [...prev, a])}
            onRemove={() => remove(index)}
          />
        ))}
      </section>

      {errors.root && (
        <Alert variant="destructive">
          <WarningCircleIcon />
          <AlertDescription>{errors.root.message}</AlertDescription>
        </Alert>
      )}

      <div className="sticky bottom-0 z-10 -mx-4 flex flex-wrap items-center justify-between gap-3 border-t bg-background/95 px-4 py-3 backdrop-blur sm:mx-0 sm:rounded-lg sm:border">
        <div className="flex flex-col">
          <span className="text-xs text-muted-foreground">Total</span>
          <RunningTotal control={form.control} />
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            size="lg"
            disabled={busy}
            onClick={() => void run('draft')}
          >
            Save draft
          </Button>
          <Button type="submit" size="lg" disabled={busy}>
            {mutation.isPending && mutation.variables?.action === 'submit'
              ? 'Submitting…'
              : 'Submit claim'}
          </Button>
        </div>
      </div>
    </form>
  )
}

function RunningTotal({ control }: { control: Control<FormValues> }) {
  const lines = useWatch({ control, name: 'lines' })
  const total = (lines ?? []).reduce((acc, l) => {
    const n = Number(l.amount)
    return Number.isFinite(n) ? acc + n : acc
  }, 0)
  return (
    <span className="tabular text-lg font-medium" data-testid="claim-total">
      {formatInr(total)}
    </span>
  )
}

interface ExpenseLineCardProps {
  index: number
  control: Control<FormValues>
  form: ReturnType<typeof useForm<FormValues>>
  claimId?: number
  disabled: boolean
  attachments: Attachment[]
  onUploaded: (a: Attachment) => void
  onRemove: () => void
}

function ExpenseLineCard({
  index,
  control,
  form,
  claimId,
  disabled,
  attachments,
  onUploaded,
  onRemove,
}: ExpenseLineCardProps) {
  const line = useWatch({ control, name: `lines.${index}` })
  const lineErrors = form.formState.errors.lines?.[index]
  const id = (name: string) => `line-${index}-${name}`
  const isHotel = line?.category === 'hotel'
  const needsReceipt = Number(line?.amount) > RECEIPT_THRESHOLD
  const receipt = attachments.find((a) => a.id === line?.receipt_id)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const upload = useMutation({
    mutationFn: (file: File) => uploadAttachment(claimId!, file),
    onSuccess: (attachment) => {
      onUploaded(attachment)
      form.setValue(`lines.${index}.receipt_id`, attachment.id, { shouldDirty: true })
      form.clearErrors(`lines.${index}.receipt_id`)
      setUploadError(null)
      toast.success('Receipt uploaded — save the claim to keep it linked')
    },
    onError: (err) => setUploadError(errorMessage(err)),
  })

  const onFile = (file: File | undefined) => {
    if (!file) return
    if (!RECEIPT_TYPES.includes(file.type)) {
      setUploadError('Receipts must be PDF, PNG or JPEG.')
      return
    }
    if (file.size > MAX_RECEIPT_BYTES) {
      setUploadError('Receipts must be 5 MB or smaller.')
      return
    }
    upload.mutate(file)
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle className="text-sm font-medium">Expense {index + 1}</CardTitle>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label={`Remove expense ${index + 1}`}
          onClick={onRemove}
          disabled={disabled}
        >
          <TrashIcon />
        </Button>
      </CardHeader>
      <CardContent>
        <FieldGroup className="grid gap-4 sm:grid-cols-2">
          <Field data-invalid={!!lineErrors?.category}>
            <FieldLabel htmlFor={id('category')}>Category</FieldLabel>
            <select
              id={id('category')}
              className={selectClass}
              aria-invalid={!!lineErrors?.category}
              disabled={disabled}
              {...form.register(`lines.${index}.category`)}
            >
              <option value="">Choose…</option>
              {EXPENSE_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {CATEGORY_LABEL[c]}
                </option>
              ))}
            </select>
            <FieldError errors={[lineErrors?.category]} />
          </Field>

          <Field data-invalid={!!lineErrors?.amount}>
            <FieldLabel htmlFor={id('amount')}>Amount (₹)</FieldLabel>
            <Input
              id={id('amount')}
              inputMode="decimal"
              placeholder="0.00"
              className="tabular h-9 bg-card"
              aria-invalid={!!lineErrors?.amount}
              disabled={disabled}
              {...form.register(`lines.${index}.amount`)}
            />
            <FieldError errors={[lineErrors?.amount]} />
          </Field>

          <Field data-invalid={!!lineErrors?.expense_date}>
            <FieldLabel htmlFor={id('date')}>Expense date</FieldLabel>
            <Input
              id={id('date')}
              type="date"
              max={today()}
              className="h-9 bg-card"
              aria-invalid={!!lineErrors?.expense_date}
              disabled={disabled}
              {...form.register(`lines.${index}.expense_date`)}
            />
            <FieldError errors={[lineErrors?.expense_date]} />
          </Field>

          <Field data-invalid={!!lineErrors?.vendor}>
            <FieldLabel htmlFor={id('vendor')}>Vendor</FieldLabel>
            <Input
              id={id('vendor')}
              className="h-9 bg-card"
              aria-invalid={!!lineErrors?.vendor}
              disabled={disabled}
              {...form.register(`lines.${index}.vendor`)}
            />
            <FieldError errors={[lineErrors?.vendor]} />
          </Field>

          {isHotel && (
            <>
              <Field data-invalid={!!lineErrors?.city}>
                <FieldLabel htmlFor={id('city')}>City</FieldLabel>
                <Input
                  id={id('city')}
                  className="h-9 bg-card"
                  aria-invalid={!!lineErrors?.city}
                  disabled={disabled}
                  {...form.register(`lines.${index}.city`)}
                />
                <FieldError errors={[lineErrors?.city]} />
              </Field>
              <Field data-invalid={!!lineErrors?.nights}>
                <FieldLabel htmlFor={id('nights')}>Nights</FieldLabel>
                <Input
                  id={id('nights')}
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={365}
                  className="h-9 bg-card"
                  aria-invalid={!!lineErrors?.nights}
                  disabled={disabled}
                  {...form.register(`lines.${index}.nights`)}
                />
                <FieldError errors={[lineErrors?.nights]} />
              </Field>
            </>
          )}

          <Field data-invalid={!!lineErrors?.description} className="sm:col-span-2">
            <FieldLabel htmlFor={id('description')}>Description (optional)</FieldLabel>
            <Textarea
              id={id('description')}
              rows={2}
              className="bg-card"
              aria-invalid={!!lineErrors?.description}
              disabled={disabled}
              {...form.register(`lines.${index}.description`)}
            />
            <FieldError errors={[lineErrors?.description]} />
          </Field>

          <Field data-invalid={!!lineErrors?.receipt_number}>
            <FieldLabel htmlFor={id('receipt-number')}>Receipt number</FieldLabel>
            <Input
              id={id('receipt-number')}
              className="h-9 bg-card"
              aria-invalid={!!lineErrors?.receipt_number}
              disabled={disabled}
              {...form.register(`lines.${index}.receipt_number`)}
            />
            {needsReceipt && (
              <FieldDescription>Receipt required above ₹{RECEIPT_THRESHOLD}.</FieldDescription>
            )}
            <FieldError errors={[lineErrors?.receipt_number]} />
          </Field>

          <Field data-invalid={!!uploadError || !!lineErrors?.receipt_id}>
            <FieldLabel htmlFor={id('receipt-file')}>Receipt file</FieldLabel>
            {claimId ? (
              <>
                <label
                  htmlFor={id('receipt-file')}
                  className={cn(
                    'flex h-9 cursor-pointer items-center gap-2 rounded-lg border border-dashed border-input bg-card px-2.5 text-sm hover:bg-muted',
                    (disabled || upload.isPending) && 'pointer-events-none opacity-50',
                  )}
                >
                  {receipt ? (
                    <PaperclipIcon className="size-4 shrink-0" />
                  ) : (
                    <FileArrowUpIcon className="size-4 shrink-0" />
                  )}
                  <span className="truncate">
                    {upload.isPending
                      ? 'Uploading…'
                      : receipt
                        ? receipt.original_name
                        : line?.receipt_id
                          ? `Receipt #${line.receipt_id}`
                          : 'Upload PDF, PNG or JPEG'}
                  </span>
                </label>
                <input
                  id={id('receipt-file')}
                  type="file"
                  accept="application/pdf,image/png,image/jpeg"
                  capture="environment"
                  className="sr-only"
                  disabled={disabled || upload.isPending}
                  onChange={(e) => {
                    onFile(e.target.files?.[0])
                    e.target.value = ''
                  }}
                />
              </>
            ) : (
              <FieldDescription>Save as draft first to attach a receipt.</FieldDescription>
            )}
            {uploadError ? (
              <FieldError>{uploadError}</FieldError>
            ) : (
              <FieldError errors={[lineErrors?.receipt_id]} />
            )}
          </Field>
        </FieldGroup>
      </CardContent>
    </Card>
  )
}
