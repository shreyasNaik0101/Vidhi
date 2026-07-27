// Ask extraction — the who/when/clause parsing that drives the natural-language box.
import { describe, it, expect } from 'vitest';
import { extractEntity, extractDate, extractClause } from '../src/ask.js';

describe('extractEntity', () => {
  it('maps common phrasings to codes', () => {
    expect(extractEntity('rule for a Regional Rural Bank')).toBe('RRB');
    expect(extractEntity('what about rural banks?')).toBe('RRB');
    expect(extractEntity('a Local Area Bank')).toBe('LAB');
    expect(extractEntity('small finance bank query')).toBe('SFB');
    expect(extractEntity('for commercial banks')).toBe('SCB');
    expect(extractEntity('an NBFC')).toBe('NBFC');
  });

  it('does not confuse rural co-operative with rural bank', () => {
    expect(extractEntity('rural co-operative banks')).toBe('RCB');
    expect(extractEntity('urban cooperative banks')).toBe('UCB');
  });

  it('returns null when no entity is named', () => {
    expect(extractEntity('what is the SNFA rule')).toBeNull();
    expect(extractEntity('')).toBeNull();
  });
});

describe('extractDate', () => {
  it('parses explicit formats', () => {
    expect(extractDate('as of 2026-10-01')).toBe('2026-10-01');
    expect(extractDate('on 2026/10/1')).toBe('2026-10-01');
    expect(extractDate('in November 2026')).toBe('2026-11-01');
    expect(extractDate('October 15, 2026')).toBe('2026-10-15');
    expect(extractDate('October 1st, 2026')).toBe('2026-10-01');
    expect(extractDate('15 November 2026')).toBe('2026-11-15');
    expect(extractDate('1st of April 2027')).toBe('2027-04-01');
  });

  it('handles today/now', () => {
    const today = new Date().toISOString().slice(0, 10);
    expect(extractDate('what is it today?')).toBe(today);
    expect(extractDate('right now')).toBe(today);
  });

  it('returns null when no date and ignores non-month words', () => {
    expect(extractDate('rule for a rural bank')).toBeNull();
    // "sections 21 ... 1949" must not be read as a date
    expect(extractDate('under sections 21 and 35A of the Act, 1949')).toBeNull();
  });
});

describe('extractClause', () => {
  it('reads clause references and bare numbers', () => {
    expect(extractClause('what does clause 68C say')).toBe('68C');
    expect(extractClause('para 119D')).toBe('119D');
    expect(extractClause('tell me about 133C')).toBe('133C');
    expect(extractClause('clause 68c lowercase')).toBe('68C');
  });

  it('returns null when no clause number is present', () => {
    expect(extractClause('how is SNFA income treated')).toBeNull();
  });
});
