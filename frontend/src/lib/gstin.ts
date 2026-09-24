/** Mirrors the backend rules so users see problems before submitting. */
export const ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
export const GSTIN_SHAPE = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/
export const PAN_SHAPE = /^[A-Z]{3}[CPHFATBLJG][A-Z][0-9]{4}[A-Z]$/
export const UDYAM_SHAPE = /^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$/

export function checkCharacter(first14: string): string {
  let sum = 0
  for (let i = 0; i < 14; i++) {
    const value = ALPHABET.indexOf(first14[i])
    if (value < 0) throw new Error('invalid character')
    const product = value * (i % 2 === 0 ? 1 : 2)
    sum += Math.floor(product / 36) + (product % 36)
  }
  return ALPHABET[(36 - (sum % 36)) % 36]
}

export type GstinStatus = 'empty' | 'malformed' | 'checksum' | 'pan-mismatch' | 'state-mismatch' | 'ok'

/** Checks a GSTIN against the declared PAN and state, exactly as the compliance gate will. */
export function gstinStatus(raw: string, pan?: string, stateCode?: string): GstinStatus {
  const g = raw.trim().toUpperCase()
  if (!g) return 'empty'
  if (!GSTIN_SHAPE.test(g)) return 'malformed'
  if (checkCharacter(g.slice(0, 14)) !== g[14]) return 'checksum'
  if (pan && g.slice(2, 12) !== pan.trim().toUpperCase()) return 'pan-mismatch'
  if (stateCode && g.slice(0, 2) !== stateCode) return 'state-mismatch'
  return 'ok'
}

export const STATES: { code: string; name: string }[] = [
  ['01', 'Jammu and Kashmir'], ['02', 'Himachal Pradesh'], ['03', 'Punjab'], ['04', 'Chandigarh'],
  ['05', 'Uttarakhand'], ['06', 'Haryana'], ['07', 'Delhi'], ['08', 'Rajasthan'], ['09', 'Uttar Pradesh'],
  ['10', 'Bihar'], ['11', 'Sikkim'], ['12', 'Arunachal Pradesh'], ['13', 'Nagaland'], ['14', 'Manipur'],
  ['15', 'Mizoram'], ['16', 'Tripura'], ['17', 'Meghalaya'], ['18', 'Assam'], ['19', 'West Bengal'],
  ['20', 'Jharkhand'], ['21', 'Odisha'], ['22', 'Chhattisgarh'], ['23', 'Madhya Pradesh'], ['24', 'Gujarat'],
  ['26', 'Dadra and Nagar Haveli and Daman and Diu'], ['27', 'Maharashtra'], ['29', 'Karnataka'], ['30', 'Goa'],
  ['31', 'Lakshadweep'], ['32', 'Kerala'], ['33', 'Tamil Nadu'], ['34', 'Puducherry'],
  ['35', 'Andaman and Nicobar Islands'], ['36', 'Telangana'], ['37', 'Andhra Pradesh'], ['38', 'Ladakh'],
].map(([code, name]) => ({ code, name }))

export const stateName = (code: string) => STATES.find((s) => s.code === code)?.name ?? code
