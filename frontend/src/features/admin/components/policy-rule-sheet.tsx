import { WarningCircleIcon } from '@phosphor-icons/react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from 'sonner'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import { errorMessage } from '@/lib/api'
import { type PolicyRule, type PolicyRuleUpdate, updatePolicyRule } from '../api'
import { paramLabel } from './param-label'

type Outcome = 'ROUTE_FOR_APPROVAL' | 'AUTO_REJECT'

const OUTCOME_ITEMS = [
  { value: 'ROUTE_FOR_APPROVAL', label: 'Route for approval' },
  { value: 'AUTO_REJECT', label: 'Auto-reject' },
]

/** Strings/numbers edit as-is; anything else (arrays, objects) edits as JSON. */
function paramToText(value: unknown) {
  return typeof value === 'string' || typeof value === 'number'
    ? String(value)
    : JSON.stringify(value)
}

/** Converts the edited text back to the original value's type. */
function textToParam(text: string, original: unknown): unknown {
  if (typeof original === 'string') return text
  if (typeof original === 'number') {
    const n = Number(text)
    return text.trim() === '' || Number.isNaN(n) ? text : n
  }
  try {
    return JSON.parse(text) as unknown
  } catch {
    return text
  }
}

interface PolicyRuleSheetProps {
  rule: PolicyRule | null
  onOpenChange: (open: boolean) => void
}

export function PolicyRuleSheet({ rule, onOpenChange }: PolicyRuleSheetProps) {
  return (
    <Sheet open={!!rule} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-md">
        {rule && <RuleForm key={rule.code} rule={rule} onDone={() => onOpenChange(false)} />}
      </SheetContent>
    </Sheet>
  )
}

function RuleForm({ rule, onDone }: { rule: PolicyRule; onDone: () => void }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState(rule.name)
  const [params, setParams] = useState<Record<string, string>>(() =>
    Object.fromEntries(Object.entries(rule.params).map(([k, v]) => [k, paramToText(v)])),
  )
  const [outcome, setOutcome] = useState(rule.outcome_on_breach)
  const [active, setActive] = useState(rule.active)
  const [template, setTemplate] = useState(rule.reason_template)

  const mutation = useMutation({
    mutationFn: (body: PolicyRuleUpdate) => updatePolicyRule(rule.code, body),
    onSuccess: async (updated) => {
      toast.success(`Saved "${updated.name}". Pending claims keep their earlier evaluation.`)
      await queryClient.invalidateQueries({ queryKey: ['policy-rules'] })
      onDone()
    },
  })

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    const body: PolicyRuleUpdate = {}
    if (name.trim() !== rule.name) body.name = name.trim()
    const nextParams = Object.fromEntries(
      Object.entries(params).map(([k, v]) => [k, textToParam(v, rule.params[k])]),
    )
    if (JSON.stringify(nextParams) !== JSON.stringify(rule.params)) body.params = nextParams
    if (outcome !== rule.outcome_on_breach) body.outcome_on_breach = outcome as Outcome
    if (active !== rule.active) body.active = active
    if (template !== rule.reason_template) body.reason_template = template
    if (Object.keys(body).length === 0) {
      onDone()
      return
    }
    mutation.mutate(body)
  }

  const paramEntries = Object.entries(params)
  const pending = mutation.isPending

  return (
    <form noValidate onSubmit={handleSubmit} className="flex min-h-full flex-col">
      <SheetHeader>
        <SheetTitle>Edit rule</SheetTitle>
        <SheetDescription className="font-mono text-xs">{rule.code}</SheetDescription>
      </SheetHeader>

      <div className="flex flex-1 flex-col gap-6 px-4">
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="rule-name">Name</FieldLabel>
            <Input
              id="rule-name"
              value={name}
              disabled={pending}
              onChange={(e) => setName(e.target.value)}
            />
          </Field>

          <FieldSet>
            <FieldLegend variant="label">Parameters</FieldLegend>
            {paramEntries.length === 0 ? (
              <FieldDescription>This rule has no parameters.</FieldDescription>
            ) : (
              <FieldGroup className="gap-4">
                {paramEntries.map(([key, value]) => (
                  <Field key={key}>
                    <FieldLabel htmlFor={`param-${key}`}>{paramLabel(key)}</FieldLabel>
                    <Input
                      id={`param-${key}`}
                      value={value}
                      disabled={pending}
                      inputMode={/^\d+(\.\d+)?$/.test(value) ? 'decimal' : undefined}
                      className="tabular-nums"
                      onChange={(e) => setParams((p) => ({ ...p, [key]: e.target.value }))}
                    />
                  </Field>
                ))}
              </FieldGroup>
            )}
          </FieldSet>

          <Field>
            <FieldLabel htmlFor="rule-outcome">Outcome on breach</FieldLabel>
            <Select
              items={OUTCOME_ITEMS}
              value={outcome}
              disabled={pending}
              onValueChange={(v) => v && setOutcome(v)}
            >
              <SelectTrigger id="rule-outcome" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {OUTCOME_ITEMS.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>

          <Field orientation="horizontal">
            <Checkbox
              id="rule-active"
              checked={active}
              disabled={pending}
              onCheckedChange={(checked) => setActive(checked)}
            />
            <FieldLabel htmlFor="rule-active">Active</FieldLabel>
          </Field>

          <Field>
            <FieldLabel htmlFor="rule-template">Reason template</FieldLabel>
            <Textarea
              id="rule-template"
              value={template}
              disabled={pending}
              rows={3}
              onChange={(e) => setTemplate(e.target.value)}
            />
            <FieldDescription>
              Shown to employees when the rule fires. Keep the {'{placeholders}'} this rule type
              supports.
            </FieldDescription>
          </Field>
        </FieldGroup>

        {mutation.isError && (
          <Alert variant="destructive">
            <WarningCircleIcon />
            <AlertDescription>{errorMessage(mutation.error)}</AlertDescription>
          </Alert>
        )}
        <p className="text-xs text-muted-foreground">
          Changes apply to new submissions only; pending claims are not re-evaluated.
        </p>
      </div>

      <SheetFooter>
        <Button type="submit" disabled={pending}>
          {pending ? 'Saving…' : 'Save rule'}
        </Button>
        <Button type="button" variant="outline" disabled={pending} onClick={onDone}>
          Cancel
        </Button>
      </SheetFooter>
    </form>
  )
}
