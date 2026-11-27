import { adminHandlers } from './admin'
import { approvalsHandlers } from './approvals'
import { authHandlers } from './auth'
import { claimsHandlers } from './claims'

export const handlers = [...authHandlers, ...claimsHandlers, ...approvalsHandlers, ...adminHandlers]
