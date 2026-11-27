import { zodResolver } from '@hookform/resolvers/zod'
import { WarningCircleIcon } from '@phosphor-icons/react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { ApiError } from '@/lib/api'
import { login, meQueryOptions, type User } from '../api'
import { setToken } from '../token-storage'

// Team decision: the form asks for a work email and sends it as the API's `username`.
// Limits mirror LoginRequest in docs/openapi.json (username ≤ 64, password ≤ 128).
const loginFormSchema = z.object({
  email: z
    .string()
    .trim()
    .min(1, 'Enter your work email')
    .max(64, 'Email must be at most 64 characters')
    .pipe(z.email('Enter a valid email address')),
  password: z
    .string()
    .min(1, 'Enter your password')
    .max(128, 'Password must be at most 128 characters'),
})

type LoginFormValues = z.infer<typeof loginFormSchema>

interface LoginFormProps {
  onSuccess: (user: User) => void
}

export function LoginForm({ onSuccess }: LoginFormProps) {
  const queryClient = useQueryClient()
  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginFormSchema),
    defaultValues: { email: '', password: '' },
  })
  const { errors } = form.formState

  const mutation = useMutation({
    mutationFn: (values: LoginFormValues) =>
      login({ username: values.email, password: values.password }),
    onSuccess: ({ access_token, user }) => {
      setToken(access_token)
      queryClient.setQueryData(meQueryOptions.queryKey, user)
      onSuccess(user)
    },
    onError: (error) => {
      form.setError('root', {
        message:
          error instanceof ApiError && error.status === 401
            ? 'Email or password is incorrect.'
            : "We couldn't sign you in. Check your connection and try again.",
      })
      // Keep the email, clear the password (L1 spec).
      form.resetField('password')
      form.setFocus('password')
    },
  })

  const onSubmit = form.handleSubmit((values) => mutation.mutate(values))
  const isPending = mutation.isPending

  return (
    <form noValidate onSubmit={onSubmit} className="flex w-full max-w-[440px] flex-col gap-6">
      <h1 className="text-gradient-brand w-fit text-[32px]/10 font-medium tracking-tight">
        Sign in to your account
      </h1>

      <FieldGroup className="gap-5">
        <Field data-invalid={!!errors.email}>
          <FieldLabel htmlFor="email">Work email</FieldLabel>
          <Input
            id="email"
            type="email"
            autoComplete="username"
            placeholder="name@company.com"
            className="h-9 bg-card"
            aria-invalid={!!errors.email}
            disabled={isPending}
            {...form.register('email')}
          />
          <FieldError errors={[errors.email]} />
        </Field>

        <Field data-invalid={!!errors.password}>
          <FieldLabel htmlFor="password">Password</FieldLabel>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            className="h-9 bg-card"
            aria-invalid={!!errors.password}
            disabled={isPending}
            {...form.register('password')}
          />
          <FieldError errors={[errors.password]} />
        </Field>
      </FieldGroup>

      {errors.root && (
        <Alert variant="destructive">
          <WarningCircleIcon />
          <AlertDescription>{errors.root.message}</AlertDescription>
        </Alert>
      )}

      <Button type="submit" size="lg" className="w-full" disabled={isPending}>
        {isPending ? 'Signing in…' : 'Sign in'}
      </Button>
    </form>
  )
}
