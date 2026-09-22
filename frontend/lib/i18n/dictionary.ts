/**
 * Static UI dictionaries for the EN/VI locale toggle.
 *
 * `Dictionary` is an explicit object type literal (not `typeof en`) so a missing or
 * misspelled key in either locale is a compile error. The functions are string builders,
 * not formatting rules: every number, status and score still comes from the backend.
 *
 * EN text is the single source of truth and must stay byte-for-byte identical to the
 * strings that were hardcoded in the components before i18n.
 */

import type { TrendStatusValue } from "@/types/api";

/** Locales with a complete dictionary. Language codes themselves are never translated. */
export type Locale = "en" | "vi";

export type Dictionary = {
  nav: {
    allTrends: string;
    mainLabel: string;
    languageLabel: string;
  };
  footer: {
    tagline: string;
    dataVia: string;
    backend: string;
  };
  common: {
    home: string;
    articles: string;
    latestArticles: string;
    all: string;
    categoriesLabel: string;
    breadcrumbLabel: string;
    paginationLabel: string;
    sortLabel: string;
    statusLabel: string;
    search: string;
    apply: string;
    previous: string;
    next: string;
    tryAgain: string;
    unknownSource: string;
    noArticlesYet: string;
    notEnoughData: string;
    pageOf: (page: number, pages: number) => string;
  };
  status: {
    labels: Record<TrendStatusValue, string>;
    descriptions: Record<TrendStatusValue, string>;
  };
  relative: {
    now: string;
    minutesAgo: (minutes: number) => string;
    hoursAgo: (hours: number) => string;
    daysAgo: (days: number) => string;
  };
  chart: {
    noHistory: string;
    growthCaptionNoWindow: string;
    countCaptionNoWindow: string;
    growthCaption: (windowDays: number) => string;
    countCaption: (windowDays: number) => string;
    ariaGrowth: (days: number) => string;
    ariaCount: (days: number) => string;
  };
  home: {
    topicsTracked: string;
    leadingTrend: string;
    emergingTopics: string;
    acrossAllTopics: string;
    apiDownTitle: string;
    apiDownHint: string;
    trendingNow: string;
    viewAllTrends: string;
    trendsUnavailable: string;
    noSnapshotsTitle: string;
    noSnapshotsBody: string;
    viewAllArticles: string;
    articlesUnavailable: string;
    noArticlesTitle: string;
    noArticlesBody: string;
    intro: (windowDays: number | null) => string;
  };
  category: {
    topics: string;
    leadingTrend: string;
    topTrends: string;
    noScoredTitle: string;
    noScoredBody: string;
    articlesUnavailable: string;
    emptyArticles: string;
    couldNotLoad: (slug: string) => string;
    score: (value: string) => string;
  };
  trends: {
    title: string;
    subtitle: string;
    searchPlaceholder: string;
    couldNotLoad: string;
    couldNotLoadHint: string;
    emptyTitle: string;
    emptyBody: string;
    statusAny: string;
    sortTrendScore: string;
    sortGrowthRate: string;
    sortArticleCount: string;
    sortNameAsc: string;
  };
  trendDetail: {
    inCurrentWindow: string;
    trendScore: string;
    scoreHint: string;
    snapshot: string;
    growthHistory: string;
    historyUnavailable: string;
    noSnapshotsTitle: string;
    noSnapshotsBody: string;
    summary: string;
    noSummary: string;
    viewAll: string;
    noArticles: string;
    growth: (windowDays: number) => string;
    articlesHint: (previous: string, current: string) => string;
    windowHint: (windowDays: number) => string;
    lastNDays: (days: number) => string;
    relativeVolume: (percent: number) => string;
    couldNotLoad: (slug: string) => string;
  };
  articles: {
    allArticles: string;
    searchPlaceholder: string;
    filteredByTopic: string;
    clearFilter: string;
    couldNotLoad: string;
    emptyTitle: string;
    emptyBody: string;
    sortNewest: string;
    sortOldest: string;
    sortRecent: string;
    sortTitleAsc: string;
    showingTopic: (name: string) => string;
  };
  articleDetail: {
    couldNotLoad: string;
    aiSummary: string;
    description: string;
    readOriginal: string;
    classificationStatus: string;
    moreLikeThis: string;
    noTopic: string;
    noOtherArticles: string;
  };
  notFound: {
    body: string;
    homepage: string;
  };
  errorPage: {
    title: string;
    hint: string;
  };
  trendCard: {
    growth: string;
    articles: string;
    viewTrend: string;
    score: (value: string) => string;
    ariaLabel: (name: string, growth: string) => string;
  };
  table: {
    trend: string;
    category: string;
    growth: string;
    articles: string;
    score: string;
    status: string;
    volume: string;
  };
};

