import { render, screen } from '@testing-library/react'
import { Ledger } from './Ledger'

const contributions = [
  { feature: 'revenue_volatility', featureValue: 0.78, shapContribution: 0.84 },
  { feature: 'gst_filing_consistency', featureValue: 0.91, shapContribution: -0.56 },
  { feature: 'loan_to_revenue', featureValue: 0.23, shapContribution: -0.001 },
]
const base = -1.75
const logit = base + 0.84 - 0.56 - 0.001
const pd = 1 / (1 + Math.exp(-logit))

describe('Ledger', () => {
  it('lists every line item in plain language, largest first', () => {
    render(<Ledger baseValue={base} contributions={contributions} probabilityOfDefault={pd} audience="applicant" />)
    const items = screen.getAllByRole('listitem')
    expect(items[0]).toHaveAccessibleName(/revenue swings by about 78%.*raises risk by 0.84/i)
    expect(items[1]).toHaveAccessibleName(/91% of GST returns filed on time.*lowers risk by 0.56/i)
    expect(items[2]).toHaveAccessibleName(/no effect on risk/i)
  })

  it('balances: opening balance plus line items equals the score', () => {
    render(<Ledger baseValue={base} contributions={contributions} probabilityOfDefault={pd} audience="applicant" />)
    expect(screen.getByText('−1.75')).toBeInTheDocument()
    expect(screen.getByText(`${logit >= 0 ? '+' : '−'}${Math.abs(logit).toFixed(2)} → ${(pd * 100).toFixed(1)}%`)).toBeInTheDocument()
  })

  it('shows raw values only to officers', () => {
    const { rerender } = render(<Ledger baseValue={base} contributions={contributions} probabilityOfDefault={pd} audience="applicant" />)
    expect(screen.queryByText('0.78')).not.toBeInTheDocument()
    rerender(<Ledger baseValue={base} contributions={contributions} probabilityOfDefault={pd} audience="officer" />)
    expect(screen.getByText('0.78')).toBeInTheDocument()
  })
})
