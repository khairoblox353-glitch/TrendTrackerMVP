/**
 * Backend connection settings.
 *
 * `API_BASE_URL` is the address the Next.js **server** uses to reach FastAPI. Inside
 * Docker Compose that is the service name (`http://backend:8000`); on a developer
 * machine it is localhost. The browser never calls FastAPI directly, so no public
 * variable is required and the API needs no CORS configuration in practice (the CORS
 * allow-list exists for tooling such as `/docs` and curl from a browser session).
 */

export const API_BASE_URL =
  process.env.API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export const API_PREFIX = "/api";

// Reads are uncached (`cache: "no-store"` in lib/api.ts). The dashboard reflects the
// database as it is now, and because a build can run before the database is seeded,
// caching a response would risk pinning an empty snapshot.
export function apiUrl(path: string): string {
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${API_PREFIX}${suffix}`;
}
