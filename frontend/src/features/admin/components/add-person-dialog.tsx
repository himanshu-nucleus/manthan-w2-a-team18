import { zodResolver } from '@hookform/resolvers/zod'
import { PlusIcon, WarningCircleIcon } from '@phosphor-icons/react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'
import { ROLE_LABEL } from '@/components/app-shell'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { User } from '@/features/auth/api'
import { errorMessage } from '@/lib/api'
import { adminKeys, createUser } from '../api'

// Limits mirror UserCreate in docs/openapi.json.
const personSchema = z.object({
  full_name: z.string().trim().min(1, 'Enter a full name').max(120, 'At most 120 characters'),
  email: z
    .string()
    .trim()
    .min(1, 'Enter a work email')
    .pipe(z.email('Enter a valid email address')),
  username: z.string().trim().min(1, 'Enter a username').max(64, 'At most 64 characters'),
  role: z.enum(['employee', 'line_manager', 'finance_auditor']),
  password: z
    .string()
    .min(8, 'Password must be at least 8 characters')
    .max(128, 'At most 128 characters'),
  manager_id: z.string(),
})
type PersonValues = z.infer<typeof personSchema>

const NO_MANAGER = 'none'

const ROLE_ITEMS = (['employee', 'line_manager', 'finance_auditor'] as const).map((role) => ({
  value: role,
  label: ROLE_LABEL[role],
}))

const DEFAULTS: PersonValues = {
  full_name: '',
  email: '',
  username: '',
  role: 'employee',
  password: '',
  manager_id: NO_MANAGER,
}

export function AddPersonDialog({ users }: { users: User[] }) {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const form = useForm<PersonValues>({
    resolver: zodResolver(personSchema),
    defaultValues: DEFAULTS,
  })
  const { errors } = form.formState

  const managerItems = [
    { value: NO_MANAGER, label: 'No manager' },
    ...users
      .filter((u) => u.is_active && u.role !== 'employee')
      .map((u) => ({ value: String(u.id), label: `${u.full_name} (${ROLE_LABEL[u.role]})` })),
  ]

  const mutation = useMutation({
    mutationFn: (values: PersonValues) =>
      createUser({
        full_name: values.full_name,
        email: values.email,
        username: values.username,
        role: values.role,
        password: values.password,
        manager_id: values.manager_id === NO_MANAGER ? null : Number(values.manager_id),
      }),
    onSuccess: async (created) => {
      toast.success(`Added ${created.full_name}. They can sign in with ${created.username}.`)
      await queryClient.invalidateQueries({ queryKey: adminKeys.users })
      form.reset(DEFAULTS)
      setOpen(false)
    },
  })

  const pending = mutation.isPending
  const emailField = form.register('email')

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) {
          form.reset(DEFAULTS)
          mutation.reset()
        }
      }}
    >
      <DialogTrigger render={<Button />}>
        <PlusIcon data-icon="inline-start" />
        Add person
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <form
          noValidate
          onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
          className="flex flex-col gap-4"
        >
          <DialogHeader>
            <DialogTitle>Add person</DialogTitle>
            <DialogDescription>
              Create an account. Share the password with them securely.
            </DialogDescription>
          </DialogHeader>

          <FieldGroup className="gap-4">
            <Field data-invalid={!!errors.full_name}>
              <FieldLabel htmlFor="person-name">Full name</FieldLabel>
              <Input
                id="person-name"
                aria-invalid={!!errors.full_name}
                disabled={pending}
                {...form.register('full_name')}
              />
              <FieldError errors={[errors.full_name]} />
            </Field>

            <Field data-invalid={!!errors.email}>
              <FieldLabel htmlFor="person-email">Work email</FieldLabel>
              <Input
                id="person-email"
                type="email"
                aria-invalid={!!errors.email}
                disabled={pending}
                {...emailField}
                onChange={(e) => {
                  void emailField.onChange(e)
                  // Sign-in uses the work email as username: keep them in sync until edited.
                  if (!form.getFieldState('username').isDirty) {
                    form.setValue('username', e.target.value.trim().toLowerCase())
                  }
                }}
              />
              <FieldError errors={[errors.email]} />
            </Field>

            <Field data-invalid={!!errors.username}>
              <FieldLabel htmlFor="person-username">Username</FieldLabel>
              <Input
                id="person-username"
                aria-invalid={!!errors.username}
                disabled={pending}
                {...form.register('username')}
              />
              <FieldDescription>
                People sign in with their work email, so keep this the same as the email.
              </FieldDescription>
              <FieldError errors={[errors.username]} />
            </Field>

            <Field data-invalid={!!errors.role}>
              <FieldLabel htmlFor="person-role">Role</FieldLabel>
              <Controller
                control={form.control}
                name="role"
                render={({ field }) => (
                  <Select
                    items={ROLE_ITEMS}
                    value={field.value}
                    disabled={pending}
                    onValueChange={(v) => v && field.onChange(v)}
                  >
                    <SelectTrigger id="person-role" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {ROLE_ITEMS.map((item) => (
                        <SelectItem key={item.value} value={item.value}>
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
              <FieldError errors={[errors.role]} />
            </Field>

            <Field>
              <FieldLabel htmlFor="person-manager">Manager</FieldLabel>
              <Controller
                control={form.control}
                name="manager_id"
                render={({ field }) => (
                  <Select
                    items={managerItems}
                    value={field.value}
                    disabled={pending}
                    onValueChange={(v) => v && field.onChange(v)}
                  >
                    <SelectTrigger id="person-manager" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {managerItems.map((item) => (
                        <SelectItem key={item.value} value={item.value}>
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
              <FieldDescription>
                Their claims go to this person for first approval.
              </FieldDescription>
            </Field>

            <Field data-invalid={!!errors.password}>
              <FieldLabel htmlFor="person-password">Temporary password</FieldLabel>
              <Input
                id="person-password"
                type="password"
                autoComplete="new-password"
                aria-invalid={!!errors.password}
                disabled={pending}
                {...form.register('password')}
              />
              <FieldError errors={[errors.password]} />
            </Field>
          </FieldGroup>

          {mutation.isError && (
            <Alert variant="destructive">
              <WarningCircleIcon />
              <AlertDescription>{errorMessage(mutation.error)}</AlertDescription>
            </Alert>
          )}

          <DialogFooter>
            <Button type="submit" disabled={pending}>
              {pending ? 'Adding…' : 'Add person'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
