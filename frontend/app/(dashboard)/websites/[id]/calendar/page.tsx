"use client";

/**
 * Content calendar workspace — kanban board, month grid, week view, and list view.
 * Supports manual slot creation, AI auto-scheduling from opportunities,
 * drag-and-drop between status columns, detail/edit modals, and direct
 * integration with the Content Hub.
 */

import React, { useCallback, useEffect, useMemo, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { ApiError } from "@/lib/api-client";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import {
  getCalendarBoard,
  getCalendarSummary,
  getCalendarMonth,
  getCalendarWeek,
  listCalendarEntries,
  createCalendarEntry,
  updateCalendarEntry,
  moveCalendarEntry,
  deleteCalendarEntry,
  autoScheduleFromOpportunities,
  CALENDAR_STATUSES,
  CALENDAR_STATUS_LABELS_FA,
  CALENDAR_STATUS_STYLE,
  CALENDAR_PRIORITIES,
  CALENDAR_PRIORITY_LABELS_FA,
  CALENDAR_PRIORITY_STYLE,
  CALENDAR_SOURCE_LABELS_FA,
  type CalendarBoardView,
  type CalendarEntry,
  type CalendarSummary,
  type CalendarStatus,
  type CalendarPriority,
  type CalendarMonthView,
  type CalendarWeekView,
} from "@/lib/calendar";
import { formatNumberFa, formatDateFa, labelFa } from "@/lib/insights";
import {
  AlertCircle,
  AlertTriangle,
  Calendar as CalendarIcon,
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Edit3,
  ExternalLink,
  Eye,
  FileText,
  Filter,
  Flame,
  GripVertical,
  Layers,
  LayoutGrid,
  List,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Target,
  Trash2,
  TrendingUp,
  UserX,
  X,
} from "lucide-react";
import toast from "react-hot-toast";

type ViewMode = "board" | "month" | "week" | "list";

export default function WebsiteCalendarPage() {
  const params = useParams();
  const router = useRouter();
  const websiteId = params.id as string;

  // View state
  const [viewMode, setViewMode] = useState<ViewMode>("board");
  const [board, setBoard] = useState<CalendarBoardView | null>(null);
  const [monthView, setMonthView] = useState<CalendarMonthView | null>(null);
  const [weekView, setWeekView] = useState<CalendarWeekView | null>(null);
  const [listView, setListView] = useState<CalendarEntry[]>([]);
  const [summary, setSummary] = useState<CalendarSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scheduling, setScheduling] = useState(false);
  const schedulingLock = useRef(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<CalendarEntry | null>(null);

  // Month navigation (Defaults to current year/month)
  const [currentYear, setCurrentYear] = useState<number>(() => new Date().getFullYear());
  const [currentMonth, setCurrentMonth] = useState<number>(() => new Date().getMonth() + 1);

  // Week navigation (Defaults to today)
  const [weekStartDate, setWeekStartDate] = useState<string>(() => {
    const d = new Date();
    return d.toISOString().split("T")[0];
  });

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState("");
  const [priorityFilter, setPriorityFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [sourceFilter, setSourceFilter] = useState<string>("all");

  // Create Modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [keywordDraft, setKeywordDraft] = useState("");
  const [dateDraft, setDateDraft] = useState("");
  const [deadlineDraft, setDeadlineDraft] = useState("");
  const [priorityDraft, setPriorityDraft] = useState<CalendarPriority>("normal");
  const [statusDraft, setStatusDraft] = useState<CalendarStatus>("planned");
  const [notesDraft, setNotesDraft] = useState("");
  const [saving, setSaving] = useState(false);

  // Detail / Edit Modal state
  const [selectedEntry, setSelectedEntry] = useState<CalendarEntry | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editKeyword, setEditKeyword] = useState("");
  const [editDate, setEditDate] = useState("");
  const [editDeadline, setEditDeadline] = useState("");
  const [editPriority, setEditPriority] = useState<CalendarPriority>("normal");
  const [editStatus, setEditStatus] = useState<CalendarStatus>("planned");
  const [editNotes, setEditNotes] = useState("");
  const [updating, setUpdating] = useState(false);

  // Drag and Drop state
  const [draggedEntryId, setDraggedEntryId] = useState<string | null>(null);
  const [dragOverColumn, setDragOverColumn] = useState<string | null>(null);

  // ------------------------------------------------------------- Data Fetching
  const loadData = useCallback(async () => {
    if (!websiteId) return;
    setLoading(true);
    setError(null);
    try {
      const summaryPromise = getCalendarSummary(websiteId);
      let viewPromise: Promise<any>;

      if (viewMode === "board") {
        viewPromise = getCalendarBoard(websiteId);
      } else if (viewMode === "month") {
        viewPromise = getCalendarMonth(websiteId, currentYear, currentMonth);
      } else if (viewMode === "week") {
        viewPromise = getCalendarWeek(websiteId, weekStartDate);
      } else {
        viewPromise = listCalendarEntries(websiteId, { limit: 100 });
      }

      const [sData, vData] = await Promise.all([summaryPromise, viewPromise]);
      setSummary(sData);

      if (viewMode === "board") {
        setBoard(vData as CalendarBoardView);
      } else if (viewMode === "month") {
        setMonthView(vData as CalendarMonthView);
      } else if (viewMode === "week") {
        setWeekView(vData as CalendarWeekView);
      } else {
        setListView((vData?.data || []) as CalendarEntry[]);
      }
    } catch (err: any) {
      setError(
        err instanceof ApiError ? err.message : "خطا در دریافت اطلاعات تقویم محتوا"
      );
    } finally {
      setLoading(false);
    }
  }, [websiteId, viewMode, currentYear, currentMonth, weekStartDate]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // ----------------------------------------------------------------- Filtering
  const filterEntry = useCallback(
    (entry: CalendarEntry) => {
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchTitle = entry.title.toLowerCase().includes(q);
        const matchKw = (entry.target_keyword || "").toLowerCase().includes(q);
        const matchNotes = (entry.notes || "").toLowerCase().includes(q);
        if (!matchTitle && !matchKw && !matchNotes) return false;
      }
      if (priorityFilter !== "all" && entry.priority !== priorityFilter) return false;
      if (statusFilter !== "all" && entry.status !== statusFilter) return false;
      if (sourceFilter !== "all" && entry.source !== sourceFilter) return false;
      return true;
    },
    [searchQuery, priorityFilter, statusFilter, sourceFilter]
  );

  const filteredBoardColumns = useMemo(() => {
    if (!board) return {};
    const res: Record<string, CalendarEntry[]> = {};
    for (const [col, entries] of Object.entries(board.columns)) {
      res[col] = (entries || []).filter(filterEntry);
    }
    return res;
  }, [board, filterEntry]);

  const totalEntries = useMemo(() => {
    if (!board) return 0;
    return Object.values(board.columns).reduce(
      (acc, col) => acc + (col?.length ?? 0),
      0
    );
  }, [board]);

  const isEmpty = !loading && !error && totalEntries === 0;

  // ------------------------------------------------------------- Create / Edit
  const resetCreateForm = () => {
    setShowCreateModal(false);
    setTitleDraft("");
    setKeywordDraft("");
    setDateDraft("");
    setDeadlineDraft("");
    setPriorityDraft("normal");
    setStatusDraft("planned");
    setNotesDraft("");
  };

  const submitCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const title = titleDraft.trim();
    if (title.length < 3) {
      toast.error("عنوان باید حداقل ۳ نویسه باشد");
      return;
    }

    if (dateDraft && deadlineDraft) {
      const sched = new Date(dateDraft).getTime();
      const due = new Date(deadlineDraft).getTime();
      if (due > sched) {
        toast.error("مهلت انجام (Deadline) نمی‌تواند بعد از تاریخ انتشار برنامه‌ریزی‌شده باشد.");
        return;
      }
    }

    setSaving(true);
    try {
      await createCalendarEntry({
        website_id: websiteId,
        title,
        status: statusDraft,
        priority: priorityDraft,
        target_keyword: keywordDraft.trim() || null,
        scheduled_for: dateDraft ? new Date(dateDraft).toISOString() : null,
        deadline: deadlineDraft ? new Date(deadlineDraft).toISOString() : null,
        notes: notesDraft.trim() || null,
      });
      toast.success("اسلات محتوا با موفقیت افزوده شد");
      resetCreateForm();
      await loadData();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در ساخت اسلات محتوا"
      );
    } finally {
      setSaving(false);
    }
  };

  const openDetailModal = (entry: CalendarEntry) => {
    setSelectedEntry(entry);
    setEditMode(false);
    setEditTitle(entry.title);
    setEditKeyword(entry.target_keyword || "");
    setEditDate(
      entry.scheduled_for
        ? new Date(entry.scheduled_for).toISOString().slice(0, 16)
        : ""
    );
    setEditDeadline(
      entry.deadline
        ? new Date(entry.deadline).toISOString().slice(0, 16)
        : ""
    );
    setEditPriority(entry.priority as CalendarPriority);
    setEditStatus(entry.status as CalendarStatus);
    setEditNotes(entry.notes || "");
  };

  const submitUpdate = async () => {
    if (!selectedEntry) return;
    const title = editTitle.trim();
    if (title.length < 3) {
      toast.error("عنوان باید حداقل ۳ نویسه باشد");
      return;
    }

    if (editDate && editDeadline) {
      const sched = new Date(editDate).getTime();
      const due = new Date(editDeadline).getTime();
      if (due > sched) {
        toast.error("مهلت انجام نمی‌تواند بعد از تاریخ انتشار برنامه‌ریزی‌شده باشد.");
        return;
      }
    }

    setUpdating(true);
    try {
      const updated = await updateCalendarEntry(selectedEntry.id, {
        title,
        status: editStatus,
        priority: editPriority,
        target_keyword: editKeyword.trim() || null,
        scheduled_for: editDate ? new Date(editDate).toISOString() : null,
        deadline: editDeadline ? new Date(editDeadline).toISOString() : null,
        notes: editNotes.trim() || null,
      });
      toast.success("اسلات محتوا به‌روزرسانی شد");
      setSelectedEntry(updated);
      setEditMode(false);
      await loadData();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در به‌روزرسانی اسلات"
      );
    } finally {
      setUpdating(false);
    }
  };

  const moveStatus = async (entry: CalendarEntry, nextStatus: CalendarStatus) => {
    setBusyId(entry.id);
    try {
      await moveCalendarEntry(entry.id, { status: nextStatus });
      toast.success(
        `به «${labelFa(CALENDAR_STATUS_LABELS_FA, nextStatus)}» منتقل شد`
      );
      if (selectedEntry && selectedEntry.id === entry.id) {
        setSelectedEntry({ ...selectedEntry, status: nextStatus });
      }
      await loadData();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در جابجایی وضعیت"
      );
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async () => {
    const entry = pendingDelete;
    if (!entry) return;
    setBusyId(entry.id);
    try {
      await deleteCalendarEntry(entry.id);
      toast.success("اسلات حذف شد");
      if (selectedEntry?.id === entry.id) {
        setSelectedEntry(null);
      }
      setPendingDelete(null);
      await loadData();
    } catch (err: any) {
      toast.error(err instanceof ApiError ? err.message : "خطا در حذف اسلات");
    } finally {
      setBusyId(null);
    }
  };

  const handleAutoSchedule = async () => {
    if (schedulingLock.current) return;
    schedulingLock.current = true;
    setScheduling(true);
    setError(null);
    try {
      const res = await autoScheduleFromOpportunities(websiteId, 10);
      toast.success(
        `زمان‌بندی هوشمند AI: ${formatNumberFa(res.created)} اسلات جدید از فرصت‌های رشد ایجاد شد${
          res.skipped ? ` (${formatNumberFa(res.skipped)} مورد قبلاً زمان‌بندی شده بود)` : ""
        }`
      );
      await loadData();
    } catch (err: any) {
      const message =
        err instanceof ApiError
          ? err.message
          : "خطا در زمان‌بندی خودکار از فرصت‌ها";
      setError(message);
      toast.error(message);
    } finally {
      setScheduling(false);
      schedulingLock.current = false;
    }
  };

  // ------------------------------------------------------------- Drag and Drop
  const handleDragStart = (entryId: string) => {
    setDraggedEntryId(entryId);
  };

  const handleDragOver = (e: React.DragEvent, colStatus: string) => {
    e.preventDefault();
    if (dragOverColumn !== colStatus) {
      setDragOverColumn(colStatus);
    }
  };

  const handleDrop = async (colStatus: string) => {
    setDragOverColumn(null);
    if (!draggedEntryId) return;
    const entryId = draggedEntryId;
    setDraggedEntryId(null);

    setBusyId(entryId);
    try {
      await moveCalendarEntry(entryId, { status: colStatus as CalendarStatus });
      toast.success(
        `به «${labelFa(CALENDAR_STATUS_LABELS_FA, colStatus)}» منتقل شد`
      );
      await loadData();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در جابجایی کارت"
      );
    } finally {
      setBusyId(null);
    }
  };

  const isOverdue = (entry: CalendarEntry) => {
    if (!entry.deadline || entry.status === "published" || entry.status === "cancelled") {
      return false;
    }
    return new Date(entry.deadline).getTime() < Date.now();
  };

  // ------------------------------------------------------------- Month Navigation
  const prevMonth = () => {
    if (currentMonth === 1) {
      setCurrentMonth(12);
      setCurrentYear((y) => y - 1);
    } else {
      setCurrentMonth((m) => m - 1);
    }
  };

  const nextMonth = () => {
    if (currentMonth === 12) {
      setCurrentMonth(1);
      setCurrentYear((y) => y + 1);
    } else {
      setCurrentMonth((m) => m + 1);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Main Actions */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-white">تقویم محتوا (Content Calendar)</h1>
            <span className="rounded-md bg-sky-500/15 px-2 py-0.5 text-xs font-semibold text-sky-400">
              فاز ۴
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            برنامه‌ریزی، زمان‌بندی و پیگیری تولید محتوای سئو بر اساس فرصت‌های رشد در نماهای کانبان، تقویم و لیست
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* View Mode Switcher */}
          <div className="flex rounded-xl border border-white/10 bg-black/40 p-1">
            <button
              onClick={() => setViewMode("board")}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                viewMode === "board"
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-white"
              }`}
            >
              <LayoutGrid className="h-3.5 w-3.5" />
              <span>کانبان</span>
            </button>
            <button
              onClick={() => setViewMode("month")}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                viewMode === "month"
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-white"
              }`}
            >
              <CalendarIcon className="h-3.5 w-3.5" />
              <span>ماهیانه</span>
            </button>
            <button
              onClick={() => setViewMode("week")}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                viewMode === "week"
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-white"
              }`}
            >
              <Clock className="h-3.5 w-3.5" />
              <span>هفتگی</span>
            </button>
            <button
              onClick={() => setViewMode("list")}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                viewMode === "list"
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-white"
              }`}
            >
              <List className="h-3.5 w-3.5" />
              <span>لیست</span>
            </button>
          </div>

          <button
            onClick={() => setShowCreateModal(true)}
            disabled={!websiteId}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-sky-500/20 transition hover:from-sky-600 hover:to-indigo-700 disabled:opacity-50"
          >
            <Plus className="h-4 w-4" />
            اسلات جدید
          </button>

          <button
            onClick={handleAutoSchedule}
            disabled={scheduling || !websiteId}
            className="inline-flex items-center gap-2 rounded-xl border border-purple-500/30 bg-purple-500/10 px-4 py-2 text-xs font-semibold text-purple-200 transition hover:bg-purple-500/20 disabled:opacity-50"
          >
            {scheduling ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4 text-purple-400" />
            )}
            {scheduling ? "در حال زمان‌بندی..." : "زمان‌بندی هوشمند با AI"}
          </button>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          {
            label: "کل اسلات‌های تقویم",
            value: totalEntries,
            icon: CalendarDays,
            tone: "text-sky-400",
            bg: "border-sky-500/20 bg-sky-500/5",
          },
          {
            label: "عقب‌افتاده از مهلت",
            value: summary?.overdue ?? 0,
            icon: AlertTriangle,
            tone: "text-red-400",
            bg: "border-red-500/20 bg-red-500/5",
          },
          {
            label: "برنامه این هفته",
            value: summary?.due_this_week ?? 0,
            icon: Clock,
            tone: "text-amber-400",
            bg: "border-amber-500/20 bg-amber-500/5",
          },
          {
            label: "بدون نویسنده / مسئول",
            value: summary?.unassigned ?? 0,
            icon: UserX,
            tone: "text-muted-foreground",
            bg: "border-white/10 bg-white/5",
          },
        ].map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.label}
              className={`rounded-2xl border p-5 backdrop-blur-md transition hover:border-white/20 ${card.bg}`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">
                  {card.label}
                </span>
                <Icon className={`h-4 w-4 ${card.tone}`} />
              </div>
              <p className="mt-2 text-2xl font-bold text-white">
                {formatNumberFa(card.value)}
              </p>
            </div>
          );
        })}
      </div>

      {/* Search and Filters Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/10 bg-card/60 p-3.5 backdrop-blur-md">
        <div className="flex flex-1 items-center gap-2 sm:max-w-xs">
          <div className="relative w-full">
            <Search className="absolute right-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="جستجو در عنوان یا کلمه کلیدی..."
              className="w-full rounded-xl border border-white/10 bg-black/40 py-2 pr-9 pl-3 text-xs text-white placeholder:text-muted-foreground/60 outline-none focus:border-sky-500"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute left-3 top-2.5 text-muted-foreground hover:text-white"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Priority filter */}
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-xs text-white outline-none focus:border-sky-500"
          >
            <option value="all" className="bg-card">همه اولویت‌ها</option>
            {CALENDAR_PRIORITIES.map((p) => (
              <option key={p} value={p} className="bg-card">
                اولویت: {CALENDAR_PRIORITY_LABELS_FA[p]}
              </option>
            ))}
          </select>

          {/* Source filter */}
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-xs text-white outline-none focus:border-sky-500"
          >
            <option value="all" className="bg-card">همه منابع</option>
            <option value="manual" className="bg-card">دستی (Manual)</option>
            <option value="ai_auto" className="bg-card">زمان‌بندی AI</option>
          </select>

          {/* Status filter (useful in list view) */}
          {viewMode === "list" && (
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-xs text-white outline-none focus:border-sky-500"
            >
              <option value="all" className="bg-card">همه وضعیت‌ها</option>
              {CALENDAR_STATUSES.map((s) => (
                <option key={s} value={s} className="bg-card">
                  {CALENDAR_STATUS_LABELS_FA[s]}
                </option>
              ))}
            </select>
          )}

          <button
            onClick={loadData}
            title="تازه‌سازی داده‌ها"
            className="rounded-xl border border-white/10 bg-black/40 p-2 text-muted-foreground transition hover:bg-white/10 hover:text-white"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs text-red-300">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* ------------------------------------------------- VIEW: KANBAN BOARD */}
      {viewMode === "board" && (
        <>
          {loading ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
              {CALENDAR_STATUSES.map((s) => (
                <div key={s} className="space-y-3">
                  <div className="h-8 animate-pulse rounded-lg bg-white/5" />
                  <div className="h-28 animate-pulse rounded-xl bg-white/5" />
                  <div className="h-28 animate-pulse rounded-xl bg-white/5" />
                </div>
              ))}
            </div>
          ) : isEmpty ? (
            <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-white/15 p-12 text-center">
              <CalendarDays className="h-12 w-12 text-muted-foreground/40" />
              <p className="text-base font-semibold text-white">
                تقویم محتوا خالی است
              </p>
              <p className="max-w-md text-xs text-muted-foreground">
                با زدن دکمه «اسلات جدید» محتوا برنامه‌ریزی کنید یا با «زمان‌بندی هوشمند با AI» فرصت‌های کشف‌شده سئو را به برنامه انتشار تبدیل نمایید.
              </p>
              <div className="mt-2 flex gap-3">
                <button
                  onClick={() => setShowCreateModal(true)}
                  className="rounded-xl bg-sky-500 px-4 py-2 text-xs font-semibold text-white hover:bg-sky-600"
                >
                  افزودن اسلات دستی
                </button>
                <button
                  onClick={handleAutoSchedule}
                  className="rounded-xl border border-purple-500/40 bg-purple-500/20 px-4 py-2 text-xs font-semibold text-purple-200 hover:bg-purple-500/30"
                >
                  زمان‌بندی هوشمند AI
                </button>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
              {CALENDAR_STATUSES.map((status) => {
                const cards = filteredBoardColumns[status] ?? [];
                const isDragTarget = dragOverColumn === status;
                return (
                  <div
                    key={status}
                    onDragOver={(e) => handleDragOver(e, status)}
                    onDrop={() => handleDrop(status)}
                    className={`flex flex-col gap-3 rounded-2xl border p-2.5 transition ${
                      isDragTarget
                        ? "border-sky-500/60 bg-sky-500/10 shadow-lg shadow-sky-500/10"
                        : "border-white/5 bg-card/30"
                    }`}
                  >
                    {/* Column Header */}
                    <div
                      className={`flex items-center justify-between rounded-xl border px-3 py-2 text-xs font-semibold ${
                        CALENDAR_STATUS_STYLE[status] ??
                        "border-white/10 bg-white/5 text-white"
                      }`}
                    >
                      <span>{labelFa(CALENDAR_STATUS_LABELS_FA, status)}</span>
                      <span className="rounded-md bg-black/30 px-2 py-0.5 font-bold">
                        {formatNumberFa(cards.length)}
                      </span>
                    </div>

                    {/* Cards Container */}
                    <div className="flex flex-col gap-2.5">
                      {cards.map((entry) => {
                        const statusIdx = CALENDAR_STATUSES.indexOf(
                          entry.status as CalendarStatus
                        );
                        const overdue = isOverdue(entry);

                        return (
                          <div
                            key={entry.id}
                            draggable
                            onDragStart={() => handleDragStart(entry.id)}
                            onClick={() => openDetailModal(entry)}
                            className={`group cursor-pointer rounded-xl border p-3.5 backdrop-blur-md transition hover:-translate-y-0.5 hover:shadow-lg ${
                              overdue
                                ? "border-red-500/30 bg-red-500/5 hover:border-red-500/50"
                                : "border-white/10 bg-card/80 hover:border-white/25"
                            }`}
                          >
                            {/* Card Header & Title */}
                            <div className="flex items-start justify-between gap-2">
                              <p className="text-xs font-semibold leading-5 text-white group-hover:text-sky-300">
                                {entry.title}
                              </p>
                              <div className="flex items-center gap-1 opacity-60 group-hover:opacity-100">
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setPendingDelete(entry);
                                  }}
                                  disabled={busyId === entry.id}
                                  title="حذف اسلات"
                                  className="rounded-md p-1 text-muted-foreground transition hover:bg-red-500/20 hover:text-red-400"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            </div>

                            {/* Target Keyword */}
                            {entry.target_keyword && (
                              <div className="mt-2 flex items-center gap-1 text-[11px] text-muted-foreground">
                                <Target className="h-3 w-3 shrink-0 text-sky-400" />
                                <span className="truncate">
                                  {entry.target_keyword}
                                </span>
                              </div>
                            )}

                            {/* Badges: Priority & AI Source */}
                            <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                              <span
                                className={`rounded-md px-1.5 py-0.5 text-[10px] font-medium ${
                                  CALENDAR_PRIORITY_STYLE[entry.priority] ??
                                  "bg-white/5 text-muted-foreground"
                                }`}
                              >
                                {labelFa(CALENDAR_PRIORITY_LABELS_FA, entry.priority)}
                              </span>

                              {entry.source === "ai_auto" && (
                                <span className="inline-flex items-center gap-1 rounded-md bg-purple-500/15 px-1.5 py-0.5 text-[10px] font-medium text-purple-300">
                                  <Sparkles className="h-2.5 w-2.5" />
                                  AI
                                </span>
                              )}

                              {overdue && (
                                <span className="inline-flex items-center gap-1 rounded-md bg-red-500/20 px-1.5 py-0.5 text-[10px] font-bold text-red-300">
                                  <AlertTriangle className="h-2.5 w-2.5" />
                                  عقب‌افتاده
                                </span>
                              )}
                            </div>

                            {/* Scheduled date and Deadline */}
                            <div className="mt-2 flex flex-col gap-1 text-[10px] text-muted-foreground">
                              {entry.scheduled_for && (
                                <div className="flex items-center gap-1">
                                  <CalendarDays className="h-3 w-3 shrink-0 text-slate-400" />
                                  <span>انتشار: {formatDateFa(entry.scheduled_for)}</span>
                                </div>
                              )}
                              {entry.deadline && (
                                <div className="flex items-center gap-1">
                                  <Clock className="h-3 w-3 shrink-0 text-amber-400" />
                                  <span>مهلت: {formatDateFa(entry.deadline)}</span>
                                </div>
                              )}
                            </div>

                            {/* Quick status navigation buttons */}
                            <div
                              onClick={(e) => e.stopPropagation()}
                              className="mt-3 flex items-center justify-between border-t border-white/5 pt-2"
                            >
                              <button
                                onClick={() => {
                                  if (statusIdx > 0) {
                                    moveStatus(entry, CALENDAR_STATUSES[statusIdx - 1]);
                                  }
                                }}
                                disabled={busyId === entry.id || statusIdx <= 0}
                                title="مرحله قبل"
                                className="rounded-md p-1 text-muted-foreground transition hover:bg-white/10 hover:text-white disabled:opacity-20"
                              >
                                <ChevronRight className="h-4 w-4" />
                              </button>

                              <span className="text-[9px] text-muted-foreground/80">
                                جابجایی
                              </span>

                              <button
                                onClick={() => {
                                  if (statusIdx < CALENDAR_STATUSES.length - 1) {
                                    moveStatus(entry, CALENDAR_STATUSES[statusIdx + 1]);
                                  }
                                }}
                                disabled={
                                  busyId === entry.id ||
                                  statusIdx >= CALENDAR_STATUSES.length - 1
                                }
                                title="مرحله بعد"
                                className="rounded-md p-1 text-muted-foreground transition hover:bg-white/10 hover:text-white disabled:opacity-20"
                              >
                                <ChevronLeft className="h-4 w-4" />
                              </button>
                            </div>
                          </div>
                        );
                      })}

                      {cards.length === 0 && (
                        <div className="rounded-xl border border-dashed border-white/10 p-6 text-center text-xs text-muted-foreground/50">
                          بدون اسلات
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* -------------------------------------------------- VIEW: MONTH GRID */}
      {viewMode === "month" && (
        <div className="space-y-4">
          {/* Month Header Navigation */}
          <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-card/60 p-4">
            <div className="flex items-center gap-3">
              <CalendarIcon className="h-5 w-5 text-sky-400" />
              <span className="text-sm font-bold text-white">
                ماه {currentMonth} سال {currentYear} (منطقه زمانی تهران)
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={prevMonth}
                className="flex items-center gap-1 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white transition hover:bg-white/10"
              >
                <ChevronRight className="h-4 w-4" />
                ماه قبل
              </button>
              <button
                onClick={() => {
                  const now = new Date();
                  setCurrentYear(now.getFullYear());
                  setCurrentMonth(now.getMonth() + 1);
                }}
                className="rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white transition hover:bg-white/10"
              >
                ماه جاری
              </button>
              <button
                onClick={nextMonth}
                className="flex items-center gap-1 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white transition hover:bg-white/10"
              >
                ماه بعد
                <ChevronLeft className="h-4 w-4" />
              </button>
            </div>
          </div>

          {loading ? (
            <div className="grid grid-cols-7 gap-3">
              {Array.from({ length: 31 }).map((_, i) => (
                <div key={i} className="h-28 animate-pulse rounded-2xl bg-white/5" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-7">
              {(monthView?.days || []).map((day) => {
                const filteredEntries = day.entries.filter(filterEntry);
                const hasEntries = filteredEntries.length > 0;
                return (
                  <div
                    key={day.date}
                    className={`flex flex-col justify-between rounded-2xl border p-3.5 transition ${
                      hasEntries
                        ? "border-sky-500/30 bg-card/90 shadow-md"
                        : "border-white/10 bg-card/40 hover:border-white/20"
                    }`}
                  >
                    <div className="flex items-center justify-between border-b border-white/5 pb-2">
                      <span className="text-xs font-bold text-white">
                        {day.date}
                      </span>
                      {hasEntries && (
                        <span className="rounded-full bg-sky-500/20 px-2 py-0.5 text-[10px] font-bold text-sky-300">
                          {formatNumberFa(filteredEntries.length)}
                        </span>
                      )}
                    </div>

                    <div className="mt-2 flex flex-1 flex-col gap-1.5 overflow-y-auto max-h-36">
                      {filteredEntries.map((entry) => (
                        <div
                          key={entry.id}
                          onClick={() => openDetailModal(entry)}
                          className="cursor-pointer rounded-lg border border-white/5 bg-white/5 p-1.5 text-[11px] text-white transition hover:bg-sky-500/20"
                        >
                          <div className="flex items-center justify-between gap-1">
                            <span className="truncate font-medium">{entry.title}</span>
                            <span className={`h-2 w-2 shrink-0 rounded-full ${
                              entry.status === 'published' ? 'bg-emerald-400' :
                              entry.status === 'in_progress' ? 'bg-amber-400' : 'bg-sky-400'
                            }`} />
                          </div>
                        </div>
                      ))}
                      {!hasEntries && (
                        <span className="text-[10px] text-muted-foreground/40 mt-3 text-center">
                          بدون اسلات
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* --------------------------------------------------- VIEW: WEEK VIEW */}
      {viewMode === "week" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-card/60 p-4">
            <div className="flex items-center gap-3">
              <Clock className="h-5 w-5 text-indigo-400" />
              <span className="text-sm font-bold text-white">
                نمای هفتگی (۷ روز از تاریخ {weekStartDate})
              </span>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="date"
                value={weekStartDate}
                onChange={(e) => setWeekStartDate(e.target.value)}
                className="rounded-xl border border-white/10 bg-black/40 px-3 py-1.5 text-xs text-white outline-none focus:border-sky-500"
              />
            </div>
          </div>

          {loading ? (
            <div className="grid grid-cols-7 gap-3">
              {Array.from({ length: 7 }).map((_, i) => (
                <div key={i} className="h-64 animate-pulse rounded-2xl bg-white/5" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-7">
              {(weekView?.days || []).map((day) => {
                const filteredEntries = day.entries.filter(filterEntry);
                return (
                  <div
                    key={day.date}
                    className="flex flex-col gap-3 rounded-2xl border border-white/10 bg-card/70 p-3.5"
                  >
                    <div className="flex items-center justify-between border-b border-white/5 pb-2">
                      <span className="text-xs font-bold text-white">{day.date}</span>
                      <span className="rounded-md bg-white/5 px-2 py-0.5 text-[10px] text-muted-foreground">
                        {formatNumberFa(filteredEntries.length)}
                      </span>
                    </div>

                    <div className="flex flex-1 flex-col gap-2">
                      {filteredEntries.map((entry) => (
                        <div
                          key={entry.id}
                          onClick={() => openDetailModal(entry)}
                          className="cursor-pointer rounded-xl border border-white/10 bg-card p-2.5 text-xs transition hover:border-sky-500/50"
                        >
                          <p className="font-semibold text-white truncate">{entry.title}</p>
                          {entry.target_keyword && (
                            <p className="mt-1 text-[10px] text-sky-300 truncate">
                              🎯 {entry.target_keyword}
                            </p>
                          )}
                          <div className="mt-2 flex items-center justify-between">
                            <span className={`rounded px-1.5 py-0.5 text-[9px] ${CALENDAR_STATUS_STYLE[entry.status]}`}>
                              {labelFa(CALENDAR_STATUS_LABELS_FA, entry.status)}
                            </span>
                            <span className={`rounded px-1.5 py-0.5 text-[9px] ${CALENDAR_PRIORITY_STYLE[entry.priority]}`}>
                              {labelFa(CALENDAR_PRIORITY_LABELS_FA, entry.priority)}
                            </span>
                          </div>
                        </div>
                      ))}
                      {filteredEntries.length === 0 && (
                        <div className="p-4 text-center text-[10px] text-muted-foreground/50">
                          بدون محتوا
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* --------------------------------------------------- VIEW: LIST VIEW */}
      {viewMode === "list" && (
        <div className="overflow-hidden rounded-2xl border border-white/10 bg-card/60 backdrop-blur-md">
          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs">
              <thead className="border-b border-white/10 bg-white/5 text-muted-foreground">
                <tr>
                  <th className="p-4 font-semibold text-white">عنوان محتوا</th>
                  <th className="p-4 font-semibold">کلمه کلیدی هدف</th>
                  <th className="p-4 font-semibold">وضعیت</th>
                  <th className="p-4 font-semibold">اولویت</th>
                  <th className="p-4 font-semibold">منبع</th>
                  <th className="p-4 font-semibold">تاریخ انتشار</th>
                  <th className="p-4 font-semibold">مهلت انجام</th>
                  <th className="p-4 font-semibold text-center">عملیات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-slate-300">
                {listView.filter(filterEntry).map((entry) => {
                  const overdue = isOverdue(entry);
                  return (
                    <tr
                      key={entry.id}
                      onClick={() => openDetailModal(entry)}
                      className="cursor-pointer transition hover:bg-white/5"
                    >
                      <td className="p-4 font-semibold text-white">
                        <div className="flex items-center gap-2">
                          <span>{entry.title}</span>
                          {overdue && (
                            <span className="rounded bg-red-500/20 px-1.5 py-0.5 text-[10px] font-bold text-red-300">
                              عقب‌افتاده
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="p-4 text-sky-300">{entry.target_keyword || "—"}</td>
                      <td className="p-4">
                        <span className={`rounded-md px-2 py-0.5 text-[10px] font-medium ${CALENDAR_STATUS_STYLE[entry.status]}`}>
                          {labelFa(CALENDAR_STATUS_LABELS_FA, entry.status)}
                        </span>
                      </td>
                      <td className="p-4">
                        <span className={`rounded-md px-2 py-0.5 text-[10px] font-medium ${CALENDAR_PRIORITY_STYLE[entry.priority]}`}>
                          {labelFa(CALENDAR_PRIORITY_LABELS_FA, entry.priority)}
                        </span>
                      </td>
                      <td className="p-4">
                        {entry.source === "ai_auto" ? (
                          <span className="inline-flex items-center gap-1 text-purple-300">
                            <Sparkles className="h-3 w-3" />
                            هوش مصنوعی
                          </span>
                        ) : (
                          "دستی"
                        )}
                      </td>
                      <td className="p-4">{entry.scheduled_for ? formatDateFa(entry.scheduled_for) : "تعیین نشده"}</td>
                      <td className="p-4">{entry.deadline ? formatDateFa(entry.deadline) : "ندارد"}</td>
                      <td className="p-4 text-center">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setPendingDelete(entry);
                          }}
                          className="rounded-lg p-1.5 text-muted-foreground transition hover:bg-red-500/20 hover:text-red-400"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
                {listView.filter(filterEntry).length === 0 && (
                  <tr>
                    <td colSpan={8} className="p-8 text-center text-muted-foreground">
                      موردی یافت نشد.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ------------------------------------------------ CREATE SLOT MODAL */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-card p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-4">
              <div className="flex items-center gap-2">
                <Plus className="h-5 w-5 text-sky-400" />
                <h2 className="text-base font-bold text-white">افزودن اسلات محتوای جدید</h2>
              </div>
              <button
                onClick={resetCreateForm}
                className="rounded-lg p-1 text-muted-foreground hover:bg-white/10 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={submitCreate} className="mt-4 space-y-4">
              <div>
                <label className="mb-1 block text-xs font-semibold text-white">
                  عنوان محتوا <span className="text-red-400">*</span>
                </label>
                <input
                  value={titleDraft}
                  onChange={(e) => setTitleDraft(e.target.value)}
                  placeholder="مثال: راهنمای جامع خرید پابجی یوسی در سال ۱۴۰۵"
                  required
                  autoFocus
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-white placeholder:text-muted-foreground/60 outline-none focus:border-sky-500"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-white">
                  کلمه کلیدی هدف
                </label>
                <input
                  value={keywordDraft}
                  onChange={(e) => setKeywordDraft(e.target.value)}
                  placeholder="مثال: خرید یوسی پابجی ارزان"
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-white placeholder:text-muted-foreground/60 outline-none focus:border-sky-500"
                />
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-white">
                    تاریخ و ساعت انتشار برنامه‌ریزی‌شده
                  </label>
                  <input
                    type="datetime-local"
                    value={dateDraft}
                    onChange={(e) => setDateDraft(e.target.value)}
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-xs text-white outline-none focus:border-sky-500"
                  />
                </div>

                <div>
                  <label className="mb-1 block text-xs font-semibold text-white">
                    مهلت انجام کار (Deadline)
                  </label>
                  <input
                    type="datetime-local"
                    value={deadlineDraft}
                    onChange={(e) => setDeadlineDraft(e.target.value)}
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-xs text-white outline-none focus:border-sky-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-white">
                    اولویت
                  </label>
                  <select
                    value={priorityDraft}
                    onChange={(e) => setPriorityDraft(e.target.value as CalendarPriority)}
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-xs text-white outline-none focus:border-sky-500"
                  >
                    {CALENDAR_PRIORITIES.map((p) => (
                      <option key={p} value={p} className="bg-card">
                        {CALENDAR_PRIORITY_LABELS_FA[p]}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="mb-1 block text-xs font-semibold text-white">
                    وضعیت اولیه
                  </label>
                  <select
                    value={statusDraft}
                    onChange={(e) => setStatusDraft(e.target.value as CalendarStatus)}
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-xs text-white outline-none focus:border-sky-500"
                  >
                    {CALENDAR_STATUSES.map((s) => (
                      <option key={s} value={s} className="bg-card">
                        {CALENDAR_STATUS_LABELS_FA[s]}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-white">
                  یادداشت و دستورالعمل محتوا (اختیاری)
                </label>
                <textarea
                  rows={3}
                  value={notesDraft}
                  onChange={(e) => setNotesDraft(e.target.value)}
                  placeholder="توضیحات و نکات سئو برای نویسنده..."
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-xs text-white placeholder:text-muted-foreground/60 outline-none focus:border-sky-500"
                />
              </div>

              <div className="flex items-center justify-end gap-3 border-t border-white/10 pt-4">
                <button
                  type="button"
                  onClick={resetCreateForm}
                  className="rounded-xl px-4 py-2 text-xs text-muted-foreground hover:bg-white/5 hover:text-white"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="inline-flex items-center gap-2 rounded-xl bg-sky-500 px-5 py-2 text-xs font-semibold text-white transition hover:bg-sky-600 disabled:opacity-50"
                >
                  {saving && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
                  ذخیره اسلات
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ------------------------------------------- DETAIL / EDIT MODAL */}
      {selectedEntry && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-xl rounded-2xl border border-white/10 bg-card p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-4">
              <div className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-sky-400" />
                <h2 className="text-base font-bold text-white">
                  {editMode ? "ویرایش اسلات محتوا" : "جزئیات اسلات تقویم"}
                </h2>
              </div>
              <div className="flex items-center gap-2">
                {!editMode && (
                  <button
                    onClick={() => setEditMode(true)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white transition hover:bg-white/10"
                  >
                    <Edit3 className="h-3.5 w-3.5 text-sky-400" />
                    ویرایش
                  </button>
                )}
                <button
                  onClick={() => setSelectedEntry(null)}
                  className="rounded-lg p-1 text-muted-foreground hover:bg-white/10 hover:text-white"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            {/* Read / Detail View */}
            {!editMode ? (
              <div className="mt-4 space-y-4">
                <div>
                  <h3 className="text-base font-bold text-white leading-6">
                    {selectedEntry.title}
                  </h3>
                  {selectedEntry.target_keyword && (
                    <p className="mt-1 flex items-center gap-1 text-xs text-sky-300">
                      <Target className="h-3.5 w-3.5" />
                      کلمه کلیدی هدف: <span className="font-semibold">{selectedEntry.target_keyword}</span>
                    </p>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 rounded-xl border border-white/5 bg-black/30 p-3">
                  <div>
                    <span className="text-[10px] text-muted-foreground">وضعیت:</span>
                    <p className="mt-0.5 text-xs font-semibold text-white">
                      {labelFa(CALENDAR_STATUS_LABELS_FA, selectedEntry.status)}
                    </p>
                  </div>
                  <div>
                    <span className="text-[10px] text-muted-foreground">اولویت:</span>
                    <p className="mt-0.5 text-xs font-semibold text-white">
                      {labelFa(CALENDAR_PRIORITY_LABELS_FA, selectedEntry.priority)}
                    </p>
                  </div>
                  <div>
                    <span className="text-[10px] text-muted-foreground">منبع:</span>
                    <p className="mt-0.5 text-xs font-semibold text-white">
                      {labelFa(CALENDAR_SOURCE_LABELS_FA, selectedEntry.source)}
                    </p>
                  </div>
                  <div>
                    <span className="text-[10px] text-muted-foreground">تاریخ انتشار:</span>
                    <p className="mt-0.5 text-xs font-semibold text-white">
                      {selectedEntry.scheduled_for ? formatDateFa(selectedEntry.scheduled_for) : "ندارد"}
                    </p>
                  </div>
                </div>

                {selectedEntry.deadline && (
                  <div className="flex items-center gap-2 rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-amber-300">
                    <Clock className="h-4 w-4 shrink-0" />
                    <span>مهلت تحویل (Deadline): {formatDateFa(selectedEntry.deadline)}</span>
                    {isOverdue(selectedEntry) && (
                      <span className="mr-auto rounded bg-red-500/20 px-2 py-0.5 text-[10px] font-bold text-red-300">
                        مهلت سپری شده!
                      </span>
                    )}
                  </div>
                )}

                {/* AI Opportunity Metadata if scheduled by AI */}
                {selectedEntry.source === "ai_auto" && selectedEntry.details && (
                  <div className="rounded-xl border border-purple-500/30 bg-purple-500/5 p-4">
                    <div className="flex items-center gap-2 text-xs font-bold text-purple-300">
                      <Sparkles className="h-4 w-4" />
                      جزئیات فرصت رشد کشف‌شده توسط هوش مصنوعی
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                      {selectedEntry.details.opportunity_type && (
                        <div className="text-muted-foreground">
                          نوع فرصت: <span className="text-white">{selectedEntry.details.opportunity_type}</span>
                        </div>
                      )}
                      {selectedEntry.details.priority_score !== undefined && (
                        <div className="text-muted-foreground">
                          امتیاز اولویت: <span className="font-bold text-emerald-400">{selectedEntry.details.priority_score} / ۱۰۰</span>
                        </div>
                      )}
                      {selectedEntry.details.estimated_traffic_gain !== undefined && (
                        <div className="text-muted-foreground">
                          ترافیک تخمینی قابل جذب: <span className="font-bold text-sky-300">{formatNumberFa(selectedEntry.details.estimated_traffic_gain)} کلیک</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {selectedEntry.notes && (
                  <div className="rounded-xl border border-white/5 bg-black/20 p-3.5">
                    <span className="text-xs font-semibold text-muted-foreground">یادداشت و توصیه:</span>
                    <p className="mt-1.5 text-xs text-slate-200 leading-relaxed whitespace-pre-wrap">
                      {selectedEntry.notes}
                    </p>
                  </div>
                )}

                {/* Action buttons */}
                <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/10 pt-4">
                  <button
                    onClick={() => {
                      router.push(`/websites/${websiteId}/content`);
                    }}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 px-4 py-2 text-xs font-semibold text-white shadow-md shadow-emerald-500/20 hover:from-emerald-600 hover:to-teal-700"
                  >
                    <FileText className="h-4 w-4" />
                    تولید بریِف و محتوا در Content Hub
                  </button>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setPendingDelete(selectedEntry)}
                      className="rounded-xl border border-red-500/30 bg-red-500/10 px-3.5 py-2 text-xs font-medium text-red-300 hover:bg-red-500/20"
                    >
                      حذف
                    </button>
                    <button
                      onClick={() => setSelectedEntry(null)}
                      className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-white hover:bg-white/5"
                    >
                      بستن
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              /* Edit Form */
              <div className="mt-4 space-y-4">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-white">
                    عنوان محتوا
                  </label>
                  <input
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-white outline-none focus:border-sky-500"
                  />
                </div>

                <div>
                  <label className="mb-1 block text-xs font-semibold text-white">
                    کلمه کلیدی هدف
                  </label>
                  <input
                    value={editKeyword}
                    onChange={(e) => setEditKeyword(e.target.value)}
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-xs text-white outline-none focus:border-sky-500"
                  />
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-xs font-semibold text-white">
                      تاریخ انتشار
                    </label>
                    <input
                      type="datetime-local"
                      value={editDate}
                      onChange={(e) => setEditDate(e.target.value)}
                      className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-xs text-white outline-none focus:border-sky-500"
                    />
                  </div>

                  <div>
                    <label className="mb-1 block text-xs font-semibold text-white">
                      مهلت انجام (Deadline)
                    </label>
                    <input
                      type="datetime-local"
                      value={editDeadline}
                      onChange={(e) => setEditDeadline(e.target.value)}
                      className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-xs text-white outline-none focus:border-sky-500"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-xs font-semibold text-white">
                      وضعیت
                    </label>
                    <select
                      value={editStatus}
                      onChange={(e) => setEditStatus(e.target.value as CalendarStatus)}
                      className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-xs text-white outline-none focus:border-sky-500"
                    >
                      {CALENDAR_STATUSES.map((s) => (
                        <option key={s} value={s} className="bg-card">
                          {CALENDAR_STATUS_LABELS_FA[s]}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="mb-1 block text-xs font-semibold text-white">
                      اولویت
                    </label>
                    <select
                      value={editPriority}
                      onChange={(e) => setEditPriority(e.target.value as CalendarPriority)}
                      className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-xs text-white outline-none focus:border-sky-500"
                    >
                      {CALENDAR_PRIORITIES.map((p) => (
                        <option key={p} value={p} className="bg-card">
                          {CALENDAR_PRIORITY_LABELS_FA[p]}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label className="mb-1 block text-xs font-semibold text-white">
                    یادداشت
                  </label>
                  <textarea
                    rows={3}
                    value={editNotes}
                    onChange={(e) => setEditNotes(e.target.value)}
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-xs text-white outline-none focus:border-sky-500"
                  />
                </div>

                <div className="flex items-center justify-end gap-3 border-t border-white/10 pt-4">
                  <button
                    type="button"
                    onClick={() => setEditMode(false)}
                    className="rounded-xl px-4 py-2 text-xs text-muted-foreground hover:bg-white/5 hover:text-white"
                  >
                    انصراف
                  </button>
                  <button
                    type="button"
                    onClick={submitUpdate}
                    disabled={updating}
                    className="inline-flex items-center gap-2 rounded-xl bg-sky-500 px-5 py-2 text-xs font-semibold text-white hover:bg-sky-600 disabled:opacity-50"
                  >
                    {updating && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
                    ذخیره تغییرات
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <ConfirmDialog
        isOpen={!!pendingDelete}
        title="حذف اسلات محتوا"
        description={
          pendingDelete
            ? `اسلات «${pendingDelete.title}» حذف شود؟ این عمل بازگشت‌پذیر نیست.`
            : ""
        }
        confirmLabel="حذف کن"
        loading={busyId === pendingDelete?.id}
        onConfirm={handleDelete}
        onClose={() => setPendingDelete(null)}
      />
    </div>
  );
}
