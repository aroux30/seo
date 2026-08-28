"use client";

import React, { useEffect, useState } from "react";
import { X, History, ArrowRight, ArrowLeft, RotateCcw } from "lucide-react";
import {
  ContentVersionListItem,
  ContentVersionSummary,
  ContentVersionDiff,
  listVersions,
  getVersionSummary,
  diffVersions,
  rollbackToVersion,
  CHANGE_TYPE_LABELS_FA,
  formatDiffStatsFa,
  formatScoreDeltaFa,
  changeAuthorLabelFa,
} from "@/lib/versions";
import toast from "react-hot-toast";

interface Props {
  articleId: string;
  isOpen: boolean;
  onClose: () => void;
  onRollbackComplete: () => void;
}

export function VersionHistoryPanel({ articleId, isOpen, onClose, onRollbackComplete }: Props) {
  const [summary, setSummary] = useState<ContentVersionSummary | null>(null);
  const [versions, setVersions] = useState<ContentVersionListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingDiff, setLoadingDiff] = useState(false);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [diff, setDiff] = useState<ContentVersionDiff | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadData();
    }
  }, [isOpen]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [sumRes, listRes] = await Promise.all([
        getVersionSummary(articleId),
        listVersions({ article_id: articleId }),
      ]);
      setSummary(sumRes);
      setVersions(listRes);
      if (listRes.length > 0) {
        // Select the latest non-current or just latest if it's the only one
        const initial = listRes.length > 1 ? listRes[1] : listRes[0];
        setSelectedVersion(initial.version_number);
      }
    } catch (err) {
      toast.error("خطا در دریافت تاریخچه نسخه‌ها");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedVersion !== null && summary?.current_version_number) {
      loadDiff(selectedVersion, summary.current_version_number);
    }
  }, [selectedVersion, summary]);

  const loadDiff = async (fromNum: number, toNum: number) => {
    setLoadingDiff(true);
    try {
      const res = await diffVersions({
        article_id: articleId,
        from_version: fromNum,
        to_version: toNum,
      });
      setDiff(res);
    } catch (err) {
      toast.error("خطا در دریافت تفاوت نسخه‌ها");
    } finally {
      setLoadingDiff(false);
    }
  };

  const handleRollback = async () => {
    if (!selectedVersion) return;
    const versionRow = versions.find((v) => v.version_number === selectedVersion);
    if (!versionRow) return;

    if (!confirm(`آیا از بازگردانی مقاله به نسخه ${selectedVersion} اطمینان دارید؟`)) return;

    try {
      await rollbackToVersion(versionRow.id, {
        change_summary: `بازگردانی دستی به نسخه ${selectedVersion}`,
      });
      toast.success("مقاله با موفقیت به نسخه انتخابی بازگردانی شد.");
      onRollbackComplete();
    } catch (err) {
      toast.error("خطا در بازگردانی نسخه");
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-start bg-black/60 backdrop-blur-sm" dir="rtl">
      {/* Slide-over panel */}
      <div className="w-full max-w-4xl h-full bg-slate-950 border-l border-slate-800 flex flex-col shadow-2xl animate-in slide-in-from-right duration-300">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-500/20 text-indigo-400 rounded-lg">
              <History className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">تاریخچه تغییرات مقاله</h2>
              <p className="text-xs text-slate-400 mt-1">
                {summary ? `${summary.total_versions} نسخه ثبت شده توسط ${summary.contributors} مشارکت‌کننده` : "در حال دریافت..."}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left: Versions List */}
          <div className="w-64 border-l border-slate-800 flex flex-col bg-slate-900/30">
            <div className="p-4 border-b border-slate-800 font-medium text-sm text-slate-300">
              لیست نسخه‌ها
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {loading ? (
                <p className="text-center text-xs text-slate-500 py-4">در حال بارگذاری...</p>
              ) : (
                versions.map((v) => (
                  <button
                    key={v.id}
                    onClick={() => setSelectedVersion(v.version_number)}
                    className={`w-full text-right p-3 rounded-lg text-xs transition-colors ${
                      selectedVersion === v.version_number
                        ? "bg-indigo-600 border-indigo-500 text-white shadow-md"
                        : "bg-transparent text-slate-400 hover:bg-slate-800/50 border-transparent border"
                    }`}
                  >
                    <div className="flex justify-between items-center mb-1.5">
                      <span className={`font-bold ${v.is_current ? "text-emerald-400" : ""}`}>
                        نسخه {v.version_number} {v.is_current && "(فعلی)"}
                      </span>
                      <span className="opacity-70 text-[10px]">
                        {new Date(v.created_at).toLocaleDateString("fa-IR")}
                      </span>
                    </div>
                    <div className="text-[10px] opacity-80 mb-1">
                      {CHANGE_TYPE_LABELS_FA[v.change_type] || v.change_type}
                    </div>
                    <div className="text-[10px] opacity-60">
                      توسط: {changeAuthorLabelFa(v) || v.changed_by}
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>

          {/* Right: Diff Viewer */}
          <div className="flex-1 flex flex-col bg-slate-950 overflow-hidden">
            {diff ? (
              <>
                <div className="p-5 border-b border-slate-800 bg-slate-900/40">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-4 text-sm font-medium">
                      <div className="text-rose-400 bg-rose-400/10 px-3 py-1.5 rounded-lg border border-rose-400/20">
                        نسخه {diff.from_version_number}
                      </div>
                      <ArrowLeft className="w-4 h-4 text-slate-600" />
                      <div className="text-emerald-400 bg-emerald-400/10 px-3 py-1.5 rounded-lg border border-emerald-400/20">
                        نسخه فعلی ({diff.to_version_number})
                      </div>
                    </div>
                    <button
                      onClick={handleRollback}
                      disabled={diff.from_version_number === summary?.current_version_number}
                      className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-xs font-medium transition-colors shadow-lg shadow-indigo-600/20"
                    >
                      <RotateCcw className="w-4 h-4" />
                      بازگردانی به این نسخه
                    </button>
                  </div>
                  <div className="flex gap-4 text-xs">
                    <span className="text-slate-300">
                      تغییرات: {formatDiffStatsFa(diff.stats)}
                    </span>
                    {diff.seo_score_delta !== 0 && (
                      <span className={diff.seo_score_delta > 0 ? "text-emerald-400" : "text-rose-400"}>
                        {formatScoreDeltaFa(diff.seo_score_delta)}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex-1 overflow-y-auto p-6 font-mono text-xs leading-loose bg-slate-950">
                  {loadingDiff ? (
                    <div className="flex items-center justify-center h-full text-slate-500">
                      در حال مقایسه...
                    </div>
                  ) : diff.identical ? (
                    <div className="flex items-center justify-center h-full text-slate-500">
                      محتوای این دو نسخه کاملاً یکسان است.
                    </div>
                  ) : (
                    <div className="space-y-1">
                      {diff.lines.map((line, idx) => {
                        let colorClass = "text-slate-400";
                        let bgClass = "bg-transparent";
                        if (line.kind === "added") {
                          colorClass = "text-emerald-300";
                          bgClass = "bg-emerald-950/40";
                        } else if (line.kind === "removed") {
                          colorClass = "text-rose-300";
                          bgClass = "bg-rose-950/40";
                        } else if (line.kind === "hunk") {
                          colorClass = "text-indigo-400";
                          bgClass = "bg-indigo-950/20";
                        } else if (line.kind === "header") {
                          return null;
                        }

                        return (
                          <div
                            key={idx}
                            className={`px-3 py-1 rounded whitespace-pre-wrap break-words ${bgClass} ${colorClass}`}
                          >
                            <span className="opacity-50 mr-2 select-none">
                              {line.kind === "added" ? "+" : line.kind === "removed" ? "-" : " "}
                            </span>
                            {line.text}
                          </div>
                        );
                      })}
                      {diff.truncated && (
                        <div className="text-center py-4 text-amber-500/80 italic mt-4 bg-amber-950/20 rounded-lg">
                          ادامه تغییرات به دلیل حجم بالا نمایش داده نمی‌شود.
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="flex flex-1 items-center justify-center text-slate-500 text-sm">
                یک نسخه را برای مشاهده تفاوت با نسخه فعلی انتخاب کنید.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
