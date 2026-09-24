import { ChevronDown, ChevronRight } from 'lucide-react'
import { Fragment, useState } from 'react'
import { Button, Empty, ErrorState, Input, Loading, PageHeader, Select } from '../components/ui'
import { dateTime, humanize } from '../lib/format'
import { useAuditLogs, type AuditFilters } from '../lib/queries'

const ACTIONS = [
  'APPLICATION_SUBMITTED', 'COMPLIANCE_EVALUATED', 'RISK_ASSESSED', 'ROUTED_TO_MANUAL_REVIEW', 'DECISION_RECORDED',
  'LOAN_OUTCOME_RECORDED', 'OUTCOMES_SIMULATED', 'MODEL_RETRAINED', 'USER_REGISTERED', 'USER_PROVISIONED',
  'LOGIN_SUCCEEDED', 'LOGIN_FAILED',
]

export function AdminAudit() {
  const [f, setF] = useState<AuditFilters>({ q: '', action: '', entityType: '', actor: '', page: 0 })
  const [draft, setDraft] = useState({ q: '', actor: '' })
  const [open, setOpen] = useState<number | null>(null)
  const q = useAuditLogs(f)

  return (
    <>
      <PageHeader title="Audit trail" subtitle="Append-only: the database rejects edits and deletes. Every compliance result, score, override and retrain is here." />
      <form
        role="search"
        className="mb-4 grid gap-2 rounded-md bg-panel-raised p-3 ring-1 ring-rule sm:grid-cols-2 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto]"
        onSubmit={(e) => {
          e.preventDefault()
          setF({ ...f, ...draft, page: 0 })
        }}
      >
        <label className="sr-only" htmlFor="aq">Search</label>
        <Input id="aq" className="bg-paper" placeholder="Search action, entity or actor" value={draft.q} onChange={(e) => setDraft({ ...draft, q: e.target.value })} />
        <label className="sr-only" htmlFor="aa">Action</label>
        <Select id="aa" className="bg-paper" value={f.action} onChange={(e) => setF({ ...f, action: e.target.value, page: 0 })}>
          <option value="">All actions</option>
          {ACTIONS.map((a) => <option key={a} value={a}>{humanize(a)}</option>)}
        </Select>
        <label className="sr-only" htmlFor="ae">Entity</label>
        <Select id="ae" className="bg-paper" value={f.entityType} onChange={(e) => setF({ ...f, entityType: e.target.value, page: 0 })}>
          <option value="">All entities</option>
          {['LoanApplication', 'User', 'Model', 'Portfolio'].map((t) => <option key={t}>{t}</option>)}
        </Select>
        <label className="sr-only" htmlFor="ac">Actor</label>
        <Input id="ac" className="bg-paper" placeholder="Actor email" value={draft.actor} onChange={(e) => setDraft({ ...draft, actor: e.target.value })} />
        <Button type="submit" variant="ghost" className="border-rule bg-paper">Search</Button>
      </form>

      {q.isLoading && <Loading />}
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {q.data && (
        <div className="overflow-x-auto rounded-md bg-paper text-ink">
          <table className="w-full min-w-[48rem] text-sm">
            <caption className="sr-only">Audit log entries</caption>
            <thead className="border-b border-paper-rule text-left text-xs tracking-wide text-muted uppercase">
              <tr>
                <th className="w-8" />
                <th className="px-3 py-2 font-medium">When</th>
                <th className="px-3 py-2 font-medium">Action</th>
                <th className="px-3 py-2 font-medium">Entity</th>
                <th className="px-3 py-2 font-medium">Actor</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-paper-rule">
              {q.data.content.map((e) => (
                <Fragment key={e.id}>
                  <tr className="hover:bg-paper-deep">
                    <td className="pl-2">
                      <button aria-expanded={open === e.id} aria-label="Show state change" onClick={() => setOpen(open === e.id ? null : e.id)} className="grid size-6 place-items-center rounded hover:bg-paper-rule">
                        {open === e.id ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                      </button>
                    </td>
                    <td className="num px-3 py-2 text-xs whitespace-nowrap">{dateTime(e.createdAt)}</td>
                    <td className="px-3 py-2 font-medium">{humanize(e.action)}</td>
                    <td className="num px-3 py-2 text-xs">{e.entityType}{e.entityId ? ` #${e.entityId}` : ''}</td>
                    <td className="px-3 py-2 text-xs">{e.actorEmail} <span className="text-muted">({e.actorRole.toLowerCase()})</span></td>
                  </tr>
                  {open === e.id && (
                    <tr className="bg-paper-deep/60">
                      <td />
                      <td colSpan={4} className="grid gap-3 px-3 py-3 md:grid-cols-2">
                        <StateBox label="Before" value={e.beforeState} />
                        <StateBox label="After" value={e.afterState} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
          {q.data.content.length === 0 && <Empty>No audit entries match.</Empty>}
          <div className="flex items-center justify-between border-t border-paper-rule px-3 py-2 text-xs text-muted">
            <span className="num">{q.data.page.totalElements} entries · page {q.data.page.number + 1} of {Math.max(1, q.data.page.totalPages)}</span>
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

function StateBox({ label, value }: { label: string; value: unknown }) {
  return (
    <div>
      <p className="mb-1 text-xs font-medium tracking-wide text-muted uppercase">{label}</p>
      <pre className="num max-h-60 overflow-auto rounded bg-ink p-2 text-xs text-paper">{value == null ? '—' : JSON.stringify(value, null, 2)}</pre>
    </div>
  )
}
