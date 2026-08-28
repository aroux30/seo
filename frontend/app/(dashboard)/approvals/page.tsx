"use client";

/**
 * Approval queue — organization level.
 *
 * Two rules from the backend are mirrored in the UI so a reviewer is not shown
 * a button that will 403:
 *
 * - A member cannot decide on their own request (self-approval is refused by
 *   `_assert_can_decide`), so Approve/Reject are hidden on rows the current user
 *   filed.
 * - Deciding needs seo_manager+; cancelling needs to be the requester (or
 *   admin+). The role floor is read from `currentOrg.my_role`.
 *
 * The list endpoint resolves `mine_only` / `assigned_to_me` from the session
 * rather than from a user id, so those are booleans here too.
 */

import { StyledSelect } from "@/components/StyledSelect";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/context/auth-context";
import { ApiError } from "@/lib/api-client";
import {
  listApprovals,
  getApprovalSummary,
  decideApproval,
  cancelApproval,
  expireStaleApprovals,
  APPROVAL_ACTION_LABELS_FA,
  APPROVAL_STATUS_LABELS_FA,
  APPROVAL_PRIORITY_LABELS_FA,
  APPROVAL_RISK_LABELS_FA,
  APPROVAL_ACTION_CATEGORIES_FA,
  isApprovalTerminal,
  isExpiringSoon,
  formatExpiryFa,
  type ApprovalRequestWithNames,
  type ApprovalSummary,
} from "@/lib/approvals";
import {
  formatNumberFa,
  formatDateTimeFa,
  labelFa,
} from "@/lib/insights";
import {
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  Clock,
  RefreshCw,
  Filter,
  X,
  User,
  Globe,
  FileText,
  Eye,
} from "lucide-react";
import toast from "react-hot-toast";

const STATUS_TABS: { id: string; label: string }[] = [
  { id: "pending", label: "در انتظار بررسی" },
  { id: "approved", label: "تأییدشده" },
  { id: "rejected", label: "ردشده" },
  { id: "cancelled", label: "لغوشده" },
  { id: "executed", label: "اجراشده" },
  { id: "failed", label: "ناموفق" },
  { id: "all", label: "همه" },
];

const PRIORITY_FILTERS: { id: string; label: string }[] = [
  { id: "all", label: "همه اولویت‌ها" },
  { id: "urgent", label: "فوری" },
  { id: "high", label: "بالا" },
  { id: "normal", label: "معمولی" },
  { id: "low", label: "پایین" },
];

const SCOPE_FILTERS: { id: "all" | "mine" | "assigned"; label: string }[] = [
  { id: "all", label: "کل صف" },
  { id: "mine", label: "درخواست‌های من" },
  { id: "assigned", label: "واگذارشده به من" },
];

/** Rank order must match ROLE_HIERARCHY in backend/app/core/security.py. */
const ROLE_RANK: Record<string, number> = {
  owner: 60,
  admin: 50,
  seo_manager: 40,
  editor: 30,
  reviewer: 20,
  viewer: 10,
};

function riskBadge(risk: string) {
  const common =
    "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold";
  switch (risk) {
    case "critical":
      return (
        <span className={`${common} border-rose-500/20 bg-rose-500/10 text-rose-400`}>
          <ShieldAlert className="h-3.5 w-3.5" />
          {labelFa(APPROVAL_RISK_LABELS_FA, risk)}
        </span>
      );
    case "high":
      return (
        <span className={`${common} border-amber-500/20 bg-amber-500/10 text-amber-400`}>
          <AlertTriangle className="h-3.5 w-3.5" />
          {labelFa(APPROVAL_RISK_LABELS_FA, risk)}
        </span>
      );
    case "medium":
      return (
        <span className={`${common} border-sky-500/20 bg-sky-500/10 text-sky-400`}>
          {labelFa(APPROVAL_RISK_LABELS_FA, risk)}
        </span>
      );
    default:
      return (
        <span className={`${common} border-slate-500/20 bg-slate-500/10 text-slate-400`}>
          {labelFa(APPROVAL_RISK_LABELS_FA, risk)}
        </span>
      );
  }
}

