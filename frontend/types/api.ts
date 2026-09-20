/**
 * Wire types mirroring the backend Pydantic schemas (`backend/app/schemas`).
 *
 * This file is a hand-maintained mirror: the backend is the source of truth for the
 * API contract (docs/API.md), and a change there must be reflected here.
 */

export type TrendStatusValue = "emerging" | "growing" | "stable" | "declining";

export type ProcessingStatusValue = "pending" | "classified" | "failed" | "skipped";

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface CategoryRef {
  id: number;
  slug: string;
  name: string;
}

export interface SourceRef {
  id: number;
  name: string;
}

export interface TopicRef {
  slug: string;
  name: string;
  /** True for the per-category `Other` bucket, which is a diagnostic, not a topic. */
  is_fallback?: boolean;
}

export interface TrendingTopicRef {
  slug: string;
  name: string;
  growth_rate: number;
  trend_score: number;
  status: TrendStatusValue;
}

export interface CategorySummary {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  topic_count: number;
  article_count: number;
  trending_topic: TrendingTopicRef | null;
}

export interface TrendSummary {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  summary: string | null;
  category: CategoryRef;
  trend_score: number;
  growth_rate: number;
  growth_percent: number;
  current_count: number;
  previous_count: number;
  volume_share: number;
  status: TrendStatusValue;
  is_emerging: boolean;
  snapshot_date: string;
  window_days: number;
}

export interface CategoryDetail extends CategorySummary {
  top_trends: TrendSummary[];
}

export interface ArticleSummary {
  id: number;
  title: string;
  url: string;
  published_at: string | null;
  source: SourceRef | null;
}

export interface ArticleDetail extends ArticleSummary {
  description: string | null;
  summary: string | null;
  created_at: string | null;
  processing_status: ProcessingStatusValue;
  category: CategoryRef | null;
  topics: TopicRef[];
}

export interface TrendDetail extends TrendSummary {
  latest_articles: ArticleSummary[];
  history_days: number;
}

export interface SnapshotPoint {
  date: string;
  current_count: number;
  previous_count: number;
  growth_rate: number;
  trend_score: number;
  status: TrendStatusValue;
}

export interface TrendHistory {
  slug: string;
  name: string;
  window_days: number | null;
  points: SnapshotPoint[];
}

export interface HealthResponse {
  status: string;
  database: string;
  scheduler: string;
  llm: string;
  version: string;
}

/** Query parameters accepted by `GET /api/trends`. */
export interface TrendQuery {
  category?: string;
  status?: TrendStatusValue;
  q?: string;
  min_growth?: number;
  sort?: TrendSortField;
  page?: number;
  page_size?: number;
}

export type TrendSortField =
  | "trend_score"
  | "growth_rate"
  | "article_count"
  | "volume_share"
  | "name"
  | "snapshot_date"
  | "-trend_score"
  | "-growth_rate"
  | "-article_count"
  | "-volume_share"
  | "-name"
  | "-snapshot_date";

/** Query parameters accepted by `GET /api/articles`. */
export interface ArticleQuery {
  category?: string;
  topic?: string;
  source_id?: number;
  q?: string;
  published_after?: string;
  published_before?: string;
  sort?: ArticleSortField;
  page?: number;
  page_size?: number;
}

export type ArticleSortField = "published_at" | "created_at" | "title" | "-published_at" | "-created_at" | "-title";
