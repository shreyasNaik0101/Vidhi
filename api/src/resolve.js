// Port of rbi.apply.resolve (Python) — the as-of resolver, verified by its own tests.
// Kept behaviourally identical so Python and JS agree on the answer.
//
// Dates are ISO strings ('YYYY-MM-DD'); string comparison orders them correctly,
// so we avoid Date objects and timezone surprises entirely.

/** @typedef {Object} ClauseVersion
 *  @property {string} mdFamily
 *  @property {string} entityCode
 *  @property {string} clauseNumber
 *  @property {string} text
 *  @property {string} validFrom  ISO date
 *  @property {string|null} validTo ISO date or null (still in force)
 */

export const ANSWERABLE = new Set(['in_force', 'equivalence', 'cascade']);

/**
 * Resolve what a clause says for an entity on a date. Never guesses: if nothing is
 * in force it abstains with a status explaining why, plus the candidates considered.
 */
export function resolve(versions, { mdFamily, entityCode, clauseNumber, asOf }) {
  // Entity + clause filter FIRST — semantics never cross entity types.
  const candidates = versions
    .filter(
      (v) =>
        v.mdFamily === mdFamily &&
        v.entityCode === entityCode &&
        v.clauseNumber === clauseNumber,
    )
    .sort((a, b) => (a.validFrom < b.validFrom ? -1 : a.validFrom > b.validFrom ? 1 : 0));

  const base = { mdFamily, entityCode, clauseNumber, asOf, candidates };

  if (candidates.length === 0) {
    return {
      ...base,
      status: 'no_provision',
      text: null,
      validFrom: null,
      validTo: null,
      effectiveDate: null,
      note: `clause ${clauseNumber} does not exist for ${entityCode}`,
    };
  }

  for (const v of candidates) {
    if (v.validFrom <= asOf && (v.validTo === null || v.validTo > asOf)) {
      return {
        ...base,
        status: 'in_force',
        text: v.text,
        validFrom: v.validFrom,
        validTo: v.validTo,
        effectiveDate: null,
        note: null,
        sourceRef: v.sourceRef ?? null,
        issuedDate: v.issuedDate ?? null,
      };
    }
  }

  const future = candidates.filter((v) => v.validFrom > asOf);
  if (future.length > 0) {
    const soonest = future.reduce((a, b) => (a.validFrom < b.validFrom ? a : b));
    return {
      ...base,
      status: 'not_yet_in_force',
      text: null,
      validFrom: null,
      validTo: null,
      effectiveDate: soonest.validFrom,
      note:
        `clause ${clauseNumber} was issued but comes into force ${soonest.validFrom}; ` +
        `on ${asOf} the prior text (if any) applies`,
    };
  }

  const latest = candidates.reduce((a, b) => (a.validFrom > b.validFrom ? a : b));
  return {
    ...base,
    status: 'no_longer_in_force',
    text: null,
    validFrom: null,
    validTo: latest.validTo,
    effectiveDate: null,
    note: `clause ${clauseNumber} was closed on ${latest.validTo}`,
  };
}
