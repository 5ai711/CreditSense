import clsx from 'clsx'
import { featureMeta } from '../lib/features'
import { pct, sigmoid, signed } from '../lib/format'
import type { Contribution } from '../lib/types'

interface Props {
  baseValue: number
  contributions: Contribution[]
  probabilityOfDefault: number
  /** Applicants see plain-language lines; officers also see raw values. */
  audience: 'applicant' | 'officer'
}

/**
 * The explanation ledger: each feature is a signed line item on the log-odds scale.
 * Bars grow right (risk red) when a feature pushes the score toward default and left
 * (confirm green) when it pulls toward approval. The lines balance to the final score.
 */
export function Ledger({ baseValue, contributions, probabilityOfDefault, audience }: Props) {
  const rows = [...contributions].sort((a, b) => Math.abs(b.shapContribution) - Math.abs(a.shapContribution))
  const max = Math.max(0.25, ...rows.map((r) => Math.abs(r.shapContribution)))
  const total = rows.reduce((s, r) => s + r.shapContribution, 0)
  const raising = rows.filter((r) => r.shapContribution > 0).length

  return (
    <figure className="text-ink">
      <figcaption className="sr-only">
        Explanation of the risk score: {raising} factors raise risk and {rows.length - raising} lower it.
      </figcaption>

      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-4 border-b border-paper-rule pb-2 text-xs tracking-wide text-muted uppercase">
        <span>Line item</span>
        <span className="num text-right">log-odds</span>
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 border-b border-dashed border-paper-rule py-2 text-sm">
        <span className="text-muted">Opening balance: a typical applicant ({pct(sigmoid(baseValue))} risk)</span>
        <span className="num text-right">{signed(baseValue)}</span>
      </div>

      <ol className="divide-y divide-paper-rule/70">
        {rows.map((r) => {
          const meta = featureMeta(r.feature)
          const neutral = Math.abs(r.shapContribution) < 0.005
          const up = r.shapContribution > 0
          const width = `${(Math.abs(r.shapContribution) / max) * 50}%`
          const line = meta.says(r.featureValue)
          return (
            <li
              key={r.feature}
              className="grid grid-cols-[minmax(0,1fr)_4rem] items-center gap-x-4 gap-y-1 py-2 sm:grid-cols-[minmax(0,15rem)_minmax(0,1fr)_4.5rem]"
              aria-label={neutral ? `${line}: no effect on risk` : `${line}: ${up ? 'raises' : 'lowers'} risk by ${Math.abs(r.shapContribution).toFixed(2)}`}
            >
              <div className="col-span-2 min-w-0 sm:col-span-1">
                <p className="truncate text-sm font-medium">
                  {meta.label}
                  {audience === 'officer' && <span className="num ml-2 text-xs font-normal text-muted">{meta.value(r.featureValue)}</span>}
                </p>
                <p className="text-xs text-muted">{line}</p>
              </div>
              <div aria-hidden className="relative h-4">
                <span className="absolute inset-y-[-4px] left-1/2 w-px bg-ink/40" />
                <span
                  className={clsx('absolute top-0 h-4 rounded-sm', up ? 'left-1/2 bg-risk' : 'right-1/2 bg-confirm')}
                  style={{ width }}
                />
              </div>
              <span className={clsx('num text-right text-sm', neutral ? 'text-muted' : up ? 'text-risk-deep' : 'text-confirm-deep')}>
                {neutral ? '0.00' : signed(r.shapContribution)}
              </span>
            </li>
          )
        })}
      </ol>

      <div className="mt-1 grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 border-t-2 border-double border-ink/60 pt-2 text-sm">
        <span className="text-muted">Sum of line items</span>
        <span className="num text-right">{signed(total)}</span>
        <span className="font-semibold">Closing balance → probability of default</span>
        <span className="num text-right font-semibold">
          {signed(baseValue + total)} → {pct(probabilityOfDefault)}
        </span>
      </div>
      <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        <span className="inline-flex items-center gap-1.5"><span aria-hidden className="h-2.5 w-4 rounded-sm bg-risk" /> raises risk</span>
        <span className="inline-flex items-center gap-1.5"><span aria-hidden className="h-2.5 w-4 rounded-sm bg-confirm" /> lowers risk</span>
        <span>Values are changes in the log-odds of default; they add up exactly to the score.</span>
      </p>
    </figure>
  )
}
