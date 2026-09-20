/**
 * Typed server-side API client.
 *
 * Every page and component reads data through these functions, so the wire format is
 * validated in exactly one place. All reads are `no-store`: the dashboard must reflect the
 * database as it is now, and prefetch builds the frontend before the database is seeded,
 * so any cached response would be an empty snapshot. Every failure returns a typed result
 * rather than throwing, so a page can render an honest error state instead of crashing
 * when the backend is down.
 */

import { apiUrl } from "@/lib/config";
import type {
  ArticleDetail,
  ArticleQuery,
  CategoryDetail,
  CategorySummary,
  Page,
  TrendDetail,
  TrendHistory,
  TrendQuery,
  TrendSummary,
} from "@/types/api";

export interface ApiFailure {
  ok: false;
  status: number;
  message: string;
}

export interface ApiSuccess<T> {
  ok: true;
  data: T;
}

export type ApiResult<T> = ApiSuccess<T> | ApiFailure;

const DEFAULT_TIMEOUT_MS = 8000;

function buildQuery(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

/** Extract a readable message from the backend error envelope. */
async function messageFrom(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { error?: { message?: string } };
    if (body?.error?.message) return body.error.message;
  } catch {
    // Non-JSON error bodies (proxies, gateways) fall through to the status text.
  }
  return response.statusText || `Request failed with status ${response.status}`;
}

async function request<T>(
  path: string,
  { allowNoContent = false }: { allowNoContent?: boolean } = {},
): Promise<ApiResult<T | null>> {
  const url = apiUrl(path);

  try {
    const response = await fetch(url, {
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
    });

    if (allowNoContent && response.status === 204) {
      return { ok: true, data: null };
    }

    if (!response.ok) {
      return { ok: false, status: response.status, message: await messageFrom(response) };
    }

    return { ok: true, data: (await response.json()) as T };
  } catch (error) {
    const message =
      error instanceof Error && error.name === "TimeoutError"
        ? "The API did not respond in time."
        : "Could not reach the API.";
    return { ok: false, status: 0, message };
  }
}

// ---------------------------------------------------------------------------
// Reads
// ---------------------------------------------------------------------------
export function getCategories(): Promise<ApiResult<CategorySummary[]>> {
  return request<CategorySummary[]>("/categories") as Promise<ApiResult<CategorySummary[]>>;
}

export function getCategory(slug: string): Promise<ApiResult<CategoryDetail>> {
  return request<CategoryDetail>(`/categories/${encodeURIComponent(slug)}`) as Promise<
    ApiResult<CategoryDetail>
  >;
}

export function getTrends(query: TrendQuery = {}): Promise<ApiResult<Page<TrendSummary>>> {
  const qs = buildQuery({
    category: query.category,
    status: query.status,
    q: query.q,
    min_growth: query.min_growth,
    sort: query.sort,
    page: query.page,
    page_size: query.page_size,
  });
  return request<Page<TrendSummary>>(`/trends${qs}`) as Promise<ApiResult<Page<TrendSummary>>>;
}

export function getTrend(slug: string): Promise<ApiResult<TrendDetail>> {
  return request<TrendDetail>(`/trends/${encodeURIComponent(slug)}`) as Promise<
    ApiResult<TrendDetail>
  >;
}

/** Returns `null` (not a failure) when the topic has no snapshots yet: HTTP 204. */
export function getTrendHistory(
  slug: string,
  days = 30,
  windowDays?: number,
): Promise<ApiResult<TrendHistory | null>> {
  const qs = buildQuery({ days, window_days: windowDays });
  return request<TrendHistory | null>(`/trends/${encodeURIComponent(slug)}/history${qs}`, {
    allowNoContent: true,
  });
}

export function getArticles(query: ArticleQuery = {}): Promise<ApiResult<Page<ArticleDetail>>> {
  const qs = buildQuery({
    category: query.category,
    topic: query.topic,
    source_id: query.source_id,
    q: query.q,
    published_after: query.published_after,
    published_before: query.published_before,
    sort: query.sort,
    page: query.page,
    page_size: query.page_size,
  });
  return request<Page<ArticleDetail>>(`/articles${qs}`) as Promise<
    ApiResult<Page<ArticleDetail>>
  >;
}

export function getArticle(id: number | string): Promise<ApiResult<ArticleDetail>> {
  // The route param is a string, but the API contract is a positive integer. A bad id is
  // rejected here instead of being interpolated: an unencoded `..` segment would let the
  // URL normalize past the `/api/articles` prefix on the internal backend host.
  const numericId = typeof id === "number" ? id : Number(id);
  if (!Number.isInteger(numericId) || numericId < 1) {
    return Promise.resolve({
      ok: false,
      status: 400,
      message: `Invalid article id: ${id}`,
    } satisfies ApiFailure);
  }

  return request<ArticleDetail>(`/articles/${encodeURIComponent(numericId)}`) as Promise<
    ApiResult<ArticleDetail>
  >;
}

/** Convenience accessor used by pages that must render something on failure. */
export function orEmpty<T>(result: ApiResult<T>, fallback: T): T {
  return result.ok ? result.data : fallback;
}
