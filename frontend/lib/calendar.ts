import { api } from "@/lib/api-client";

// ---------------------------------------------------------------- vocabularies

/** Mirrors CALENDAR_ENTRY_STATUSES in backend/app/models/calendar.py (order matters). */
export const CALENDAR_STATUSES = [
  "planned",
  "in_progress",
  "ready",
  "scheduled",
  "published",
  "cancelled",
] as const;
export type CalendarStatus = (typeof CALENDAR_STATUSES)[number];

export const CALENDAR_STATUS_LABELS_FA: Record<string, string> = {
  planned: "برنامه‌ریزی‌شده",
  in_progress: "در حال تولید",
  ready: "آماده بازبینی",
  scheduled: "زمان‌بندی‌شده",
  published: "منتشر شده",
  cancelled: "لغو شده",
};

/** Tailwind classes per status, for column headers and chips. */
export const CALENDAR_STATUS_STYLE: Record<string, string> = {
  planned: "bg-slate-500/15 text-slate-300 border-slate-500/30",
  in_progress: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  ready: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  scheduled: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
  published: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  cancelled: "bg-red-500/15 text-red-300 border-red-500/30",
};

export const CALENDAR_PRIORITIES = ["low", "normal", "high", "urgent"] as const;
export type CalendarPriority = (typeof CALENDAR_PRIORITIES)[number];

export const CALENDAR_PRIORITY_LABELS_FA: Record<string, string> = {
  low: "کم",
  normal: "معمولی",
  high: "زیاد",
  urgent: "فوری",
};

export const CALENDAR_PRIORITY_STYLE: Record<string, string> = {
  low: "bg-white/5 text-muted-foreground",
  normal: "bg-sky-500/15 text-sky-300",
  high: "bg-amber-500/15 text-amber-300",
  urgent: "bg-red-500/15 text-red-300",
};

export const CALENDAR_SOURCE_LABELS_FA: Record<string, string> = {
  manual: "دستی",
  ai_auto: "زمان‌بندی AI",
};

// -------------------------------------------------------------------- entities

/** Mirrors CalendarEntryRead in backend/app/schemas/calendar.py. */
export interface CalendarEntry {
  id: string;
  organization_id: string;
  website_id: string;
  title: string;
  brief_id: string | null;
  article_id: string | null;
  opportunity_id: string | null;
  status: CalendarStatus | string;
  priority: CalendarPriority | string;
  source: string;
  scheduled_for: string | null;
  deadline: string | null;
  published_at: string | null;
  assigned_to: string | null;
  target_keyword: string | null;
  notes: string | null;
  details: Record<string, any>;
  created_at: string;
  updated_at: string;
}

/** Mirrors CalendarBoardView: columns keyed by status. */
export interface CalendarBoardView {
  columns: Record<string, CalendarEntry[]>;
}

export interface CalendarSummary {
  by_status: Record<string, number>;
  overdue: number;
  due_this_week: number;
  unassigned: number;
}

export interface CalendarAutoScheduleResult {
  website_id: string;
  created: number;
  skipped: number;
  /** Open opportunities still without a slot after this run. */
  remaining_open: number;
  scheduled_through: string | null;
}

export interface CalendarDayBucket {
  date: string;
  entries: CalendarEntry[];
  count: number;
}

export interface CalendarMonthView {
  website_id: string;
  year: number;
  month: number;
  range_start: string;
  range_end: string;
  days: CalendarDayBucket[];
}

export interface CalendarWeekView {
  website_id: string;
  range_start: string;
  range_end: string;
  days: CalendarDayBucket[];
}

// ----------------------------------------------------------------- write bodies

export interface CalendarEntryCreateBody {
  website_id: string;
  title: string;
  status?: CalendarStatus;
  priority?: CalendarPriority;
  scheduled_for?: string | null;
  deadline?: string | null;
  target_keyword?: string | null;
  notes?: string | null;
}

export interface CalendarEntryUpdateBody {
  title?: string;
  status?: CalendarStatus;
  priority?: CalendarPriority;
  scheduled_for?: string | null;
  deadline?: string | null;
  target_keyword?: string | null;
  notes?: string | null;
  assigned_to?: string | null;
}

// ----------------------------------------------------------------------- calls

export function getCalendarBoard(websiteId: string) {
  return api.get<CalendarBoardView>(`/calendar/board?website_id=${websiteId}`);
}

export function getCalendarMonth(websiteId: string, year: number, month: number) {
  return api.get<CalendarMonthView>(`/calendar/month?website_id=${websiteId}&year=${year}&month=${month}`);
}

export function getCalendarWeek(websiteId: string, startDate: string) {
  return api.get<CalendarWeekView>(`/calendar/week?website_id=${websiteId}&start_date=${startDate}`);
}

export function listCalendarEntries(websiteId: string, params: Record<string, any> = {}) {
  const query = new URLSearchParams({ website_id: websiteId });
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") {
      query.set(k, String(v));
    }
  });
  return api.get<{ data: CalendarEntry[]; meta: { total: number; limit: number; offset: number } }>(
    `/calendar?${query.toString()}`
  );
}

export function getCalendarEntry(entryId: string) {
  return api.get<CalendarEntry>(`/calendar/${entryId}`);
}

export function getCalendarSummary(websiteId: string) {
  return api.get<CalendarSummary>(`/calendar/summary?website_id=${websiteId}`);
}

export function createCalendarEntry(body: CalendarEntryCreateBody) {
  return api.post<CalendarEntry>(`/calendar`, body);
}

export function updateCalendarEntry(
  entryId: string,
  body: CalendarEntryUpdateBody
) {
  return api.patch<CalendarEntry>(`/calendar/${entryId}`, body);
}

/** Board drag: change status and/or scheduled date only. */
export function moveCalendarEntry(
  entryId: string,
  body: { status?: CalendarStatus; scheduled_for?: string | null }
) {
  return api.post<CalendarEntry>(`/calendar/${entryId}/move`, body);
}

export function deleteCalendarEntry(entryId: string) {
  return api.delete<{ deleted: boolean; id: string }>(`/calendar/${entryId}`);
}

export function autoScheduleFromOpportunities(
  websiteId: string,
  maxEntries = 10
) {
  return api.post<CalendarAutoScheduleResult>(
    `/calendar/auto-schedule?website_id=${websiteId}`,
    { max_entries: maxEntries }
  );
}

