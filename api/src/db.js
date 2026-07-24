// Postgres connection pool. Reads the same DB the Python pipeline fills.
import pg from 'pg';
import dotenv from 'dotenv';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
// Load the repo-root .env if present (api/ is one level down).
dotenv.config({ path: path.resolve(__dirname, '..', '..', '.env') });

// node-postgres parses DATE (oid 1082) into a JS Date at local midnight, which
// invites timezone bugs. Keep dates as raw 'YYYY-MM-DD' strings — resolve.js
// compares them lexicographically.
pg.types.setTypeParser(1082, (v) => v);

const connectionString =
  process.env.DATABASE_URL || 'postgresql://rbi:rbi@localhost:5433/rbi';

export const pool = new pg.Pool({ connectionString });

export async function ping() {
  const { rows } = await pool.query('SELECT 1 AS ok');
  return rows[0].ok === 1;
}
