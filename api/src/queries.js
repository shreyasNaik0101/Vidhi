// Read queries over the clause timeline. SQL does the coarse filtering; the
// temporal decision happens in resolve.js.

export async function listEntities(pool) {
  const { rows } = await pool.query(
    'SELECT code, name FROM entity_type ORDER BY id',
  );
  return rows;
}

/** Clause versions for an entity+family (optionally one clause), mapped to camelCase. */
export async function loadClauseVersions(pool, { mdFamily, entityCode, clauseNumber }) {
  const params = [mdFamily, entityCode];
  let sql = `
    SELECT c.md_family, e.code, c.clause_number, c.sort_key, c.chapter,
           c.text, c.valid_from, c.valid_to
    FROM clause c
    JOIN entity_type e ON e.id = c.entity_type_id
    WHERE c.md_family = $1 AND e.code = $2`;
  if (clauseNumber) {
    sql += ' AND c.clause_number = $3';
    params.push(clauseNumber);
  }
  sql += ' ORDER BY c.sort_key, c.valid_from';

  const { rows } = await pool.query(sql, params);
  return rows.map((r) => ({
    mdFamily: r.md_family,
    entityCode: r.code,
    clauseNumber: r.clause_number,
    sortKey: r.sort_key,
    chapter: r.chapter,
    text: r.text,
    validFrom: r.valid_from,
    validTo: r.valid_to,
  }));
}

/** Distinct clause numbers available for an entity+family (for UI pickers). */
export async function listClauses(pool, { mdFamily, entityCode }) {
  const { rows } = await pool.query(
    `SELECT DISTINCT c.clause_number, c.sort_key, c.chapter
     FROM clause c JOIN entity_type e ON e.id = c.entity_type_id
     WHERE c.md_family = $1 AND e.code = $2
     ORDER BY c.sort_key`,
    [mdFamily, entityCode],
  );
  return rows.map((r) => ({
    clauseNumber: r.clause_number,
    chapter: r.chapter,
  }));
}

/** Every version of one clause, with the amendment that created and closed each. */
export async function clauseTimeline(pool, { mdFamily, entityCode, clauseNumber }) {
  const { rows } = await pool.query(
    `SELECT c.clause_number, c.chapter, c.text, c.valid_from, c.valid_to,
            cd.rbi_ref AS created_by, sd.rbi_ref AS superseded_by
     FROM clause c
     JOIN entity_type e ON e.id = c.entity_type_id
     LEFT JOIN amendment_op cop ON cop.id = c.created_by_op_id
     LEFT JOIN document cd ON cd.id = cop.amendment_doc_id
     LEFT JOIN amendment_op sop ON sop.id = c.superseded_by_op_id
     LEFT JOIN document sd ON sd.id = sop.amendment_doc_id
     WHERE c.md_family = $1 AND e.code = $2 AND c.clause_number = $3
     ORDER BY c.valid_from`,
    [mdFamily, entityCode, clauseNumber],
  );
  return rows.map((r) => ({
    clauseNumber: r.clause_number,
    chapter: r.chapter,
    text: r.text,
    validFrom: r.valid_from,
    validTo: r.valid_to,
    createdBy: r.created_by,
    supersededBy: r.superseded_by,
  }));
}

/** Change feed: groups of the same change across entities, newest issue date first. */
export async function changeFeed(pool) {
  const { rows } = await pool.query(
    `SELECT cg.id, cg.label, cg.issued_date, cg.effective_date,
            e.code AS entity_code, d.rbi_ref, cgm.similarity,
            ao.target_chapter, ao.section_heading, ao.new_text
     FROM change_group cg
     JOIN change_group_member cgm ON cgm.change_group_id = cg.id
     JOIN amendment_op ao ON ao.id = cgm.amendment_op_id
     JOIN document d ON d.id = ao.amendment_doc_id
     JOIN entity_type e ON e.id = ao.target_entity_type
     ORDER BY cg.issued_date DESC, cg.id, e.code`,
  );

  const groups = new Map();
  for (const r of rows) {
    if (!groups.has(r.id)) {
      groups.set(r.id, {
        id: r.id,
        label: r.label,
        issuedDate: r.issued_date,
        effectiveDate: r.effective_date,
        members: [],
      });
    }
    groups.get(r.id).members.push({
      entityCode: r.entity_code,
      rbiRef: r.rbi_ref,
      chapter: r.target_chapter,
      sectionHeading: r.section_heading,
      similarity: r.similarity === null ? null : Number(r.similarity),
    });
  }
  return [...groups.values()];
}
