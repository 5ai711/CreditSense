import clsx from 'clsx'
import { ArrowDown, ArrowUp, Search } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { DecisionTag, RiskBadge, StatusBadge } from '../components/badges'
import { Button, Empty, ErrorState, Input, Loading, PageHeader } from '../components/ui'
import { date, lakh, pct } from '../lib/format'
import { STATUS_LABEL, sectorLabel } from '../lib/labels'
import { useQueue, type QueueFilters } from '../lib/queries'
import type { RiskBand, Status } from '../lib/types'

const STATUS_FILTERS: Status[] = ['RISK_SCORED', 'MANUAL_REVIEW', 'COMPLIANCE_FAILED', 'APPROVED', 'REJECTED']
const BANDS: RiskBand[] = ['LOW', 'MEDIUM', 'HIGH']

export function OfficerQueue() {
  const navigate = useNavigate()
  const [f, setF] = useState<QueueFilters>({ status: ['RISK_SCORED', 'MANUAL_REVIEW'], band: [], q: '', page: 0, sort: 'submittedAt,desc' })
  const [search, setSearch] = useState('')
  const q = useQueue(f)

  const toggle = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v])
  const sortBy = (field: string) => {
    const [cur, dir] = f.sort.split(',')
    setF({ ...f, page: 0, sort: `${field},${cur === field && dir === 'desc' ? 'asc' : 'desc'}` })
  }
  const SortIcon = ({ field }: { field: string }) => {
    const [cur, dir] = f.sort.split(',')
    if (cur !== field) return null
    return dir === 'desc' ? <ArrowDown aria-hidden className="size-3" /> : <ArrowUp aria-hidden className="size-3" />
  }
  const ariaSort = (field: string) => {
    const [cur, dir] = f.sort.split(',')
    return cur === field ? (dir === 'desc' ? 'descending' : 'ascending') : 'none'
  }

  return (
    <>
      <PageHeader title="Application queue" subtitle="Scored applications waiting for a decision come first. Every decision is recorded in the audit trail." />

      <div className="mb-4 flex flex-col gap-3 rounded-md bg-panel-raised p-3 ring-1 ring-rule lg:flex-row lg:items-center">
        <form
          role="search"
          className="flex flex-1 gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            setF({ ...f, q: search, page: 0 })
          }}
        >
          <label htmlFor="q" className="sr-only">Search by reference or business</label>
          <Input id="q" placeholder="Reference or business name" value={search} onChange={(e) => setSearch(e.target.value)} className="bg-paper" />
          <Button type="submit" variant="ghost" className="border-rule bg-paper" aria-label="Search"><Search className="size-4" /></Button>
        </form>
        <fieldset className="flex flex-wrap gap-1.5">
          <legend className="sr-only">Status</legend>
          {STATUS_FILTERS.map((s) => (
            <Chip key={s} on={f.status.includes(s)} onClick={() => setF({ ...f, page: 0, status: toggle(f.status, s) })}>
              {STATUS_LABEL[s]}
            </Chip>
          ))}
        </fieldset>
        <fieldset className="flex gap-1.5">
          <legend className="sr-only">Risk band</legend>
          {BANDS.map((b) => (
            <Chip key={b} on={f.band.includes(b)} onClick={() => setF({ ...f, page: 0, band: toggle(f.band, b) })}>
              {b}
            </Chip>
          ))}
        </fieldset>
      </div>

      {q.isLoading && <Loading />}
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {q.data && (
        <div className="overflow-x-auto rounded-md bg-paper text-ink">
          <table className="w-full min-w-[52rem] text-sm">
            <caption className="sr-only">Loan applications</caption>
            <thead className="border-b border-paper-rule text-left text-xs tracking-wide text-muted uppercase">
              <tr>
                <th className="px-3 py-2 font-medium">Reference</th>
                <th className="px-3 py-2 font-medium">Business</th>
                <th className="px-3 py-2 text-right font-medium" aria-sort={ariaSort('amountRequested')}>
                  <button className="inline-flex items-center gap-1 uppercase" onClick={() => sortBy('amountRequested')}>Amount <SortIcon field="amountRequested" /></button>
                </th>
                <th className="px-3 py-2 text-right font-medium" aria-sort={ariaSort('latestPd')}>
                  <button className="inline-flex items-center gap-1 uppercase" onClick={() => sortBy('latestPd')}>PD <SortIcon field="latestPd" /></button>
                </th>
                <th className="px-3 py-2 font-medium">Band</th>
                <th className="px-3 py-2 font-medium">Model says</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium" aria-sort={ariaSort('submittedAt')}>
                  <button className="inline-flex items-center gap-1 uppercase" onClick={() => sortBy('submittedAt')}>Submitted <SortIcon field="submittedAt" /></button>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-paper-rule">
              {q.data.content.map((a) => (
                <tr
                  key={a.id}
                  tabIndex={0}
                  onClick={() => navigate(`/officer/applications/${a.id}`)}
                  onKeyDown={(e) => e.key === 'Enter' && navigate(`/officer/applications/${a.id}`)}
                  className="cursor-pointer hover:bg-paper-deep focus-visible:bg-paper-deep"
                >
                  <td className="num px-3 py-2.5 text-xs">{a.reference}</td>
                  <td className="px-3 py-2.5">
                    <p className="font-medium">{a.businessName}</p>
                    <p className="text-xs text-muted">{sectorLabel(a.sector)}</p>
                  </td>
                  <td className="num px-3 py-2.5 text-right">{lakh(a.amountRequested)}</td>
                  <td className="num px-3 py-2.5 text-right">{pct(a.probabilityOfDefault)}</td>
                  <td className="px-3 py-2.5"><RiskBadge band={a.riskBand} /></td>
                  <td className="px-3 py-2.5"><DecisionTag decision={a.modelRecommendation} /></td>
                  <td className="px-3 py-2.5"><StatusBadge status={a.status} /></td>
                  <td className="num px-3 py-2.5 text-xs">{date(a.submittedAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {q.data.content.length === 0 && <Empty>No applications match these filters.</Empty>}
          <div className="flex items-center justify-between border-t border-paper-rule px-3 py-2 text-xs text-muted">
            <span className="num">
              {q.data.page.totalElements} applications · page {q.data.page.number + 1} of {Math.max(1, q.data.page.totalPages)}
            </span>
            <div className="flex gap-2">
              <Button variant="ghost" disabled={f.page === 0} onClick={() => setF({ ...f, page: f.page - 1 })}>Previous</Button>
              <Button variant="ghost" disabled={f.page + 1 >= q.data.page.totalPages} onClick={() => setF({ ...f, page: f.page + 1 })}>Next</Button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={clsx('rounded-full px-3 py-1 text-xs font-medium ring-1', on ? 'bg-paper text-ink ring-paper' : 'text-fog ring-rule hover:text-paper')}
    >
      {children}
    </button>
  )
}
