"use client";

/**
 * Reports — organization level (a report can span every website or one).
 *
 * There is no server-side PDF renderer in this project (see report_service's
 * own docstring) — export is CSV, or the browser's print-to-PDF over the
 * on-screen view. Sharing mints a token-based public link that needs no auth;
 * the public viewer lives outside the (dashboard) route group at
 * /reports/public/[token] so it never hits the login redirect.
 *
 * Every hook runs before any conditional return — a hook after an early
 * return reorders the hook list and React rejects it (has broken a page here
 * before).
 */

import { StyledSelect } from "@/components/StyledSelect";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/context/auth-context";
import { ApiError } from "@/lib/api-client";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import {
  listReports,
  getReportSummary,
  getReportTemplates,
  generateReport,
  shareReport,
  revokeReportShare,
  deleteReport,
  downloadReportCsv,
  publicReportUrl,
  isReportTerminal,
  REPORT_TYPE_LABELS_FA,
  REPORT_STATUS_LABELS_FA,
  REPORT_STATUS_STYLE,
  type ReportListItem,
  type ReportSummary,
  type ReportTemplate,
} from "@/lib/reports";
import { formatNumberFa, formatDateFa, labelFa } from "@/lib/insights";
import {
  AlertCircle,
  Copy,
  Download,
  FileBarChart2,
  Globe,
  Link2,
  Plus,
  RefreshCw,
  ShieldOff,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import toast from "react-hot-toast";

const STATUS_TABS: { id: string; label: string }[] = [
  { id: "all", label: "همه" },
  { id: "ready", label: "آماده" },
  { id: "generating", label: "در حال تولید" },
  { id: "pending", label: "در انتظار" },
  { id: "failed", label: "ناموفق" },
];

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function daysAgoIso(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

export default function ReportsPage() {
  const { websites } = useAuth();

  const [reports, setReports] = useState<ReportListItem[]>([]);
  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [templates, setTemplates] = useState<ReportTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<ReportListItem | null>(null);

  // Generate form
  const [generating, setGenerating] = useState(false);
  const [typeDraft, setTypeDraft] = useState("weekly");
  const [websiteDraft, setWebsiteDraft] = useState<string>("");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, sum, tpl] = await Promise.all([
        listReports({
          status: statusFilter === "all" ? undefined : statusFilter,
          limit: 100,
        }),
        getReportSummary(),
        getReportTemplates(),
      ]);
      setReports(Array.isArray(list) ? list : []);
      setSummary(sum);
      setTemplates(Array.isArray(tpl) ? tpl : []);
    } catch (err: any) {
      setError(err instanceof ApiError ? err.message : "خطا در دریافت گزارش‌ها");
      setReports([]);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const isEmpty = !loading && !error && reports.length === 0;

  const activeTemplate = useMemo(
    () => templates.find((t) => t.report_type === typeDraft) || null,
    [templates, typeDraft]
  );

  const submitGenerate = async () => {
    const days = activeTemplate?.default_period_days ?? 7;
    setCreating(true);
    try {
      await generateReport({
        report_type: typeDraft as any,
        period_start: daysAgoIso(days - 1),
        period_end: todayIso(),
        website_id: websiteDraft || null,
      });
      toast.success("تولید گزارش شروع شد");
      setGenerating(false);
      setWebsiteDraft("");
      await load();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در تولید گزارش"
      );
    } finally {
      setCreating(false);
    }
  };

  const handleShare = async (report: ReportListItem) => {
    setBusyId(report.id);
    try {
      const res = await shareReport(report.id);
      const url = publicReportUrl(res.share_token);
      await navigator.clipboard.writeText(url).catch(() => {});
      toast.success("لینک عمومی ساخته و در کلیپ‌بورد کپی شد");
      await load();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در ساخت لینک اشتراک‌گذاری"
      );
    } finally {
      setBusyId(null);
    }
  };

  const handleRevoke = async (report: ReportListItem) => {
    setBusyId(report.id);
    try {
      await revokeReportShare(report.id);
      toast.success("لینک عمومی غیرفعال شد");
      await load();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در لغو لینک اشتراک‌گذاری"
      );
    } finally {
      setBusyId(null);
    }
  };

  const handleDownload = async (report: ReportListItem) => {
    setBusyId(report.id);
    try {
      await downloadReportCsv(report.id, `${report.title}.csv`);
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در دریافت خروجی CSV"
      );
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async () => {
    const report = pendingDelete;
    if (!report) return;
    setBusyId(report.id);
    try {
      await deleteReport(report.id);
      toast.success("گزارش حذف شد");
      setPendingDelete(null);
      await load();
    } catch (err: any) {
      toast.error(err instanceof ApiError ? err.message : "خطا در حذف گزارش");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">گزارش‌ها</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            گزارش‌های هفتگی، ماهانه و اجرایی؛ خروجی CSV یا لینک اشتراک‌گذاری عمومی
          </p>
        </div>
        <button
          onClick={() => setGenerating((v) => !v)}
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-500 to-fuchsia-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-violet-500/20 transition hover:from-violet-600 hover:to-fuchsia-700"
        >
          <Plus className="h-4 w-4" />
          گزارش جدید
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          { label: "کل گزارش‌ها", value: summary?.total, tone: "text-violet-400" },
          { label: "آماده", value: summary?.ready, tone: "text-emerald-400" },
          { label: "در حال تولید", value: summary?.generating, tone: "text-amber-400" },
          { label: "ناموفق", value: summary?.failed, tone: "text-red-400" },
        ].map((card) => (
          <div
            key={card.label}
            className="rounded-2xl border border-white/10 bg-card/80 p-5 backdrop-blur-md"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">
                {card.label}
              </span>
              <FileBarChart2 className={`h-4 w-4 ${card.tone}`} />
            </div>
            <p className="mt-2 text-2xl font-bold text-white">
              {formatNumberFa(card.value)}
            </p>
          </div>
        ))}
      </div>

      {/* Generate form */}
      {generating && (
        <div className="rounded-2xl border border-violet-500/20 bg-violet-500/5 p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-xs font-semibold text-violet-300">
              تولید گزارش جدید
            </span>
            <button
              onClick={() => setGenerating(false)}
              className="rounded-lg p-1 text-muted-foreground transition hover:bg-white/10 hover:text-white"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <StyledSelect
              value={typeDraft}
              onChange={setTypeDraft}
              options={Object.entries(REPORT_TYPE_LABELS_FA).map(([k, v]) => ({
                value: k,
                label: v,
              }))}
            />
            <StyledSelect
              value={websiteDraft}
              onChange={setWebsiteDraft}
              options={[
                { value: "", label: "همه وب‌سایت‌های سازمان" },
                ...websites.map((w) => ({ value: w.id, label: w.domain })),
              ]}
            />
            <button
              onClick={submitGenerate}
              disabled={creating}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-violet-500 px-4 py-2 text-xs font-semibold text-white transition hover:bg-violet-600 disabled:opacity-50"
            >
              {creating ? (
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Sparkles className="h-3.5 w-3.5" />
              )}
              تولید کن
            </button>
          </div>
          {activeTemplate && (
            <p className="mt-3 text-[11px] text-muted-foreground">
              {activeTemplate.description_fa} — بازه پیش‌فرض{" "}
              {formatNumberFa(activeTemplate.default_period_days)} روز، شامل بخش‌های{" "}
              {activeTemplate.sections.map((s) => s.title_fa).join("، ")}
            </p>
          )}
        </div>
      )}

      {/* Status tabs */}
      <div className="flex flex-wrap gap-2">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setStatusFilter(tab.id)}
            className={`rounded-xl px-3.5 py-2 text-xs font-semibold transition ${
              statusFilter === tab.id
                ? "bg-primary text-primary-foreground shadow-md shadow-primary/20"
                : "border border-white/10 bg-white/5 text-muted-foreground hover:text-white"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs text-red-300">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* List */}
      {loading ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-20 animate-pulse rounded-xl bg-white/5" />
          ))}
        </div>
      ) : isEmpty ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-white/15 p-12 text-center">
          <FileBarChart2 className="h-10 w-10 text-muted-foreground/50" />
          <p className="text-sm font-medium text-white">هنوز گزارشی تولید نشده</p>
          <p className="max-w-md text-xs text-muted-foreground">
            یک گزارش هفتگی، ماهانه یا اجرایی بسازید تا خلاصه عملکرد سئو در یک سند
            یک‌جا جمع شود.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {reports.map((report) => {
            const website = report.website_id
              ? websites.find((w) => w.id === report.website_id)
              : null;
            return (
              <div
                key={report.id}
                className="flex flex-col gap-3 rounded-2xl border border-white/10 bg-card/80 p-4 backdrop-blur-md sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-semibold text-white">
                      {report.title}
                    </span>
                    <span
                      className={`shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-medium ${
                        REPORT_STATUS_STYLE[report.status] ??
                        "bg-white/5 text-muted-foreground"
                      }`}
                    >
                      {labelFa(REPORT_STATUS_LABELS_FA, report.status)}
                    </span>
                    {report.share_enabled && (
                      <span className="inline-flex shrink-0 items-center gap-1 rounded-md bg-sky-500/15 px-1.5 py-0.5 text-[10px] text-sky-300">
                        <Link2 className="h-2.5 w-2.5" />
                        عمومی
                      </span>
                    )}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                    <span>
                      {labelFa(REPORT_TYPE_LABELS_FA, report.report_type)}
                    </span>
                    <span>·</span>
                    <span>
                      {formatDateFa(report.period_start)} تا{" "}
                      {formatDateFa(report.period_end)}
                    </span>
                    <span>·</span>
                    <span className="inline-flex items-center gap-1">
                      <Globe className="h-3 w-3" />
                      {website ? website.domain : "کل سازمان"}
                    </span>
                    {report.view_count > 0 && (
                      <>
                        <span>·</span>
                        <span>{formatNumberFa(report.view_count)} بازدید</span>
                      </>
                    )}
                  </div>
                </div>

                <div className="flex shrink-0 items-center gap-1.5">
                  {report.status === "ready" && (
                    <>
                      <button
                        onClick={() => handleDownload(report)}
                        disabled={busyId === report.id}
                        title="دریافت CSV"
                        className="rounded-lg p-2 text-muted-foreground transition hover:bg-white/10 hover:text-white disabled:opacity-50"
                      >
                        <Download className="h-4 w-4" />
                      </button>
                      {report.share_enabled ? (
                        <button
                          onClick={() => handleRevoke(report)}
                          disabled={busyId === report.id}
                          title="لغو لینک عمومی"
                          className="rounded-lg p-2 text-muted-foreground transition hover:bg-amber-500/15 hover:text-amber-400 disabled:opacity-50"
                        >
                          <ShieldOff className="h-4 w-4" />
                        </button>
                      ) : (
                        <button
                          onClick={() => handleShare(report)}
                          disabled={busyId === report.id}
                          title="ساخت لینک عمومی"
                          className="rounded-lg p-2 text-muted-foreground transition hover:bg-sky-500/15 hover:text-sky-400 disabled:opacity-50"
                        >
                          <Copy className="h-4 w-4" />
                        </button>
                      )}
                    </>
                  )}
                  <button
                    onClick={() => setPendingDelete(report)}
                    disabled={busyId === report.id}
                    title="حذف"
                    className="rounded-lg p-2 text-muted-foreground transition hover:bg-red-500/15 hover:text-red-400 disabled:opacity-50"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <ConfirmDialog
        isOpen={!!pendingDelete}
        title="حذف گزارش"
        description={
          pendingDelete
            ? `گزارش «${pendingDelete.title}» حذف شود؟ این عمل بازگشت‌پذیر نیست.`
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
