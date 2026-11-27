import { PencilSimpleIcon, WarningCircleIcon } from '@phosphor-icons/react'
import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'
import { PageHeader } from '@/components/app-shell'
import { POLICY_OUTCOME, StatusChip } from '@/components/status-chip'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { type PolicyRule, policyRulesQuery } from '@/features/admin/api'
import { paramLabel } from '@/features/admin/components/param-label'
import { PolicyRuleSheet } from '@/features/admin/components/policy-rule-sheet'
import { errorMessage } from '@/lib/api'
import { formatDateTime } from '@/lib/format'

export const Route = createFileRoute('/_authed/admin/policy-rules')({
  head: () => ({ meta: [{ title: 'Policy rules · ExpenseFlow' }] }),
  component: PolicyRulesPage,
})

function paramsSummary(params: Record<string, unknown>) {
  const entries = Object.entries(params)
  if (entries.length === 0) return '—'
  return entries
    .map(([k, v]) => `${paramLabel(k)}: ${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(' · ')
}

function PolicyRulesPage() {
  const { user } = Route.useRouteContext()
  const canEdit = user.role === 'finance_head'
  const [showInactive, setShowInactive] = useState(false)
  const [editing, setEditing] = useState<PolicyRule | null>(null)
  const rules = useQuery(policyRulesQuery(canEdit && showInactive))

  return (
    <>
      <PageHeader
        title="Policy rules"
        description={
          canEdit
            ? 'Limits and checks applied when a claim is submitted. Changes apply to new submissions only.'
            : 'Limits and checks applied when a claim is submitted. Only the finance head can change them.'
        }
        actions={
          canEdit && (
            <div className="flex items-center gap-2">
              <Checkbox
                id="show-inactive"
                checked={showInactive}
                onCheckedChange={(checked) => setShowInactive(checked)}
              />
              <Label htmlFor="show-inactive">Show inactive</Label>
            </div>
          )
        }
      />

      {rules.isError ? (
        <Alert variant="destructive">
          <WarningCircleIcon />
          <AlertDescription>{errorMessage(rules.error)}</AlertDescription>
        </Alert>
      ) : (
        <div className="overflow-hidden rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Rule</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Parameters</TableHead>
                <TableHead>On breach</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Updated</TableHead>
                {canEdit && (
                  <TableHead>
                    <span className="sr-only">Actions</span>
                  </TableHead>
                )}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rules.isPending
                ? Array.from({ length: 5 }, (_, i) => (
                    <TableRow key={i}>
                      <TableCell colSpan={canEdit ? 8 : 7}>
                        <Skeleton className="h-5 w-full" />
                      </TableCell>
                    </TableRow>
                  ))
                : rules.data.map((rule) => {
                    const outcome = POLICY_OUTCOME[rule.outcome_on_breach] ?? {
                      label: rule.outcome_on_breach,
                      tone: 'neutral' as const,
                    }
                    return (
                      <TableRow key={rule.code}>
                        <TableCell className="max-w-72 whitespace-normal">
                          <div className="font-medium">{rule.name}</div>
                          <div className="font-mono text-xs text-muted-foreground">{rule.code}</div>
                        </TableCell>
                        <TableCell className="capitalize">{rule.category ?? 'Any'}</TableCell>
                        <TableCell className="font-mono text-xs">{rule.rule_type}</TableCell>
                        <TableCell className="max-w-64 whitespace-normal tabular-nums">
                          {paramsSummary(rule.params)}
                        </TableCell>
                        <TableCell>
                          <StatusChip tone={outcome.tone} label={outcome.label} />
                        </TableCell>
                        <TableCell>
                          {rule.active ? (
                            <Badge variant="secondary">Active</Badge>
                          ) : (
                            <Badge variant="outline">Inactive</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {formatDateTime(rule.updated_at)}
                        </TableCell>
                        {canEdit && (
                          <TableCell className="text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              aria-label={`Edit ${rule.name}`}
                              onClick={() => setEditing(rule)}
                            >
                              <PencilSimpleIcon data-icon="inline-start" />
                              Edit
                            </Button>
                          </TableCell>
                        )}
                      </TableRow>
                    )
                  })}
              {rules.isSuccess && rules.data.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={canEdit ? 8 : 7}
                    className="py-8 text-center text-muted-foreground"
                  >
                    No policy rules configured.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}

      {canEdit && (
        <PolicyRuleSheet rule={editing} onOpenChange={(open) => !open && setEditing(null)} />
      )}
    </>
  )
}
