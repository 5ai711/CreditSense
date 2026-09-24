import clsx from 'clsx'
import { AlertTriangle, Loader2 } from 'lucide-react'
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { forwardRef } from 'react'
import { toApiError } from '../lib/api'

export function Card({ title, action, children, className, dark }: {
  title?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
  dark?: boolean
}) {
  return (
    <section
      className={clsx(
        'rounded-md',
        dark ? 'bg-panel-raised text-paper ring-1 ring-rule' : 'bg-paper text-ink shadow-[0_1px_0_rgba(0,0,0,0.25)]',
        className,
      )}
    >
      {(title || action) && (
        <header className={clsx('flex items-center justify-between gap-3 border-b px-4 py-3', dark ? 'border-rule' : 'border-paper-rule')}>
          <h2 className="text-sm font-semibold tracking-wide uppercase">{title}</h2>
          {action}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  )
}

type Variant = 'primary' | 'approve' | 'reject' | 'ghost' | 'quiet'

export function Button({ variant = 'primary', busy, className, children, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  busy?: boolean
}) {
  return (
    <button
      {...rest}
      disabled={rest.disabled || busy}
      className={clsx(
        'inline-flex items-center justify-center gap-2 rounded px-3.5 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50',
        variant === 'primary' && 'bg-ink text-paper hover:bg-panel',
        variant === 'approve' && 'bg-confirm text-white hover:bg-confirm-deep',
        variant === 'reject' && 'bg-risk text-white hover:bg-risk-deep',
        variant === 'ghost' && 'border border-paper-rule text-ink hover:bg-paper-deep',
        variant === 'quiet' && 'text-fog hover:text-paper',
        className,
      )}
    >
      {busy && <Loader2 aria-hidden className="size-4 animate-spin" />}
      {children}
    </button>
  )
}

export function Field({ label, error, hint, htmlFor, children }: { label: string; error?: string; hint?: ReactNode; htmlFor: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={htmlFor} className="text-xs font-medium tracking-wide text-muted uppercase">
        {label}
      </label>
      {children}
      {error ? (
        <p role="alert" className="text-xs text-risk-deep">{error}</p>
      ) : hint ? (
        <div className="text-xs text-muted">{hint}</div>
      ) : null}
    </div>
  )
}

const inputClass =
  'w-full rounded border border-paper-rule bg-white/70 px-3 py-2 text-sm text-ink placeholder:text-muted/70 focus:border-ink focus:outline-none aria-[invalid=true]:border-risk'

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...p }, ref) {
  return <input ref={ref} {...p} className={clsx(inputClass, className)} />
})

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select({ className, ...p }, ref) {
  return <select ref={ref} {...p} className={clsx(inputClass, className)} />
})

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className, ...p }, ref) {
  return <textarea ref={ref} {...p} className={clsx(inputClass, className)} />
})

export function Loading({ label = 'Loading' }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 p-6 text-sm text-fog">
      <Loader2 aria-hidden className="size-4 animate-spin" /> {label}…
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const e = toApiError(error)
  return (
    <div role="alert" className="flex items-start gap-3 rounded-md bg-risk/15 p-4 text-sm text-paper ring-1 ring-risk/50">
      <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0 text-risk" />
      <div className="flex-1">
        <p className="font-medium">Something went wrong</p>
        <p className="text-fog">{e.message}</p>
      </div>
      {onRetry && (
        <button onClick={onRetry} className="text-xs font-medium text-amber underline">
          Retry
        </button>
      )}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="p-6 text-center text-sm text-fog">{children}</p>
}

export function PageHeader({ title, subtitle, action }: { title: ReactNode; subtitle?: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold text-paper">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-fog">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

export function Kpi({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: 'risk' | 'confirm' | 'amber' }) {
  return (
    <div className="rounded-md bg-ink px-4 py-3 ring-1 ring-rule">
      <p className="text-[11px] font-medium tracking-wider text-fog uppercase">{label}</p>
      <p
        className={clsx(
          'num mt-1 text-2xl text-paper',
          tone === 'risk' && 'text-risk',
          tone === 'confirm' && 'text-[#6fb68a]',
          tone === 'amber' && 'text-amber',
        )}
      >
        {value}
      </p>
      {sub && <p className="num mt-0.5 text-xs text-fog">{sub}</p>}
    </div>
  )
}
