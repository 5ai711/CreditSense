import { lakh } from './format'

interface FeatureMeta {
  label: string
  /** The raw value, formatted for the ledger's value column. */
  value: (v: number | string) => string
  /** A plain-language statement of what the value means for this applicant. */
  says: (v: number | string) => string
}

const n = (v: number | string) => (typeof v === 'number' ? v : Number(v))
const p0 = (v: number) => `${Math.round(v * 100)}%`

export const FEATURES: Record<string, FeatureMeta> = {
  business_vintage: {
    label: 'Business vintage',
    value: (v) => `${n(v).toFixed(1)} yr`,
    says: (v) => `In business for ${n(v).toFixed(1)} years`,
  },
  monthly_revenue: {
    label: 'Monthly revenue',
    value: (v) => lakh(n(v)),
    says: (v) => `Average monthly revenue of ${lakh(n(v))}`,
  },
  revenue_volatility: {
    label: 'Revenue volatility',
    value: (v) => n(v).toFixed(2),
    says: (v) => `Monthly revenue swings by about ${p0(n(v))} around its average`,
  },
  gst_filing_consistency: {
    label: 'GST filing consistency',
    value: (v) => p0(n(v)),
    says: (v) => `${p0(n(v))} of GST returns filed on time in the last year`,
  },
  debt_to_revenue: {
    label: 'Debt-to-revenue',
    value: (v) => n(v).toFixed(2),
    says: (v) => `Existing debt equals ${p0(n(v))} of annual revenue`,
  },
  inflow_outflow_ratio: {
    label: 'Inflow / outflow',
    value: (v) => `${n(v).toFixed(2)}×`,
    says: (v) =>
      n(v) >= 1
        ? `Money coming in is ${n(v).toFixed(2)}× money going out`
        : `Spending exceeds income: only ${n(v).toFixed(2)}× of outflow comes back in`,
  },
  balance_cover: {
    label: 'Balance cover',
    value: (v) => `${n(v).toFixed(2)} mo`,
    says: (v) => `Average bank balance covers ${n(v).toFixed(1)} months of spending`,
  },
  trade_references: {
    label: 'Trade references',
    value: (v) => `${n(v)}`,
    says: (v) => `${n(v)} active supplier ${n(v) === 1 ? 'reference' : 'references'}`,
  },
  delinquency_events: {
    label: 'Past delinquencies',
    value: (v) => `${n(v)}`,
    says: (v) => (n(v) === 0 ? 'No past repayment delays on record' : `${n(v)} past repayment ${n(v) === 1 ? 'delay' : 'delays'} on record`),
  },
  loan_to_revenue: {
    label: 'Loan-to-revenue',
    value: (v) => n(v).toFixed(2),
    says: (v) => `Amount requested is ${p0(n(v))} of annual revenue`,
  },
  kyc_completeness: {
    label: 'KYC completeness',
    value: (v) => p0(n(v)),
    says: (v) => `KYC documents ${p0(n(v))} complete`,
  },
  digital_txn_volume: {
    label: 'Digital payments',
    value: (v) => `${Math.round(n(v))}/mo`,
    says: (v) => `${Math.round(n(v))} digital (UPI) payments a month`,
  },
  sector: {
    label: 'Sector',
    value: (v) => String(v),
    says: (v) => `Operates in ${String(v).toLowerCase()}`,
  },
}

export const featureMeta = (name: string): FeatureMeta =>
  FEATURES[name] ?? { label: name, value: (v) => String(v), says: (v) => `${name}: ${v}` }
