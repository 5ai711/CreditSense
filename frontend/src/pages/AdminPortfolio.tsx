import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Button, Card, ErrorState, Input, Kpi, Loading, PageHeader } from '../components/ui'
import { toApiError } from '../lib/api'
import { date, integer, pct } from '../lib/format'
import { STATUS_LABEL } from '../lib/labels'
import { useLifecycleActions, usePortfolio } from '../lib/queries'
import type { Analytics, ModelMetrics, Status } from '../lib/types'

const C = {
  low: '#3F7D58',
  medium: '#D9A441',
  high: '#C4453D',
  champion: '#5B6472',
  challenger: '#3A6EA5',
  axis: '#5B6472',
  grid: '#C3C9D1',
}
const axis = { stroke: C.axis, fontSize: 11, fontFamily: 'IBM Plex Mono' }
const tooltipStyle = { contentStyle: { background: '#12161C', border: 'none', borderRadius: 4, color: '#E4E7EB', fontSize: 12 }, labelStyle: { color: '#9AA3B0' } }

export function AdminPortfolio() {
  const q = usePortfolio()
  if (q.isLoading) return <Loading label="Loading portfolio" />
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />
  if (!q.data) return null
  const d = q.data
  const k = d.kpis
  return (
    <>
      <PageHeader title="Portfolio" subtitle="Risk mix, realised defaults and live model performance." />
      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Kpi label="Applications" value={integer(k.totalApplications)} sub={`${k.pendingReview} awaiting decision`} />
        <Kpi label="Approval rate" value={pct(k.approvalRate)} sub={`${k.approved} approved · ${k.rejected} rejected`} />
        <Kpi label="Avg PD approved" value={pct(k.averageApprovedPd)} tone="amber" />
        <Kpi label="Observed default" value={pct(k.observedDefaultRate)} sub={`${k.maturedLoans} matured loans`} tone="risk" />
        <Kpi label="Compliance failed" value={integer(k.complianceFailed)} sub={`${k.manualReview} in manual review`} />
        <Kpi label="Override rate" value={pct(k.overrideRate)} sub="officer vs model" />
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card title="Risk distribution (probability of default)">
          <Histogram d={d} />
        </Card>
        <Card title="Default rate by approval month">
          <Trend d={d} />
        </Card>
        <Card title="Champion vs challenger (held-out AUC)">
          <LifecycleActions />
          <ChampionChallenger d={d} />
        </Card>
        <Card title="Serving model">
          <ModelCard d={d} />
        </Card>
      </div>

      <Card title="Applications by status" className="mt-5">
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
          {(Object.entries(d.statusCounts) as [Status, number][]).map(([s, n]) => (
            <div key={s}>
              <dt className="text-xs text-muted">{STATUS_LABEL[s]}</dt>
              <dd className="num text-xl">{n}</dd>
            </div>
          ))}
        </dl>
      </Card>
    </>
  )
}

function Histogram({ d }: { d: Analytics }) {
  const data = d.pdHistogram.map((b) => ({
    label: b.to >= 1 ? '50%+' : `${(b.from * 100).toFixed(1)}`,
    range: b.to >= 1 ? '50% and above' : `${(b.from * 100).toFixed(1)}–${(b.to * 100).toFixed(1)}%`,
    count: b.count,
    color: b.from < 0.05 ? C.low : b.from < 0.2 ? C.medium : C.high,
  }))
  return (
    <>
      <div className="h-64" role="img" aria-label={`Histogram of probability of default. Bands: ${d.riskBandCounts.LOW} low, ${d.riskBandCounts.MEDIUM} medium, ${d.riskBandCounts.HIGH} high.`}>
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: -16 }} barCategoryGap={2}>
            <CartesianGrid vertical={false} stroke={C.grid} strokeDasharray="2 4" />
            <XAxis dataKey="label" tick={axis} interval={1} tickLine={false} />
            <YAxis allowDecimals={false} tick={axis} tickLine={false} axisLine={false} />
            <Tooltip {...tooltipStyle} formatter={(v) => [v, 'applications']} labelFormatter={(_, p) => p?.[0]?.payload?.range ?? ''} />
            <Bar dataKey="count" radius={[3, 3, 0, 0]}>
              {data.map((x, i) => <Cell key={i} fill={x.color} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 flex flex-wrap gap-4 text-xs text-muted">
        <Swatch color={C.low}>Low &lt; 5% ({d.riskBandCounts.LOW})</Swatch>
        <Swatch color={C.medium}>Medium 5–20% ({d.riskBandCounts.MEDIUM})</Swatch>
        <Swatch color={C.high}>High ≥ 20% ({d.riskBandCounts.HIGH})</Swatch>
      </p>
    </>
  )
}

