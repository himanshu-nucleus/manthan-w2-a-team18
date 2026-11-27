import { adminHandlers } from './admin'
import { approvalsHandlers } from './approvals'
import { auditLogsHandlers } from './audit-logs'
import { authHandlers } from './auth'
import { claimsHandlers } from './claims'
import { dashboardHandlers } from './dashboard'
import { payoutsHandlers } from './payouts'

export const handlers = [
  ...authHandlers,
  ...claimsHandlers,
  ...approvalsHandlers,
  ...adminHandlers,
  ...payoutsHandlers,
  ...auditLogsHandlers,
  ...dashboardHandlers,
]
