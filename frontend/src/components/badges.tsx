import clsx from 'clsx'
import { STATUS_LABEL } from '../lib/labels'
import type { Decision, RiskBand, Status } from '../lib/types'

export function RiskBadge({ band }: { band: RiskBand | null }) {
  if (!band) return <span className="text-xs text-muted">—</span>
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-[11px] font-semibold tracking-wider uppercase',
        band === 'LOW' && 'bg-confirm text-white',
        band === 'MEDIUM' && 'bg-amber text-ink',
        band === 'HIGH' && 'bg-risk text-white',
      )}
    >
      <span aria-hidden className="size-1.5 rounded-full bg-current opacity-80" />
      {band} risk
    </span>
  )
}

const STATUS_TONE: Record<Status, string> = {
  SUBMITTED: 'bg-paper-deep text-ink',
  COMPLIANCE_REVIEW: 'bg-paper-deep text-ink',
  COMPLIANCE_FAILED: 'bg-risk/15 text-risk-deep ring-1 ring-risk/40',
  RISK_SCORED: 'bg-steel/15 text-steel ring-1 ring-steel/40',
  MANUAL_REVIEW: 'bg-amber/20 text-[#7a5a14] ring-1 ring-amber/60',
  APPROVED: 'bg-confirm/15 text-confirm-deep ring-1 ring-confirm/40',
  REJECTED: 'bg-ink/10 text-ink ring-1 ring-ink/30',
}

export function StatusBadge({ status }: { status: Status }) {
  return (
    <span className={clsx('inline-flex rounded px-2 py-0.5 text-xs font-medium whitespace-nowrap', STATUS_TONE[status])}>
      {STATUS_LABEL[status]}
    </span>
  )
}

export function DecisionTag({ decision }: { decision: Decision | null }) {
  if (!decision) return <span className="text-muted">—</span>
  return (
    <span className={clsx('text-xs font-semibold uppercase', decision === 'APPROVE' ? 'text-confirm-deep' : 'text-risk-deep')}>
      {decision === 'APPROVE' ? 'Approve' : 'Reject'}
    </span>
  )
}