function Trend({ d }: { d: Analytics }) {
  const data = d.defaultRateTrend.map((t) => ({ ...t, defaultRate: t.defaultRate, averagePd: t.averagePd }))
  if (!data.length) return <p className="text-sm text-muted">No approvals yet.</p>
  return (
    <>
      <div className="h-64" role="img" aria-label="Observed default rate and average predicted PD by month of approval">
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -8 }}>
            <CartesianGrid vertical={false} stroke={C.grid} strokeDasharray="2 4" />
            <XAxis dataKey="month" tick={axis} tickLine={false} />
            <YAxis tick={axis} tickFormatter={(v) => `${Math.round(v * 100)}%`} tickLine={false} axisLine={false} />
            <Tooltip
              {...tooltipStyle}
              formatter={(v, name) => [v == null ? 'not matured' : pct(Number(v)), name]}
              labelFormatter={(m, p) => {
                const row = p?.[0]?.payload
                return row ? `${m}: ${row.approved} approved, ${row.matured} matured, ${row.defaulted} defaulted` : String(m)
              }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line name="Observed default rate" dataKey="defaultRate" stroke={C.high} strokeWidth={2} dot={{ r: 3 }} connectNulls />
            <Line name="Average predicted PD" dataKey="averagePd" stroke={C.champion} strokeWidth={2} strokeDasharray="5 4" dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-xs text-muted">Recent months have no matured loans yet; outcomes appear after "Simulate maturity".</p>
    </>
  )
}

function ChampionChallenger({ d }: { d: Analytics }) {
  const rows = (d.modelHistory?.comparisons ?? []).map((c, i) => ({
    label: c.event === 'bootstrap' ? 'Initial' : `Retrain ${i}`,
    champion: c.champion_holdout_auc,
    challenger: c.challenger_holdout_auc,
    promoted: c.promoted,
    at: c.at,
    feedback: c.feedback_rows,
  }))
  if (!d.modelServiceAvailable) return <p className="text-sm text-risk-deep">The ML service is unreachable (circuit {d.circuitBreaker.toLowerCase()}).</p>
  if (!rows.length) return <p className="text-sm text-muted">No training history yet.</p>
  const values = rows.flatMap((r) => [r.champion, r.challenger]).filter((v): v is number => v != null)
  const lo = Math.floor((Math.min(...values) - 0.01) * 100) / 100
  const hi = Math.ceil((Math.max(...values) + 0.005) * 100) / 100
  return (
    <>
      <div className="h-64" role="img" aria-label="Held-out AUC of champion and challenger for each training event">
        <ResponsiveContainer>
          <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 4, left: -8 }} barGap={2}>
            <CartesianGrid vertical={false} stroke={C.grid} strokeDasharray="2 4" />
            <XAxis dataKey="label" tick={axis} tickLine={false} />
            <YAxis domain={[lo, hi]} tick={axis} tickFormatter={(v) => Number(v).toFixed(3)} tickLine={false} axisLine={false} />
            <Tooltip {...tooltipStyle} formatter={(v, n) => [v == null ? '—' : Number(v).toFixed(4), n]}
              labelFormatter={(l, p) => { const r = p?.[0]?.payload; return r ? `${l} · ${date(r.at)} · ${r.feedback} feedback rows · ${r.promoted ? 'promoted' : 'kept champion'}` : String(l) }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar name="Champion" dataKey="champion" fill={C.champion} radius={[3, 3, 0, 0]} />
            <Bar name="Challenger" dataKey="challenger" fill={C.challenger} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-2 space-y-0.5 text-xs text-muted">
        {rows.map((r) => (
          <li key={r.label} className="num">
            {r.label}: {r.promoted ? 'challenger promoted' : 'champion kept'} {r.champion != null && `(${r.challenger.toFixed(4)} vs ${r.champion.toFixed(4)})`}
          </li>
        ))}
      </ul>
    </>
  )
}

