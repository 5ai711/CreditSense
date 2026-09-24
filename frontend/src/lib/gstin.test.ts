import { ALPHABET, checkCharacter, gstinStatus } from './gstin'

describe('GSTIN rules (mirror of the backend compliance gate)', () => {
  it('computes the documented check character', () => {
    expect(checkCharacter('27AAPFU0939F1Z')).toBe('V')
    expect(gstinStatus('27AAPFU0939F1ZV')).toBe('ok')
    expect(gstinStatus(' 27aapfu0939f1zv ')).toBe('ok')
  })

  it('catches every single-character substitution', () => {
    const valid = '27AAPFU0939F1ZV'
    for (let pos = 0; pos < 15; pos++) {
      for (const c of ALPHABET) {
        if (c === valid[pos]) continue
        const mutated = valid.slice(0, pos) + c + valid.slice(pos + 1)
        expect(gstinStatus(mutated)).not.toBe('ok')
      }
    }
  })

  it('reports why a GSTIN will fail the gate', () => {
    expect(gstinStatus('')).toBe('empty')
    expect(gstinStatus('27AAPFU0939F1YV')).toBe('malformed')
    expect(gstinStatus('27AAPFU0939F1ZW')).toBe('checksum')
    expect(gstinStatus('27AAPFU0939F1ZV', 'AAPFU0939G')).toBe('pan-mismatch')
    expect(gstinStatus('27AAPFU0939F1ZV', 'AAPFU0939F', '36')).toBe('state-mismatch')
  })
})
