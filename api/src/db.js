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

// Use 127.0.0.1, not localhost: Node resolves localhost to IPv6 (::1) first, and the
// Docker/WSL2 IPv6 port mapping is unreliable — IPv4 is stable.
const connectionString =
  process.env.DATABASE_URL || 'postgresql://rbi:rbi@127.0.0.1:5433/rbi';

// keepAlive stops the WSL2/Docker network relay from silently dropping idle
// connections; idleTimeoutMillis recycles them so the pool never hands out a dead
// socket. The error handler keeps a dropped backend connection from crashing the API.
export const pool = new pg.Pool({
  connectionString,
  keepAlive: true,
  idleTimeoutMillis: 30_000,
  max: 10,
});
pool.on('error', (err) => console.error('pg pool error (recovered):', err.message));

export async function ping() {
  const { rows } = await pool.query('SELECT 1 AS ok');
  return rows[0].ok === 1;
}