function ModelCard({ d }: { d: Analytics }) {
  const m = d.model
  if (!m) return <p className="text-sm text-risk-deep">Model details unavailable: the ML service cannot be reached.</p>
  const rows: [string, keyof ModelMetrics, boolean][] = [
    ['AUC-ROC', 'auc_roc', true],
    ['PR-AUC', 'pr_auc', true],
    ['KS statistic', 'ks', true],
    ['Brier score', 'brier', false],
    ['Calibration error', 'ece', false],
  ]
  const curve = m.metrics.calibration_curve.map((c) => ({ predicted: c.mean_predicted, observed: c.observed_rate }))
  const cm = m.metrics.confusion_matrix
  return (
    <div className="space-y-4">
      <p className="text-sm">
        <span className="num font-medium">{m.model_version}</span> · trained {date(m.trained_at)} · {integer(m.training_rows)} rows · {integer(m.feedback_rows)} outcomes fed back
      </p>
      <table className="w-full text-sm">
        <caption className="sr-only">Test metrics for the serving model and the baseline</caption>
        <thead className="text-left text-xs text-muted uppercase">
          <tr><th className="py-1 font-medium">Metric</th><th className="py-1 text-right font-medium">XGBoost</th><th className="py-1 text-right font-medium">WOE scorecard</th></tr>
        </thead>
        <tbody className="divide-y divide-paper-rule">
          {rows.map(([label, key, higher]) => {
            const a = m.metrics[key] as number
            const b = m.baseline_metrics[key] as number
            const better = higher ? a > b : a < b
            return (
              <tr key={key}>
                <td className="py-1.5">{label}</td>
                <td className={`num py-1.5 text-right ${better ? 'font-semibold text-confirm-deep' : ''}`}>{a.toFixed(3)}</td>
                <td className="num py-1.5 text-right">{b.toFixed(3)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <p className="mb-1 text-xs font-medium tracking-wide text-muted uppercase">Calibration</p>
          <div className="h-40" role="img" aria-label="Calibration curve: observed default rate against predicted probability">
            <ResponsiveContainer>
              <LineChart data={curve} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                <CartesianGrid stroke={C.grid} strokeDasharray="2 4" />
                <XAxis type="number" dataKey="predicted" domain={[0, 'dataMax']} tick={axis} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
                <YAxis type="number" domain={[0, 'dataMax']} tick={axis} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
                <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 0.6, y: 0.6 }]} stroke={C.axis} strokeDasharray="3 3" />
                <Tooltip {...tooltipStyle} formatter={(v) => pct(Number(v))} labelFormatter={(v) => `predicted ${pct(Number(v))}`} />
                <Line dataKey="observed" name="Observed" stroke={C.challenger} strokeWidth={2} dot={{ r: 2.5 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div>
          <p className="mb-1 text-xs font-medium tracking-wide text-muted uppercase">Confusion at PD ≥ {pct(cm.threshold, 0)}</p>
          <table className="num w-full text-center text-sm">
            <caption className="sr-only">Confusion matrix on the test set</caption>
            <thead className="text-[11px] text-muted"><tr><th /><th className="font-normal">pred. repay</th><th className="font-normal">pred. default</th></tr></thead>
            <tbody>
              <tr><th className="text-[11px] font-normal text-muted">repaid</th><td className="bg-confirm/15 py-2">{cm.tn}</td><td className="bg-risk/10 py-2">{cm.fp}</td></tr>
              <tr><th className="text-[11px] font-normal text-muted">defaulted</th><td className="bg-risk/10 py-2">{cm.fn}</td><td className="bg-confirm/15 py-2">{cm.tp}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function LifecycleActions() {
  const { mature, retrain } = useLifecycleActions()
  const [age, setAge] = useState(90)
  const msg = mature.data
    ? `${mature.data.matured} loans matured, ${mature.data.defaulted} defaulted`
    : retrain.data
      ? retrain.data.promoted ? `Challenger promoted → ${retrain.data.serving_version}` : 'Champion kept: challenger did not beat it'
      : null
  const err = mature.error ?? retrain.error
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2 border-b border-paper-rule pb-3">
      <p className="mr-auto text-xs text-muted">Feed matured-loan outcomes back, then retrain a challenger.</p>
      <label className="flex items-center gap-1 text-xs text-muted">
        Loans older than
        <Input type="number" min={0} value={age} onChange={(e) => setAge(Number(e.target.value))} className="num w-16 px-2 py-1" aria-label="Minimum loan age in days" />
        days
      </label>
      <Button variant="ghost" className="px-2.5 py-1 text-xs" busy={mature.isPending} onClick={() => mature.mutate(age)}>Simulate maturity</Button>
      <Button className="px-2.5 py-1 text-xs" busy={retrain.isPending} onClick={() => retrain.mutate()}>Retrain</Button>
      {(msg || err) && (
        <p role="status" className={`w-full text-xs ${err ? 'text-risk-deep' : 'text-confirm-deep'}`}>
          {err ? toApiError(err).message : msg}
        </p>
      )}
    </div>
  )
}

function Swatch({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span aria-hidden className="size-2.5 rounded-sm" style={{ background: color }} />
      {children}
    </span>
  )
}
