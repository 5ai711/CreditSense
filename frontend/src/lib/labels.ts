import type { CheckType, DocumentType, LoanPurpose, Sector, Status } from './types'

export const SECTORS: { value: Sector; label: string }[] = [
  { value: 'MANUFACTURING', label: 'Manufacturing' },
  { value: 'TRADING', label: 'Trading' },
  { value: 'SERVICES', label: 'Services' },
  { value: 'RETAIL', label: 'Retail' },
  { value: 'AGRI_ALLIED', label: 'Agri-allied' },
  { value: 'HOSPITALITY', label: 'Hospitality' },
]
export const sectorLabel = (s: Sector) => SECTORS.find((x) => x.value === s)?.label ?? s

export const PURPOSES: { value: LoanPurpose; label: string }[] = [
  { value: 'WORKING_CAPITAL', label: 'Working capital' },
  { value: 'EQUIPMENT', label: 'Equipment purchase' },
  { value: 'EXPANSION', label: 'Business expansion' },
  { value: 'INVENTORY', label: 'Inventory' },
  { value: 'REFINANCE', label: 'Refinance existing debt' },
]
export const purposeLabel = (p: LoanPurpose) => PURPOSES.find((x) => x.value === p)?.label ?? p

export const STATUS_LABEL: Record<Status, string> = {
  SUBMITTED: 'Submitted',
  COMPLIANCE_REVIEW: 'Compliance cleared',
  COMPLIANCE_FAILED: 'Compliance failed',
  RISK_SCORED: 'Awaiting decision',
  MANUAL_REVIEW: 'Manual review',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
}

export const CHECK_LABEL: Record<CheckType, string> = {
  GST_VALIDITY: 'GST registration',
  KYC_COMPLETENESS: 'KYC completeness',
  DUPLICATE_PAN: 'Duplicate PAN',
  ADDRESS_MISMATCH: 'Address matches GST state',
  BLACKLIST: 'Blacklist screening',
  VELOCITY: 'Application frequency',
}

export const DOC_LABEL: Record<DocumentType, string> = {
  PAN: 'PAN card',
  UDYAM: 'Udyam registration',
  ADDRESS_PROOF: 'Address proof',
  BANK_STATEMENT: 'Bank statements',
  GST_CERTIFICATE: 'GST certificate',
}
