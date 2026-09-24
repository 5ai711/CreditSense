import clsx from 'clsx'
import { Check, X } from 'lucide-react'
import { CHECK_LABEL } from '../lib/labels'
import type { ComplianceCheck } from '../lib/types'

export function ComplianceChecklist({ checks }: { checks: ComplianceCheck[] }) {
  if (!checks.length) return <p className="text-sm text-muted">The compliance gate has not run yet.</p>
  return (
    <ul className="divide-y divide-paper-rule">
      {checks.map((c) => (
        <li key={c.checkType} className="flex items-start gap-3 py-2.5">
          <span
            className={clsx('mt-0.5 grid size-5 shrink-0 place-items-center rounded-full', c.passed ? 'bg-confirm text-white' : 'bg-risk text-white')}
            aria-hidden
          >
            {c.passed ? <Check className="size-3.5" /> : <X className="size-3.5" />}
          </span>
          <div className="min-w-0">
            <p className="text-sm font-medium">
              {CHECK_LABEL[c.checkType]} <span className="sr-only">{c.passed ? 'passed' : 'failed'}</span>
              <span className="ml-2 text-[10px] font-semibold tracking-wider text-muted uppercase">{c.category}</span>
            </p>
            <p className={clsx('text-xs', c.passed ? 'text-muted' : 'text-risk-deep')}>{c.reason}</p>
          </div>
        </li>
      ))}
    </ul>
  )
}