export const en: Dictionary = {
  nav: {
    allTrends: "All trends",
    mainLabel: "Main",
    languageLabel: "Select language",
  },
  footer: {
    tagline: "Trend Tracker MVP — RSS ingestion, topic classification and trend scoring.",
    dataVia: "Data via the",
    backend: "FastAPI backend",
  },
  common: {
    home: "Home",
    articles: "Articles",
    latestArticles: "Latest articles",
    all: "All",
    categoriesLabel: "Categories",
    breadcrumbLabel: "Breadcrumb",
    paginationLabel: "Pagination",
    sortLabel: "Sort",
    statusLabel: "Status",
    search: "Search",
    apply: "Apply",
    previous: "← Previous",
    next: "Next →",
    tryAgain: "Try again",
    unknownSource: "Unknown source",
    noArticlesYet: "No articles yet.",
    notEnoughData: "Not enough data yet",
    pageOf: (page, pages) => `Page ${page} of ${pages}`,
  },
  status: {
    labels: {
      emerging: "Emerging",
      growing: "Growing",
      stable: "Stable",
      declining: "Declining",
    },
    descriptions: {
      emerging: "No articles in the previous period, and new activity now.",
      growing: "Publishing more than the previous period.",
      stable: "Publishing about as much as the previous period.",
      declining: "Publishing less than the previous period.",
    },
  },
  relative: {
    now: "just now",
    minutesAgo: (minutes) => `${minutes}m ago`,
    hoursAgo: (hours) => `${hours}h ago`,
    daysAgo: (days) => `${days}d ago`,
  },
  chart: {
    noHistory: "No history available yet.",
    growthCaptionNoWindow: "Growth rate per day (current window vs the previous equivalent period).",
    countCaptionNoWindow: "Articles per window.",
    growthCaption: (windowDays) =>
      `Growth rate per day (current ${windowDays}-day window vs the previous ${windowDays} days).`,
    countCaption: (windowDays) => `Articles per ${windowDays}-day window.`,
    ariaGrowth: (days) => `Growth rate over ${days} days`,
    ariaCount: (days) => `Article count over ${days} days`,
  },
  home: {
    topicsTracked: "Topics tracked",
    leadingTrend: "Leading trend",
    emergingTopics: "Emerging topics",
    acrossAllTopics: "Across all tracked topics",
    apiDownTitle: "The API is not responding",
    apiDownHint:
      "Start the backend (uvicorn app.main:app) or docker compose up, then reload.",
    trendingNow: "Trending now",
    viewAllTrends: "View all trends →",
    trendsUnavailable: "Trends unavailable",
    noSnapshotsTitle: "No trend snapshots yet",
    noSnapshotsBody:
      "Run the trend recalculation to generate the first snapshot, then reload.",
    viewAllArticles: "View all articles →",
    articlesUnavailable: "Articles unavailable",
    noArticlesTitle: "No articles ingested yet",
    noArticlesBody: "Run the RSS collector to fetch articles from the configured feeds.",
    intro: (windowDays) =>
      "Articles are collected from RSS feeds, classified into topics and scored by the backend from article growth" +
      (windowDays == null ? "" : ` over the last ${windowDays} days`) +
      ".",
  },
  category: {
    topics: "Topics",
    leadingTrend: "Leading trend",
    topTrends: "Top trends",
    noScoredTitle: "No scored topics yet",
    noScoredBody: "Trend snapshots have not been generated for this category.",
    articlesUnavailable: "Articles unavailable",
    emptyArticles: "No articles have been classified into this category yet.",
    couldNotLoad: (slug) => `Could not load the ${slug} category`,
    score: (value) => `Score ${value}`,
  },
  trends: {
    title: "All trends",
    subtitle:
      "The latest snapshot for every tracked topic, ranked by the backend trend score.",
    searchPlaceholder: "Search topics…",
    couldNotLoad: "Could not load trends",
    couldNotLoadHint: "Check that the FastAPI backend is running.",
    emptyTitle: "No trends match these filters",
    emptyBody: "Try a different category, status or search term.",
    statusAny: "Any status",
    sortTrendScore: "Trend score",
    sortGrowthRate: "Growth rate",
    sortArticleCount: "Article count",
    sortNameAsc: "Name (A–Z)",
  },
  trendDetail: {
    inCurrentWindow: "In the current window",
    trendScore: "Trend score",
    scoreHint: "0–100, growth-weighted",
    snapshot: "Snapshot",
    growthHistory: "Growth history",
    historyUnavailable: "History unavailable",
    noSnapshotsTitle: "No snapshots for this topic yet",
    noSnapshotsBody:
      "The trend engine has not scored this topic. Recalculating trends will create the first snapshot.",
    summary: "Summary",
    noSummary:
      "No summary has been generated for this topic yet. Summaries are written by the classification job from the most recent article titles.",
    viewAll: "View all →",
    noArticles: "No articles linked to this topic yet",
    growth: (windowDays) => `Growth (${windowDays}d)`,
    articlesHint: (previous, current) => `${previous} → ${current} articles`,
    windowHint: (windowDays) => `${windowDays}-day window`,
    lastNDays: (days) => `Last ${days} days`,
    relativeVolume: (percent) =>
      `Relative volume: ${percent}% of the busiest topic this period`,
    couldNotLoad: (slug) => `Could not load ${slug}`,
  },
  articles: {
    allArticles: "Every article stored from the configured RSS feeds.",
    searchPlaceholder: "Search headlines…",
    filteredByTopic: "Filtered by topic",
    clearFilter: "clear filter",
    couldNotLoad: "Could not load articles",
    emptyTitle: "No articles found",
    emptyBody: "Run the collector to ingest feeds, or adjust the filters.",
    sortNewest: "Newest first",
    sortOldest: "Oldest first",
    sortRecent: "Recently ingested",
    sortTitleAsc: "Title (A–Z)",
    showingTopic: (name) => `Showing articles classified into “${name}”.`,
  },
  articleDetail: {
    couldNotLoad: "Could not load this article",
    aiSummary: "AI summary",
    description: "Description",
    readOriginal: "Read the original article →",
    classificationStatus: "Classification status:",
    moreLikeThis: "More like this",
    noTopic:
      "This article was not linked to a specific topic, so there is nothing to compare.",
    noOtherArticles: "No other articles in this topic yet.",
  },
  notFound: {
    body: "This page does not exist.",
    homepage: "Homepage",
  },
  errorPage: {
    title: "Could not load this page",
    hint: "The backend may be starting up. Retry in a moment.",
  },
  trendCard: {
    growth: "growth",
    articles: "articles",
    viewTrend: "View trend →",
    score: (value) => `Score ${value}`,
    ariaLabel: (name, growth) => `${name}, ${growth} growth`,
  },
  table: {
    trend: "Trend",
    category: "Category",
    growth: "Growth",
    articles: "Articles",
    score: "Score",
    status: "Status",
    volume: "Volume",
  },
};

