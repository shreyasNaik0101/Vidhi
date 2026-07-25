// Baseline A (naive RAG) retriever for the live comparison view.
// Mirrors src/rbi/eval/naive.py: embed the question (nomic, query prefix) and
// return the single nearest chunk from the naive_chunk pgvector index — no entity
// or date filter. The index is built on the Python side (`make eval-index`).

const OLLAMA_HOST = process.env.OLLAMA_HOST || 'http://localhost:11434';
const EMBED_MODEL = process.env.EMBED_MODEL || 'nomic-embed-text-v2-moe:latest';
const QUERY_PREFIX = 'search_query: ';

export async function embedQuery(question) {
  const res = await fetch(`${OLLAMA_HOST}/api/embed`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: EMBED_MODEL, input: QUERY_PREFIX + question }),
  });
  if (!res.ok) throw new Error(`ollama embed failed: ${res.status}`);
  const data = await res.json();
  return data.embeddings[0];
}

export async function nearestChunk(pool, vec) {
  const literal = '[' + vec.map((x) => x.toFixed(6)).join(',') + ']';
  const { rows } = await pool.query(
    `SELECT entity_code, md_family, effective_date, issued_date, chunk_text
     FROM naive_chunk
     ORDER BY embedding <=> $1::vector
     LIMIT 1`,
    [literal],
  );
  return rows[0] || null;
}