function priorityBadge(priority: string) {
  const common =
    "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold";
  switch (priority) {
    case "urgent":
      return (
        <span className={`${common} border-rose-500/20 bg-rose-500/10 text-rose-400`}>
          {labelFa(APPROVAL_PRIORITY_LABELS_FA, priority)}
        </span>
      );
    case "high":
      return (
        <span className={`${common} border-orange-500/20 bg-orange-500/10 text-orange-400`}>
          {labelFa(APPROVAL_PRIORITY_LABELS_FA, priority)}
        </span>
      );
    case "low":
      return (
        <span className={`${common} border-slate-500/20 bg-slate-500/10 text-slate-500`}>
          {labelFa(APPROVAL_PRIORITY_LABELS_FA, priority)}
        </span>
      );
    default:
      return (
        <span className={`${common} border-slate-500/20 bg-slate-500/10 text-slate-400`}>
          {labelFa(APPROVAL_PRIORITY_LABELS_FA, priority)}
        </span>
      );
  }
}

function statusBadge(status: string) {
  const common =
    "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold";
  switch (status) {
    case "pending":
      return (
        <span className={`${common} border-amber-500/20 bg-amber-500/10 text-amber-400`}>
          <Clock className="h-3.5 w-3.5" />
          {labelFa(APPROVAL_STATUS_LABELS_FA, status)}
        </span>
      );
    case "approved":
    case "executed":
      return (
        <span className={`${common} border-emerald-500/20 bg-emerald-500/10 text-emerald-400`}>
          <CheckCircle2 className="h-3.5 w-3.5" />
          {labelFa(APPROVAL_STATUS_LABELS_FA, status)}
        </span>
      );
    case "rejected":
    case "failed":
      return (
        <span className={`${common} border-rose-500/20 bg-rose-500/10 text-rose-400`}>
          <X className="h-3.5 w-3.5" />
          {labelFa(APPROVAL_STATUS_LABELS_FA, status)}
        </span>
      );
    default:
      return (
        <span className={`${common} border-slate-500/20 bg-slate-500/10 text-slate-400`}>
          {labelFa(APPROVAL_STATUS_LABELS_FA, status)}
        </span>
      );
  }
}

/** True when a still-pending row is inside its final 24 hours.
 *
 * The deadline arithmetic itself lives in `lib/approvals` and is shared with
 * `formatExpiryFa`, so the badge and the countdown text cannot disagree about
 * what "soon" means. Only the pending check is added here: an already-decided
 * row keeps its `expires_at` but is no longer waiting on anyone.
 */
function isPendingExpiringSoon(row: ApprovalRequestWithNames): boolean {
  return row.status === "pending" && isExpiringSoon(row.expires_at);
}

