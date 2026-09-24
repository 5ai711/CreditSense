import clsx from 'clsx'
import { Check, Circle, X } from 'lucide-react'
import { lakh, pct } from '../lib/format'
import { DOC_LABEL } from '../lib/labels'
import type { Detail } from '../lib/types'
import { RiskBadge } from './badges'

type StepState = 'done' | 'failed' | 'current' | 'todo' | 'manual'

export function PipelineStepper({ app }: { app: Detail }) {
  const s = app.status
  const gate: StepState = s === 'SUBMITTED' ? 'current' : s === 'COMPLIANCE_FAILED' ? 'failed' : 'done'
  const scoring: StepState =
    s === 'COMPLIANCE_FAILED' || s === 'SUBMITTED' ? 'todo'
      : s === 'COMPLIANCE_REVIEW' ? 'current'
        : s === 'MANUAL_REVIEW' || (!app.riskAssessment && (s === 'APPROVED' || s === 'REJECTED')) ? 'manual'
          : 'done'
  const decision: StepState =
    s === 'APPROVED' ? 'done' : s === 'REJECTED' ? 'failed' : s === 'RISK_SCORED' || s === 'MANUAL_REVIEW' ? 'current' : 'todo'
  const steps: [string, StepState][] = [
    ['Submitted', 'done'],
    ['Compliance gate', gate],
    ['Risk scoring', scoring],
    ['Decision', decision],
  ]
  return (
    <ol className="flex flex-wrap gap-x-6 gap-y-2" aria-label="Application progress">
      {steps.map(([label, st]) => (
        <li key={label} className="flex items-center gap-2 text-sm">
          <span
            className={clsx(
              'grid size-5 place-items-center rounded-full',
              st === 'done' && 'bg-confirm text-white',
              st === 'failed' && 'bg-risk text-white',
              st === 'current' && 'bg-amber text-ink',
              st === 'manual' && 'bg-amber text-ink',
              st === 'todo' && 'bg-paper-deep text-muted',
            )}
            aria-hidden
          >
            {st === 'done' ? <Check className="size-3.5" /> : st === 'failed' ? <X className="size-3.5" /> : <Circle className="size-2.5 fill-current" />}
          </span>
          <span className={clsx(st === 'todo' && 'text-muted')}>
            {label}
            {st === 'manual' && <span className="text-muted"> (manual)</span>}
            <span className="sr-only">: {st}</span>
          </span>
        </li>
      ))}
    </ol>
  )
}

export function ScoreBlock({ app }: { app: Detail }) {
  const r = app.riskAssessment
  if (!r) return null
  return (
    <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
      <div>
        <p className="text-xs font-medium tracking-wide text-muted uppercase">Probability of default</p>
        <p className="num text-4xl leading-none">{pct(r.probabilityOfDefault)}</p>
      </div>
      <div className="pb-1">
        <RiskBadge band={r.riskBand} />
      </div>
      <div className="pb-1 text-xs text-muted">
        <p>Model <span className="num">{r.modelVersion}</span></p>
        <p>Scored <span className="num">{new Date(r.assessedAt).toLocaleDateString('en-IN')}</span></p>
      </div>
    </div>
  )
}

export function Documents({ app }: { app: Detail }) {
  return (
    <ul className="divide-y divide-paper-rule text-sm">
      {app.documents.map((d, i) => (
        <li key={i} className="flex items-start justify-between gap-3 py-2">
          <div className="min-w-0">
            <p className="font-medium">{DOC_LABEL[d.type]}</p>
            <p className="num truncate text-xs text-muted">
              {d.documentNumber}
              {d.monthsCovered ? ` · ${d.monthsCovered} months` : ''}
            </p>
          </div>
          <span className={clsx('shrink-0 text-xs font-medium', d.verified ? 'text-confirm-deep' : 'text-risk-deep')}>
            {d.verified ? 'Verified' : d.verificationNote ?? 'Not verified'}
          </span>
        </li>
      ))}
      {app.kycScore != null && (
        <li className="flex justify-between py-2 text-sm">
          <span className="text-muted">Weighted completeness</span>
          <span className="num font-medium">{pct(app.kycScore, 0)}</span>
        </li>
      )}
    </ul>
  )
}

export function Financials({ app }: { app: Detail }) {
  const f = app.financials
  const avg = f.monthlyRevenues.reduce((a, b) => a + b, 0) / f.monthlyRevenues.length
  const max = Math.max(...f.monthlyRevenues)
  return (
    <div className="space-y-3 text-sm">
      <div>
        <p className="mb-1 text-xs font-medium tracking-wide text-muted uppercase">Monthly revenue, last 6 months</p>
        <div className="flex h-14 items-end gap-1.5" aria-label={`Monthly revenue: ${f.monthlyRevenues.map((r) => lakh(r)).join(', ')}`}>
          {f.monthlyRevenues.map((r, i) => (
            <span key={i} className="flex-1 rounded-t-sm bg-steel" style={{ height: `${(r / max) * 100}%` }} title={lakh(r)} />
          ))}
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5">
        {([
          ['Avg revenue', lakh(avg)],
          ['Existing debt', lakh(f.existingDebt)],
          ['Bank credits / mo', lakh(f.avgMonthlyInflow)],
          ['Bank debits / mo', lakh(f.avgMonthlyOutflow)],
          ['Avg balance', lakh(f.avgBankBalance)],
          ['GST on time', `${f.gstOnTimeFilingPct}%`],
          ['Trade refs', String(f.tradeReferences)],
          ['Past delays', String(f.delinquencyEvents)],
          ['Digital payments', `${f.digitalTxnPerMonth}/mo`],
        ] as const).map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-muted">{k}</dt>
            <dd className="num text-right">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
