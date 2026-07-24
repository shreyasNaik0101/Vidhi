// Ported-resolver tests — mirror tests/test_apply.py so JS and Python agree.
import { describe, it, expect } from 'vitest';
import { resolve } from '../src/resolve.js';

const EFF = '2026-10-01';

function v(entityCode, clauseNumber, text, validFrom = EFF, validTo = null) {
  return { mdFamily: 'IRACP', entityCode, clauseNumber, text, validFrom, validTo };
}

const RRB_LAB = [
  v('RRB', '68C', 'RRB accrued interest text'),
  v('RRB', '68D', 'RRB income text'),
  v('LAB', '119C', 'LAB accrued interest text'),
  v('LAB', '119D', 'LAB income text'),
];

const ask = (versions, entityCode, clauseNumber, asOf) =>
  resolve(versions, { mdFamily: 'IRACP', entityCode, clauseNumber, asOf });

describe('the date flip', () => {
  it('is not_yet_in_force before the effective date', () => {
    const r = ask(RRB_LAB, 'RRB', '68C', '2026-09-30');
    expect(r.status).toBe('not_yet_in_force');
    expect(r.effectiveDate).toBe(EFF);
    expect(r.text).toBeNull();
    expect(r.candidates.length).toBe(1); // abstention shows what it considered
  });

  it('is in_force on and after the effective date', () => {
    expect(ask(RRB_LAB, 'RRB', '68C', EFF).status).toBe('in_force');
    const r = ask(RRB_LAB, 'RRB', '68C', '2026-10-02');
    expect(r.status).toBe('in_force');
    expect(r.text).toBe('RRB accrued interest text');
  });
});

describe('entity isolation', () => {
  it('abstains when an RRB is asked with a LAB clause number', () => {
    const r = ask(RRB_LAB, 'RRB', '119C', '2026-10-02');
    expect(r.status).toBe('no_provision');
    expect(r.text).toBeNull();
  });

  it('resolves the same-shaped question per entity', () => {
    expect(ask(RRB_LAB, 'LAB', '119C', '2026-10-02').text).toBe('LAB accrued interest text');
  });
});

describe('substitute and omit over time', () => {
  it('returns the version in force at the asked date', () => {
    const versions = [
      v('RRB', '68C', 'original text', EFF, '2027-01-01'),
      v('RRB', '68C', 'revised text', '2027-01-01', null),
    ];
    expect(ask(versions, 'RRB', '68C', '2026-12-01').text).toBe('original text');
    expect(ask(versions, 'RRB', '68C', '2027-02-01').text).toBe('revised text');
  });

  it('reports no_longer_in_force after a clause is closed with no successor', () => {
    const versions = [v('RRB', '68C', 'original', EFF, '2027-01-01')];
    const r = ask(versions, 'RRB', '68C', '2027-02-01');
    expect(r.status).toBe('no_longer_in_force');
    expect(r.text).toBeNull();
  });
});

describe('non-existent clause', () => {
  it('abstains with no_provision', () => {
    expect(ask(RRB_LAB, 'RRB', '999Z', '2026-10-02').status).toBe('no_provision');
  });
});
