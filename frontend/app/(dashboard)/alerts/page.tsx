"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/context/auth-context";
import { ApiError } from "@/lib/api-client";
import { StyledSelect } from "@/components/StyledSelect";
import {
  listAlerts,
  getAlertSummary,
  updateAlertStatus,
  formatNumberFa,
  formatDateTimeFa,
  labelFa,
  ALERT_TYPE_LABELS_FA,
  ALERT_SEVERITY_LABELS_FA,
  ALERT_STATUS_LABELS_FA,
  type Alert,
  type AlertSummary,
} from "@/lib/insights";
import {
  ShieldAlert,
  AlertTriangle,
  Info,
  CheckCircle2,
  RefreshCw,
  Search,
  Filter,
  Clock,
  X,
  Globe,
} from "lucide-react";
import toast from "react-hot-toast";

const STATUS_TABS: { id: string; label: string }[] = [
  { id: "active", label: "فعال" },
  { id: "acknowledged", label: "تایید شده" },
  { id: "resolved", label: "برطرف شده" },
  { id: "muted", label: "بی‌صدا شده" },
  { id: "all", label: "همه" },
];

const SEVERITY_FILTERS: { id: string; label: string }[] = [
  { id: "all", label: "همه شدت‌ها" },
  { id: "critical", label: "بحرانی" },
  { id: "warning", label: "هشدار" },
  { id: "info", label: "اطلاعات" },
];

function severityBadge(severity: string) {
  switch (severity) {
    case "critical":
      return (
        <span className="inline-flex items-center gap-1 rounded-full border border-rose-500/20 bg-rose-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-rose-400">
          <ShieldAlert className="h-3.5 w-3.5" />
          {labelFa(ALERT_SEVERITY_LABELS_FA, severity)}
        </span>
      );
    case "warning":
      return (
        <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/20 bg-amber-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-amber-400">
          <AlertTriangle className="h-3.5 w-3.5" />
          {labelFa(ALERT_SEVERITY_LABELS_FA, severity)}
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 rounded-full border border-blue-500/20 bg-blue-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-blue-400">
          <Info className="h-3.5 w-3.5" />
          {labelFa(ALERT_SEVERITY_LABELS_FA, severity)}
        </span>
      );
  }
}

function statusStyle(status: string): string {
  switch (status) {
    case "active":
      return "bg-rose-500/15 text-rose-400";
    case "acknowledged":
      return "bg-blue-500/15 text-blue-400";
    case "resolved":
      return "bg-emerald-500/15 text-emerald-400";
    case "muted":
      return "bg-white/5 text-muted-foreground";
    default:
      return "bg-white/5 text-muted-foreground";
  }
}

