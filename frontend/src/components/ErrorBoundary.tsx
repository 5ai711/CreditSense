import { AlertTriangle } from 'lucide-react'
import { Component, type ErrorInfo, type ReactNode } from 'react'

/**
 * Last line of defence: a rendering error shows a way out instead of a blank page. The usual cause after a
 * deployment is a page chunk that no longer exists, which a reload fixes.
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('CreditSense UI error', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <main className="grid min-h-dvh place-items-center bg-ink p-6 text-paper">
        <div role="alert" className="max-w-md rounded-md bg-panel p-6 ring-1 ring-risk/50">
          <p className="flex items-center gap-2 font-display text-lg">
            <AlertTriangle aria-hidden className="size-5 text-risk" /> This page could not be shown
          </p>
          <p className="mt-2 text-sm text-fog">
            Reloading usually fixes this, for example after CreditSense has been updated. Anything you had not yet
            submitted may need to be entered again.
          </p>
          <div className="mt-5 flex gap-3">
            <button
              onClick={() => window.location.reload()}
              className="rounded bg-amber px-4 py-2 text-sm font-medium text-ink hover:brightness-110"
            >
              Reload
            </button>
            <a href="/" className="rounded px-4 py-2 text-sm text-fog ring-1 ring-fog/40 hover:text-paper">
              Go to start
            </a>
          </div>
        </div>
      </main>
    )
  }
}