export const vi: Dictionary = {
  nav: {
    allTrends: "Tất cả xu hướng",
    mainLabel: "Chính",
    languageLabel: "Chọn ngôn ngữ",
  },
  footer: {
    tagline: "Trend Tracker MVP — Thu thập RSS, phân loại chủ đề và chấm điểm xu hướng.",
    dataVia: "Dữ liệu qua",
    backend: "FastAPI backend",
  },
  common: {
    home: "Trang chủ",
    articles: "Bài viết",
    latestArticles: "Bài viết mới nhất",
    all: "Tất cả",
    categoriesLabel: "Danh mục",
    breadcrumbLabel: "Đường dẫn",
    paginationLabel: "Phân trang",
    sortLabel: "Sắp xếp",
    statusLabel: "Trạng thái",
    search: "Tìm",
    apply: "Áp dụng",
    previous: "← Trước",
    next: "Tiếp →",
    tryAgain: "Thử lại",
    unknownSource: "Nguồn không rõ",
    noArticlesYet: "Chưa có bài viết nào.",
    notEnoughData: "Chưa đủ dữ liệu",
    pageOf: (page, pages) => `Trang ${page} / ${pages}`,
  },
  status: {
    labels: {
      emerging: "Mới nổi",
      growing: "Đang tăng",
      stable: "Ổn định",
      declining: "Đang giảm",
    },
    descriptions: {
      emerging: "Kỳ trước không có bài viết nào, hiện tại đã có hoạt động mới.",
      growing: "Đăng nhiều bài hơn kỳ trước.",
      stable: "Số bài đăng tương đương kỳ trước.",
      declining: "Đăng ít bài hơn kỳ trước.",
    },
  },
  relative: {
    now: "vừa xong",
    minutesAgo: (minutes) => `${minutes} phút trước`,
    hoursAgo: (hours) => `${hours} giờ trước`,
    daysAgo: (days) => `${days} ngày trước`,
  },
  chart: {
    noHistory: "Chưa có dữ liệu lịch sử.",
    growthCaptionNoWindow: "Tốc độ tăng trưởng mỗi ngày (kỳ hiện tại so với kỳ tương đương trước đó).",
    countCaptionNoWindow: "Số bài viết mỗi kỳ.",
    growthCaption: (windowDays) =>
      `Tốc độ tăng trưởng mỗi ngày (kỳ ${windowDays} ngày hiện tại so với ${windowDays} ngày trước).`,
    countCaption: (windowDays) => `Số bài viết mỗi kỳ ${windowDays} ngày.`,
    ariaGrowth: (days) => `Tốc độ tăng trưởng trong ${days} ngày`,
    ariaCount: (days) => `Số bài viết trong ${days} ngày`,
  },
  home: {
    topicsTracked: "Chủ đề đang theo dõi",
    leadingTrend: "Xu hướng dẫn đầu",
    emergingTopics: "Chủ đề mới nổi",
    acrossAllTopics: "Trên tất cả chủ đề đang theo dõi",
    apiDownTitle: "API không phản hồi",
    apiDownHint:
      "Hãy khởi động backend (uvicorn app.main:app) hoặc docker compose up, rồi tải lại.",
    trendingNow: "Đang thịnh hành",
    viewAllTrends: "Xem tất cả xu hướng →",
    trendsUnavailable: "Không có dữ liệu xu hướng",
    noSnapshotsTitle: "Chưa có ảnh chụp xu hướng",
    noSnapshotsBody: "Hãy chạy tính toán lại xu hướng để tạo ảnh chụp đầu tiên, rồi tải lại.",
    viewAllArticles: "Xem tất cả bài viết →",
    articlesUnavailable: "Không có dữ liệu bài viết",
    noArticlesTitle: "Chưa thu thập bài viết nào",
    noArticlesBody: "Hãy chạy trình thu thập RSS để lấy bài viết từ các nguồn đã cấu hình.",
    intro: (windowDays) =>
      "Bài viết được thu thập từ nguồn RSS, phân loại theo chủ đề và chấm điểm bởi backend dựa trên tăng trưởng bài viết" +
      (windowDays == null ? "" : ` trong ${windowDays} ngày qua`) +
      ".",
  },
  category: {
    topics: "Chủ đề",
    leadingTrend: "Xu hướng dẫn đầu",
    topTrends: "Xu hướng hàng đầu",
    noScoredTitle: "Chưa có chủ đề nào được chấm điểm",
    noScoredBody: "Chưa có ảnh chụp xu hướng nào cho danh mục này.",
    articlesUnavailable: "Không có dữ liệu bài viết",
    emptyArticles: "Chưa có bài viết nào được phân loại vào danh mục này.",
    couldNotLoad: (slug) => `Không tải được danh mục ${slug}`,
    score: (value) => `Điểm ${value}`,
  },
  trends: {
    title: "Tất cả xu hướng",
    subtitle:
      "Ảnh chụp mới nhất của mọi chủ đề đang theo dõi, xếp hạng theo điểm xu hướng từ backend.",
    searchPlaceholder: "Tìm chủ đề…",
    couldNotLoad: "Không tải được xu hướng",
    couldNotLoadHint: "Kiểm tra xem backend FastAPI có đang chạy không.",
    emptyTitle: "Không có xu hướng nào khớp bộ lọc",
    emptyBody: "Hãy thử danh mục, trạng thái hoặc từ khóa khác.",
    statusAny: "Mọi trạng thái",
    sortTrendScore: "Điểm xu hướng",
    sortGrowthRate: "Tốc độ tăng trưởng",
    sortArticleCount: "Số bài viết",
    sortNameAsc: "Tên (A–Z)",
  },
  trendDetail: {
    inCurrentWindow: "Trong kỳ hiện tại",
    trendScore: "Điểm xu hướng",
    scoreHint: "0–100, theo trọng số tăng trưởng",
    snapshot: "Ảnh chụp dữ liệu",
    growthHistory: "Lịch sử tăng trưởng",
    historyUnavailable: "Không có dữ liệu lịch sử",
    noSnapshotsTitle: "Chưa có ảnh chụp nào cho chủ đề này",
    noSnapshotsBody:
      "Công cụ xu hướng chưa chấm điểm chủ đề này. Tính toán lại xu hướng sẽ tạo ảnh chụp đầu tiên.",
    summary: "Tóm tắt",
    noSummary:
      "Chưa có tóm tắt nào cho chủ đề này. Tóm tắt do tác vụ phân loại tạo từ tiêu đề các bài viết gần nhất.",
    viewAll: "Xem tất cả →",
    noArticles: "Chưa có bài viết nào liên kết với chủ đề này",
    growth: (windowDays) => `Tăng trưởng (${windowDays} ngày)`,
    articlesHint: (previous, current) => `${previous} → ${current} bài viết`,
    windowHint: (windowDays) => `Kỳ ${windowDays} ngày`,
    lastNDays: (days) => `${days} ngày gần nhất`,
    relativeVolume: (percent) =>
      `Lượng tin tương đối: ${percent}% so với chủ đề sôi động nhất kỳ này`,
    couldNotLoad: (slug) => `Không tải được ${slug}`,
  },
  articles: {
    allArticles: "Mọi bài viết được lưu từ các nguồn RSS đã cấu hình.",
    searchPlaceholder: "Tìm tiêu đề…",
    filteredByTopic: "Lọc theo chủ đề",
    clearFilter: "bỏ lọc",
    couldNotLoad: "Không tải được bài viết",
    emptyTitle: "Không tìm thấy bài viết nào",
    emptyBody: "Hãy chạy trình thu thập để lấy nguồn, hoặc điều chỉnh bộ lọc.",
    sortNewest: "Mới nhất trước",
    sortOldest: "Cũ nhất trước",
    sortRecent: "Vừa thu thập",
    sortTitleAsc: "Tiêu đề (A–Z)",
    showingTopic: (name) => `Đang hiển thị bài viết thuộc chủ đề “${name}”.`,
  },
  articleDetail: {
    couldNotLoad: "Không tải được bài viết này",
    aiSummary: "Tóm tắt AI",
    description: "Mô tả",
    readOriginal: "Đọc bài gốc →",
    classificationStatus: "Trạng thái phân loại:",
    moreLikeThis: "Bài viết tương tự",
    noTopic:
      "Bài viết này không được gắn với chủ đề cụ thể nào nên không có gì để so sánh.",
    noOtherArticles: "Chưa có bài viết nào khác trong chủ đề này.",
  },
  notFound: {
    body: "Trang này không tồn tại.",
    homepage: "Trang chủ",
  },
  errorPage: {
    title: "Không tải được trang này",
    hint: "Backend có thể đang khởi động. Hãy thử lại sau giây lát.",
  },
  trendCard: {
    growth: "tăng trưởng",
    articles: "bài viết",
    viewTrend: "Xem xu hướng →",
    score: (value) => `Điểm ${value}`,
    ariaLabel: (name, growth) => `${name}, tăng trưởng ${growth}`,
  },
  table: {
    trend: "Xu hướng",
    category: "Danh mục",
    growth: "Tăng trưởng",
    articles: "Bài viết",
    score: "Điểm",
    status: "Trạng thái",
    volume: "Lượng tin",
  },
};