export default function AlertsPage() {
  const { websites } = useAuth();

  const [items, setItems] = useState<Alert[]>([]);
  const [summary, setSummary] = useState<AlertSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("active");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [websiteFilter, setWebsiteFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  // Resolve modal state
  const [resolveTarget, setResolveTarget] = useState<Alert | null>(null);
  const [resolutionNote, setResolutionNote] = useState("");

  // Mute modal state
  const [muteTarget, setMuteTarget] = useState<Alert | null>(null);
  const [muteHours, setMuteHours] = useState(24);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, sum] = await Promise.all([
        listAlerts({
          website_id: websiteFilter === "all" ? undefined : websiteFilter,
          status: statusFilter === "all" ? undefined : statusFilter,
          severity: severityFilter === "all" ? undefined : severityFilter,
          limit: 100,
        }),
        getAlertSummary(),
      ]);
      setItems(Array.isArray(list) ? list : []);
      setSummary(sum);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("خطا در دریافت هشدارها");
      }
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, severityFilter, websiteFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const websiteNameById = useMemo(() => {
    const map: Record<string, string> = {};
    websites.forEach((w) => {
      map[w.id] = w.domain;
    });
    return map;
  }, [websites]);

  const visibleItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter((a) => {
      const haystack = [a.title, a.message, a.metric_name]
        .filter((v): v is string => typeof v === "string" && v.length > 0)
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [items, search]);

  const changeStatus = async (
    alert: Alert,
    status: "active" | "acknowledged" | "resolved" | "muted",
    extra?: { resolution_note?: string; mute_hours?: number }
  ) => {
    setBusyId(alert.id);
    try {
      await updateAlertStatus(alert.id, { status, ...extra });
      toast.success("وضعیت هشدار بروزرسانی شد");
      setResolveTarget(null);
      setResolutionNote("");
      setMuteTarget(null);
      setMuteHours(24);
      await load();
    } catch (err: any) {
      toast.error(err instanceof ApiError ? err.message : "خطا در بروزرسانی هشدار");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">هشدارهای سئو (Alerts)</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            افت ترافیک، رتبه، نرخ کلیک و مشکلات فنی در سطح سازمان
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-white/10 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          {loading ? "در حال بروزرسانی..." : "بروزرسانی"}
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">هشدارهای فعال</span>
            <div className="rounded-xl bg-primary/10 p-2 text-primary">
              <ShieldAlert className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 text-3xl font-bold text-white">
            {summary ? formatNumberFa(summary.active) : "—"}
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">بحرانی</span>
            <div className="rounded-xl bg-rose-500/10 p-2 text-rose-400">
              <ShieldAlert className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 text-3xl font-bold text-rose-400">
            {summary ? formatNumberFa(summary.critical) : "—"}
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">هشدار</span>
            <div className="rounded-xl bg-amber-500/10 p-2 text-amber-400">
              <AlertTriangle className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 text-3xl font-bold text-amber-400">
            {summary ? formatNumberFa(summary.warning) : "—"}
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">اطلاعاتی</span>
            <div className="rounded-xl bg-blue-500/10 p-2 text-blue-400">
              <Info className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 text-3xl font-bold text-blue-400">
            {summary ? formatNumberFa(summary.info) : "—"}
          </div>
        </div>
      </div>

      {error && (
        <div className="flex flex-col gap-3 rounded-2xl border border-rose-500/20 bg-rose-500/10 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-xs leading-relaxed text-rose-300">
            <span className="font-semibold">خطا: </span>
            {error}
          </div>
          <button
            onClick={load}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-rose-500/30 px-3 py-2 text-xs font-semibold text-rose-200 transition hover:bg-rose-500/10"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            تلاش مجدد
          </button>
        </div>
      )}

      {/* Filters */}
      <div className="rounded-2xl border border-white/10 bg-card/60 p-4 backdrop-blur-md">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap items-center gap-1 rounded-xl bg-white/5 p-1">
            {STATUS_TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setStatusFilter(tab.id)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                  statusFilter === tab.id
                    ? "bg-white/10 text-white shadow-sm"
                    : "text-muted-foreground hover:text-white"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative">
              <Search className="absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="جستجو در عنوان یا پیام"
                className="w-full rounded-xl border border-white/10 bg-black/40 py-2 pr-9 pl-3 text-xs text-white placeholder-muted-foreground focus:border-primary focus:outline-none sm:w-56"
              />
            </div>

            <div className="sm:w-48">
              <StyledSelect
                value={websiteFilter}
                onChange={setWebsiteFilter}
                options={[
                  { value: "all", label: "همه وب‌سایت‌ها" },
                  ...websites.map((w) => ({ value: w.id, label: w.domain })),
                ]}
                placeholder="همه وب‌سایت‌ها"
              />
            </div>

            <div className="sm:w-40">
              <StyledSelect
                value={severityFilter}
                onChange={setSeverityFilter}
                options={SEVERITY_FILTERS.map((s) => ({ value: s.id, label: s.label }))}
                placeholder="فیلتر شدت"
              />
            </div>
          </div>
        </div>
      </div>

      {/* List */}
      {loading ? (
        <div className="space-y-3">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="animate-pulse rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur-md"
            >
              <div className="h-2.5 w-32 rounded bg-white/10" />
              <div className="mt-4 h-4 w-2/3 rounded bg-white/[0.07]" />
              <div className="mt-3 h-2 w-full rounded bg-white/[0.05]" />
            </div>
          ))}
        </div>
      ) : visibleItems.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-white/10 bg-card/60 py-16 text-center backdrop-blur-md">
          <ShieldAlert className="mx-auto h-10 w-10 text-muted-foreground/50" />
          <h3 className="mt-3 text-sm font-semibold text-white">
            {items.length === 0 ? "هشداری با این فیلترها یافت نشد" : "نتیجه‌ای برای این جستجو یافت نشد"}
          </h3>
          <p className="mx-auto mt-1 max-w-sm text-xs leading-relaxed text-muted-foreground">
            {items.length === 0
              ? "به‌محض افت ترافیک، رتبه یا بروز خطای فنی، هشدار جدید همین‌جا نمایش داده می‌شود."
              : "عبارت جستجو را تغییر دهید یا فیلترها را بازنشانی کنید."}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {visibleItems.map((a) => (
            <div
              key={a.id}
              className="rounded-2xl border border-white/10 bg-card/60 p-5 shadow-lg backdrop-blur-md transition hover:border-white/20"
            >
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0 flex-1 space-y-2.5">
                  <div className="flex flex-wrap items-center gap-2">
                    {severityBadge(a.severity)}
                    <span className="rounded-full bg-white/5 px-2.5 py-0.5 text-[11px] font-semibold text-muted-foreground">
                      {labelFa(ALERT_TYPE_LABELS_FA, a.alert_type)}
                    </span>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${statusStyle(
                        a.status
                      )}`}
                    >
                      {labelFa(ALERT_STATUS_LABELS_FA, a.status)}
                    </span>
                    {websiteNameById[a.website_id] && (
                      <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground" dir="ltr">
                        <Globe className="h-3 w-3" />
                        {websiteNameById[a.website_id]}
                      </span>
                    )}
                    {a.occurrence_count > 1 && (
                      <span className="text-[11px] text-muted-foreground">
                        تکرار: {formatNumberFa(a.occurrence_count)} بار
                      </span>
                    )}
                  </div>

                  <h3 className="text-sm font-bold text-white">{a.title}</h3>
                  <p className="text-xs leading-relaxed text-muted-foreground">{a.message}</p>

                  {(a.metric_name || a.change_percent !== null) && (
                    <div className="flex flex-wrap items-center gap-4 border-t border-white/5 pt-3 text-[11px]">
                      {a.metric_name && (
                        <span className="text-muted-foreground">
                          شاخص: <span className="font-bold text-white">{a.metric_name}</span>
                        </span>
                      )}
                      {a.current_value !== null && (
                        <span className="text-muted-foreground">
                          مقدار فعلی:{" "}
                          <span className="font-bold text-white">
                            {formatNumberFa(a.current_value)}
                          </span>
                        </span>
                      )}
                      {a.previous_value !== null && (
                        <span className="text-muted-foreground">
                          مقدار قبلی:{" "}
                          <span className="font-bold text-white">
                            {formatNumberFa(a.previous_value)}
                          </span>
                        </span>
                      )}
                      {a.change_percent !== null && (
                        <span
                          className={`font-bold ${
                            a.change_percent < 0 ? "text-rose-400" : "text-emerald-400"
                          }`}
                        >
                          {a.change_percent > 0 ? "+" : ""}
                          {formatNumberFa(Math.round(a.change_percent * 10) / 10)}٪
                        </span>
                      )}
                    </div>
                  )}

                  <div className="flex flex-wrap items-center gap-4 text-[11px] text-muted-foreground">
                    <span>ثبت اولیه: {formatDateTimeFa(a.triggered_at)}</span>
                    {a.last_seen_at && <span>آخرین مشاهده: {formatDateTimeFa(a.last_seen_at)}</span>}
                    {a.status === "muted" && a.muted_until && (
                      <span className="text-amber-400">
                        بی‌صدا تا: {formatDateTimeFa(a.muted_until)}
                      </span>
                    )}
                  </div>

                  {a.status === "resolved" && a.resolution_note && (
                    <div className="rounded-lg border border-white/10 bg-white/[0.02] p-2.5 text-[11px] text-muted-foreground">
                      <span className="font-semibold">یادداشت رفع مشکل: </span>
                      {a.resolution_note}
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="flex shrink-0 flex-wrap gap-2 lg:flex-col">
                  {a.status === "active" && (
                    <button
                      onClick={() => changeStatus(a, "acknowledged")}
                      disabled={busyId === a.id}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-blue-500/20 bg-blue-500/10 px-3 py-2 text-xs font-semibold text-blue-400 transition hover:bg-blue-500/20 disabled:opacity-50"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      تایید مشاهده
                    </button>
                  )}
                  {a.status !== "resolved" && (
                    <button
                      onClick={() => {
                        setResolveTarget(a);
                        setResolutionNote("");
                      }}
                      disabled={busyId === a.id}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-xs font-semibold text-emerald-400 transition hover:bg-emerald-500/20 disabled:opacity-50"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      رفع شد
                    </button>
                  )}
                  {a.status !== "muted" && a.status !== "resolved" && (
                    <button
                      onClick={() => {
                        setMuteTarget(a);
                        setMuteHours(24);
                      }}
                      disabled={busyId === a.id}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-muted-foreground transition hover:bg-white/10 hover:text-white disabled:opacity-50"
                    >
                      <Clock className="h-3.5 w-3.5" />
                      بی‌صدا کردن
                    </button>
                  )}
                  {(a.status === "resolved" || a.status === "muted") && (
                    <button
                      onClick={() => changeStatus(a, "active")}
                      disabled={busyId === a.id}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-muted-foreground transition hover:bg-white/10 hover:text-white disabled:opacity-50"
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                      بازگردانی به فعال
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Resolve modal */}
      {resolveTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md space-y-4 rounded-2xl border border-white/10 bg-card p-6 shadow-2xl">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="h-6 w-6 shrink-0 text-emerald-400" />
              <h3 className="text-base font-bold text-white">رفع هشدار</h3>
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground">
              هشدار «{resolveTarget.title}» به‌عنوان رفع‌شده علامت می‌خورد.
            </p>
            <textarea
              value={resolutionNote}
              onChange={(e) => setResolutionNote(e.target.value)}
              rows={3}
              maxLength={1000}
              placeholder="یادداشت رفع مشکل (اختیاری)"
              className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-xs text-white placeholder-muted-foreground focus:border-primary focus:outline-none"
            />
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => {
                  setResolveTarget(null);
                  setResolutionNote("");
                }}
                className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-muted-foreground transition hover:bg-white/5"
              >
                انصراف
              </button>
              <button
                type="button"
                onClick={() =>
                  changeStatus(resolveTarget, "resolved", {
                    resolution_note: resolutionNote.trim() || undefined,
                  })
                }
                disabled={busyId === resolveTarget.id}
                className="rounded-xl bg-emerald-600 px-5 py-2 text-xs font-semibold text-white shadow-lg transition hover:bg-emerald-500 disabled:opacity-50"
              >
                {busyId === resolveTarget.id ? "در حال ثبت..." : "ثبت رفع مشکل"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Mute modal */}
      {muteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md space-y-4 rounded-2xl border border-white/10 bg-card p-6 shadow-2xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Clock className="h-6 w-6 shrink-0 text-amber-400" />
                <h3 className="text-base font-bold text-white">بی‌صدا کردن هشدار</h3>
              </div>
              <button
                onClick={() => setMuteTarget(null)}
                className="rounded-lg p-1 text-muted-foreground transition hover:bg-white/10 hover:text-white"
                aria-label="بستن"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground">
              هشدار «{muteTarget.title}» تا مدت انتخاب‌شده اعلان‌رسانی نمی‌کند.
            </p>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                مدت بی‌صدا شدن (ساعت)
              </label>
              <input
                type="number"
                min={1}
                max={720}
                value={muteHours}
                onChange={(e) => setMuteHours(Number(e.target.value))}
                className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-xs text-white focus:border-primary focus:outline-none"
              />
            </div>
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setMuteTarget(null)}
                className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-muted-foreground transition hover:bg-white/5"
              >
                انصراف
              </button>
              <button
                type="button"
                onClick={() =>
                  changeStatus(muteTarget, "muted", {
                    mute_hours: Math.min(720, Math.max(1, Math.round(muteHours))),
                  })
                }
                disabled={busyId === muteTarget.id}
                className="rounded-xl bg-amber-600 px-5 py-2 text-xs font-semibold text-white shadow-lg transition hover:bg-amber-500 disabled:opacity-50"
              >
                {busyId === muteTarget.id ? "در حال ثبت..." : "بی‌صدا کردن"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
