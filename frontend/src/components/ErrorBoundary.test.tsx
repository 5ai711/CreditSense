import { render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { ErrorBoundary } from './ErrorBoundary'

function Broken(): never {
  throw new Error('chunk failed to load')
}

it('shows a recovery screen instead of a blank page when rendering fails', () => {
  const quiet = vi.spyOn(console, 'error').mockImplementation(() => {})
  render(<ErrorBoundary><Broken /></ErrorBoundary>)
  expect(screen.getByRole('alert')).toHaveTextContent('This page could not be shown')
  expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument()
  quiet.mockRestore()
})
