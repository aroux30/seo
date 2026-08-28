"use client";

/**
 * Public report viewer — no auth, reached only via a share token.
 *
 * Lives outside the (auth)/(dashboard) route groups on purpose: the dashboard
 * layout redirects to /login whenever there is no session, which would make a
 * "public" link unusable for the client it was shared with.
 *
 * Section bodies are backend-defined and vary by type (weekly/monthly/
 * executive), so rendering stays generic: a table when `rows` is a non-empty
 * array of objects, otherwise the Persian `note` the backend already writes
 * for `has_data: false` sections instead of guessing at a chart.
 */

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError } from "@/lib/api-client";
import { AlertCircle, CalendarDays, Globe, Sparkles } from "lucide-react";

interface PublicReportSection {
  key: string;
  title_fa: string;
  has_data: boolean;
  note?: string;
  rows?: Record<string, any>[];
  [key: string]: any;
}

interface PublicReport {
  report_type: string;
  title: string;
  period_start: string;
  period_end: string;
  generated_at: string | null;
  content: {
    sections?: PublicReportSection[];
    scope?: { level: string; websites: { name: string; domain: string }[] };
    [key: string]: any;
  };
  metrics_snapshot: Record<string, any>;
}

function formatFa(v: any): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return v.toLocaleString("fa-IR");
  return String(v);
}

export default function PublicReportPage() {
  const params = useParams();
  const token = params.token as string;

  const [report, setReport] = useState<PublicReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.get<PublicReport>(`/reports/public/${token}`);
        setReport(data);
      } catch (err: any) {
        setError(
          err instanceof ApiError
            ? "این لینک منقضی شده یا نامعتبر است"
            : "خطا در بارگذاری گزارش"
        );
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  return (
    <div dir="rtl" className="min-h-screen bg-background px-4 py-10 text-foreground">
      <div className="mx-auto max-w-3xl space-y-6">
        {loading && (
          <div className="space-y-3">
            <div className="h-8 w-2/3 animate-pulse rounded-lg bg-white/5" />
            <div className="h-32 animate-pulse rounded-2xl bg-white/5" />
          </div>
        )}

        {!loading && error && (
          <div className="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!loading && report && (
          <>
            <div className="rounded-2xl border border-white/10 bg-card/80 p-6 backdrop-blur-md">
              <div className="flex items-center gap-2 text-xs text-primary">
                <Sparkles className="h-3.5 w-3.5" />
                <span>گزارش عمومی — فقط خواندنی</span>
              </div>
              <h1 className="mt-2 text-2xl font-bold text-white">
                {report.title}
              </h1>
              <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1">
                  <CalendarDays className="h-3.5 w-3.5" />
                  {report.period_start} تا {report.period_end}
                </span>
                {report.content?.scope && (
                  <span className="inline-flex items-center gap-1">
                    <Globe className="h-3.5 w-3.5" />
                    {report.content.scope.level === "organization"
                      ? "کل سازمان"
                      : report.content.scope.websites?.[0]?.domain ?? "یک وب‌سایت"}
                  </span>
                )}
              </div>
            </div>

            {/* Key metrics */}
            {report.metrics_snapshot && (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {Object.entries(report.metrics_snapshot)
                  .filter(([, v]) => typeof v === "number")
                  .slice(0, 8)
                  .map(([key, value]) => (
                    <div
                      key={key}
                      className="rounded-xl border border-white/10 bg-card/60 p-4"
                    >
                      <p className="text-[10px] text-muted-foreground" dir="ltr">
                        {key}
                      </p>
                      <p className="mt-1 text-lg font-bold text-white">
                        {formatFa(value)}
                      </p>
                    </div>
                  ))}
              </div>
            )}

            {/* Sections */}
            <div className="space-y-4">
              {(report.content?.sections ?? []).map((section) => (
                <div
                  key={section.key}
                  className="rounded-2xl border border-white/10 bg-card/60 p-5"
                >
                  <h2 className="text-sm font-semibold text-white">
                    {section.title_fa}
                  </h2>
                  {!section.has_data ? (
                    <p className="mt-2 text-xs text-muted-foreground">
                      {section.note}
                    </p>
                  ) : Array.isArray(section.rows) && section.rows.length > 0 ? (
                    <div className="mt-3 overflow-x-auto">
                      <table className="w-full text-right text-xs">
                        <thead>
                          <tr className="border-b border-white/10 text-muted-foreground">
                            {Object.keys(section.rows[0]).map((col) => (
                              <th key={col} className="px-2 py-1.5 font-medium">
                                {col}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {section.rows.slice(0, 50).map((row, i) => (
                            <tr key={i} className="border-b border-white/5">
                              {Object.keys(section.rows![0]).map((col) => (
                                <td key={col} className="px-2 py-1.5 text-white">
                                  {formatFa(row[col])}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="mt-2 text-xs text-muted-foreground">
                      داده‌ای برای نمایش جدولی در این بخش وجود ندارد.
                    </p>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