export default function ApprovalsPage() {
  const { user, currentOrg } = useAuth();

  const [rows, setRows] = useState<ApprovalRequestWithNames[]>([]);
  const [summary, setSummary] = useState<ApprovalSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [sweeping, setSweeping] = useState(false);

  const [statusTab, setStatusTab] = useState("pending");
  const [priorityFilter, setPriorityFilter] = useState("all");
  const [scope, setScope] = useState<"all" | "mine" | "assigned">("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Decision modal state. Kept as one object so opening it cannot leave a
  // stale comment from the previous row.
  const [decisionModal, setDecisionModal] = useState<{
    row: ApprovalRequestWithNames;
    decision: "approved" | "rejected";
    comment: string;
  } | null>(null);

  const myRole = currentOrg?.my_role ?? "viewer";
  const myRank = ROLE_RANK[myRole] ?? 0;
  const canDecide = myRank >= ROLE_RANK.seo_manager;
  const canSweep = myRank >= ROLE_RANK.admin;

  const load = useCallback(async () => {
    if (!currentOrg) return;
    setLoading(true);
    try {
      const [listRes, summaryRes] = await Promise.all([
        listApprovals({
          status: statusTab === "all" ? undefined : statusTab,
          priority: priorityFilter === "all" ? undefined : priorityFilter,
          mine_only: scope === "mine" ? true : undefined,
          assigned_to_me: scope === "assigned" ? true : undefined,
          limit: 100,
        }),
        getApprovalSummary(),
      ]);
      setRows(listRes ?? []);
      setSummary(summaryRes ?? null);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "بارگذاری صف تأییدها ناموفق بود";
      toast.error(message);
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [currentOrg, statusTab, priorityFilter, scope]);

  useEffect(() => {
    load();
  }, [load]);

  const submitDecision = async () => {
    if (!decisionModal) return;
    const { row, decision, comment } = decisionModal;
    setBusyId(row.id);
    try {
      await decideApproval(row.id, {
        decision,
        reviewer_comment: comment.trim() || undefined,
      });
      toast.success(decision === "approved" ? "درخواست تأیید شد" : "درخواست رد شد");
      setDecisionModal(null);
      await load();
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "ثبت تصمیم ناموفق بود";
      toast.error(message);
    } finally {
      setBusyId(null);
    }
  };

  const handleCancel = async (row: ApprovalRequestWithNames) => {
    setBusyId(row.id);
    try {
      await cancelApproval(row.id, { reason: "لغو توسط کاربر از صف تأییدها" });
      toast.success("درخواست لغو شد");
      await load();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "لغو درخواست ناموفق بود";
      toast.error(message);
    } finally {
      setBusyId(null);
    }
  };

  const handleSweep = async () => {
    setSweeping(true);
    try {
      const res = await expireStaleApprovals();
      const count = res?.expired ?? 0;
      toast.success(
        count > 0
          ? `${formatNumberFa(count)} درخواست منقضی بسته شد`
          : "درخواست منقضی‌شده‌ای نبود"
      );
      await load();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "پاک‌سازی صف ناموفق بود";
      toast.error(message);
    } finally {
      setSweeping(false);
    }
  };

  const kpis = useMemo(
    () => [
      {
        label: "در انتظار بررسی",
        value: summary?.pending ?? 0,
        icon: Clock,
        tone: "text-amber-400",
      },
      {
        label: "فوری",
        value: summary?.pending_urgent ?? 0,
        icon: ShieldAlert,
        tone: "text-rose-400",
      },
      {
        label: "پرخطر",
        value: summary?.pending_high_risk ?? 0,
        icon: AlertTriangle,
        tone: "text-orange-400",
      },
      {
        label: "در انتظار اجرا",
        value: summary?.approved_awaiting_execution ?? 0,
        icon: CheckCircle2,
        tone: "text-emerald-400",
      },
      {
        label: "نزدیک به انقضا",
        value: summary?.expiring_soon ?? 0,
        icon: Clock,
        tone: "text-sky-400",
      },
    ],
    [summary]
  );

  if (!currentOrg) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-8 text-center text-sm text-slate-400">
        برای دیدن صف تأییدها ابتدا یک سازمان انتخاب کنید.
      </div>
    );
  }

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold text-slate-100">
            <ShieldCheck className="h-5 w-5 text-emerald-400" />
            صف تأییدها
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            اقدامات پرخطر پیش از اجرا اینجا بررسی و تأیید می‌شوند.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {canSweep && (
            <button
              onClick={handleSweep}
              disabled={sweeping}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 text-sm text-slate-300 transition hover:bg-slate-800 disabled:opacity-50"
            >
              <Clock className={`h-4 w-4 ${sweeping ? "animate-spin" : ""}`} />
              بستن منقضی‌شده‌ها
            </button>
          )}
          <button
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 text-sm text-slate-300 transition hover:bg-slate-800 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            به‌روزرسانی
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {kpis.map((kpi) => (
          <div
            key={kpi.label}
            className="rounded-xl border border-slate-800 bg-slate-900/40 p-4"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">{kpi.label}</span>
              <kpi.icon className={`h-4 w-4 ${kpi.tone}`} />
            </div>
            <div className="mt-2 text-2xl font-bold text-slate-100">
              {formatNumberFa(kpi.value)}
            </div>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-800 bg-slate-900/40 p-3">
        <div className="flex flex-wrap items-center gap-1">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setStatusTab(tab.id)}
              className={`rounded-lg px-3 py-1.5 text-sm transition ${
                statusTab === tab.id
                  ? "bg-emerald-500/15 text-emerald-300"
                  : "text-slate-400 hover:bg-slate-800/60"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="mr-auto flex flex-wrap items-center gap-2">
          <Filter className="h-4 w-4 text-slate-500" />
          <StyledSelect
            value={priorityFilter}
            onChange={setPriorityFilter}
            options={PRIORITY_FILTERS.map((f) => ({ value: f.id, label: f.label }))}
            className="w-44"
          />
          <StyledSelect
            value={scope}
            onChange={(v) => setScope(v as "all" | "mine" | "assigned")}
            options={SCOPE_FILTERS.map((f) => ({ value: f.id, label: f.label }))}
            className="w-40"
          />
        </div>
      </div>

      {loading ? (
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-10 text-center text-sm text-slate-400">
          در حال بارگذاری…
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-10 text-center">
          <ShieldCheck className="mx-auto h-8 w-8 text-slate-600" />
          <p className="mt-3 text-sm text-slate-400">
            درخواستی با این فیلترها وجود ندارد.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {rows.map((row) => {
            const isMine = !!user && row.requester_id === user.id;
            const isPending = row.status === "pending";
            // Self-approval is refused by the backend, so the buttons are not
            // shown at all rather than shown and then 403'ing.
            const showDecide = isPending && canDecide && !isMine;
            const showCancel = isPending && (isMine || myRank >= ROLE_RANK.admin);
            const expanded = expandedId === row.id;
            // Maps action_type straight to the Persian category name, so no
            // second lookup through a category-label table is needed.
            const category = APPROVAL_ACTION_CATEGORIES_FA[row.action_type];

            return (
              <div
                key={row.id}
                className="rounded-xl border border-slate-800 bg-slate-900/40 p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      {statusBadge(row.status)}
                      {priorityBadge(row.priority)}
                      {riskBadge(row.risk_level)}
                      {isPendingExpiringSoon(row) && (
                        <span className="inline-flex items-center gap-1 rounded-full border border-sky-500/20 bg-sky-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-sky-400">
                          <Clock className="h-3.5 w-3.5" />
                          {formatExpiryFa(row.expires_at) ?? "نزدیک به انقضا"}
                        </span>
                      )}
                    </div>
                    <h3 className="mt-2 truncate font-semibold text-slate-100">
                      {row.title}
                    </h3>
                    <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
                      <span className="inline-flex items-center gap-1">
                        <FileText className="h-3.5 w-3.5" />
                        {labelFa(APPROVAL_ACTION_LABELS_FA, row.action_type)}
                        {category ? ` · ${category}` : ""}
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <User className="h-3.5 w-3.5" />
                        {row.requester_name || row.requester_email || "—"}
                      </span>
                      {row.website_name && (
                        <span className="inline-flex items-center gap-1">
                          <Globe className="h-3.5 w-3.5" />
                          {row.website_name}
                        </span>
                      )}
                      <span className="inline-flex items-center gap-1">
                        <Clock className="h-3.5 w-3.5" />
                        {formatDateTimeFa(row.created_at)}
                      </span>
                      {row.affected_items_count > 1 && (
                        <span>
                          {formatNumberFa(row.affected_items_count)} مورد تحت تأثیر
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex shrink-0 items-center gap-2">
                    <button
                      onClick={() => setExpandedId(expanded ? null : row.id)}
                      className="inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800/60 px-2.5 py-1.5 text-xs text-slate-300 transition hover:bg-slate-800"
                    >
                      <Eye className="h-3.5 w-3.5" />
                      {expanded ? "بستن" : "جزئیات"}
                    </button>
                    {showDecide && (
                      <>
                        <button
                          onClick={() =>
                            setDecisionModal({
                              row,
                              decision: "approved",
                              comment: "",
                            })
                          }
                          disabled={busyId === row.id}
                          className="inline-flex items-center gap-1 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1.5 text-xs font-semibold text-emerald-300 transition hover:bg-emerald-500/20 disabled:opacity-50"
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          تأیید
                        </button>
                        <button
                          onClick={() =>
                            setDecisionModal({
                              row,
                              decision: "rejected",
                              comment: "",
                            })
                          }
                          disabled={busyId === row.id}
                          className="inline-flex items-center gap-1 rounded-lg border border-rose-500/30 bg-rose-500/10 px-2.5 py-1.5 text-xs font-semibold text-rose-300 transition hover:bg-rose-500/20 disabled:opacity-50"
                        >
                          <X className="h-3.5 w-3.5" />
                          رد
                        </button>
                      </>
                    )}
                    {showCancel && (
                      <button
                        onClick={() => handleCancel(row)}
                        disabled={busyId === row.id}
                        className="rounded-lg border border-slate-700 bg-slate-800/60 px-2.5 py-1.5 text-xs text-slate-400 transition hover:bg-slate-800 disabled:opacity-50"
                      >
                        لغو
                      </button>
                    )}
                  </div>
                </div>

                {expanded && (
                  <div className="mt-4 space-y-3 border-t border-slate-800 pt-3 text-sm">
                    {row.description && (
                      <p className="whitespace-pre-wrap text-slate-300">
                        {row.description}
                      </p>
                    )}
                    <div className="grid gap-2 text-xs text-slate-400 md:grid-cols-2">
                      <div>
                        بازبین تعیین‌شده:{" "}
                        <span className="text-slate-300">
                          {row.reviewer_name || "تعیین نشده (باز برای همه بازبین‌ها)"}
                        </span>
                      </div>
                      <div>
                        مهلت:{" "}
                        <span className="text-slate-300">
                          {row.expires_at ? formatDateTimeFa(row.expires_at) : "بدون مهلت"}
                        </span>
                      </div>
                      {isApprovalTerminal(row.status) && (
                        <>
                          <div>
                            تصمیم‌گیرنده:{" "}
                            <span className="text-slate-300">
                              {row.decided_by_name || "—"}
                            </span>
                          </div>
                          <div>
                            زمان تصمیم:{" "}
                            <span className="text-slate-300">
                              {formatDateTimeFa(row.decided_at)}
                            </span>
                          </div>
                        </>
                      )}
                      {row.executed_at && (
                        <div>
                          زمان اجرا:{" "}
                          <span className="text-slate-300">
                            {formatDateTimeFa(row.executed_at)}
                          </span>
                        </div>
                      )}
                    </div>
                    {row.reviewer_comment && (
                      <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3 text-xs text-slate-300">
                        <span className="text-slate-500">یادداشت بازبین: </span>
                        {row.reviewer_comment}
                      </div>
                    )}
                    {row.execution_error && (
                      <div className="rounded-lg border border-rose-500/20 bg-rose-500/5 p-3 text-xs text-rose-300">
                        <span className="text-rose-400">خطای اجرا: </span>
                        {row.execution_error}
                      </div>
                    )}
                    {Object.keys(row.payload || {}).length > 0 && (
                      <details className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
                        <summary className="cursor-pointer text-xs text-slate-400">
                          داده‌های درخواست
                        </summary>
                        <pre
                          dir="ltr"
                          className="mt-2 max-h-56 overflow-auto text-[11px] leading-relaxed text-slate-400"
                        >
                          {JSON.stringify(row.payload, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {decisionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4">
          <div className="w-full max-w-lg rounded-xl border border-slate-800 bg-slate-900 p-5">
            <div className="flex items-start justify-between gap-3">
              <h2 className="font-semibold text-slate-100">
                {decisionModal.decision === "approved"
                  ? "تأیید درخواست"
                  : "رد درخواست"}
              </h2>
              <button
                onClick={() => setDecisionModal(null)}
                className="rounded-lg p-1 text-slate-500 transition hover:bg-slate-800 hover:text-slate-300"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="mt-2 text-sm text-slate-400">{decisionModal.row.title}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {riskBadge(decisionModal.row.risk_level)}
              {priorityBadge(decisionModal.row.priority)}
            </div>
            {decisionModal.row.affected_items_count > 1 && (
              <p className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-amber-300">
                این اقدام روی{" "}
                {formatNumberFa(decisionModal.row.affected_items_count)} مورد اثر
                می‌گذارد.
              </p>
            )}
            <label className="mt-4 block text-xs text-slate-400">
              یادداشت بازبین {decisionModal.decision === "rejected" ? "(توصیه می‌شود)" : "(اختیاری)"}
            </label>
            <textarea
              value={decisionModal.comment}
              onChange={(e) =>
                setDecisionModal({ ...decisionModal, comment: e.target.value })
              }
              rows={3}
              maxLength={2000}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-800/60 p-2 text-sm text-slate-200 outline-none focus:border-slate-600"
              placeholder="دلیل تصمیم را برای سابقه ثبت کنید…"
            />
            <div className="mt-4 flex items-center justify-end gap-2">
              <button
                onClick={() => setDecisionModal(null)}
                className="rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 text-sm text-slate-300 transition hover:bg-slate-800"
              >
                انصراف
              </button>
              <button
                onClick={submitDecision}
                disabled={busyId === decisionModal.row.id}
                className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition disabled:opacity-50 ${
                  decisionModal.decision === "approved"
                    ? "bg-emerald-500/90 text-slate-950 hover:bg-emerald-500"
                    : "bg-rose-500/90 text-slate-950 hover:bg-rose-500"
                }`}
              >
                {decisionModal.decision === "approved" ? (
                  <CheckCircle2 className="h-4 w-4" />
                ) : (
                  <X className="h-4 w-4" />
                )}
                {decisionModal.decision === "approved" ? "تأیید نهایی" : "رد نهایی"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
