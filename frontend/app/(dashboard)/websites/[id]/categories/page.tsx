"use client";

/**
 * Site-structure (categories) workspace.
 *
 * One website, one materialised tree. The backend returns children already
 * nested and sorted (sort_order, then name); we flatten to rows carrying depth
 * and indent by depth. Add / rename / delete / move are inline — no modal
 * component exists in this project, so an "add child" row expands under its
 * parent and the edit form replaces a row in place, matching how the rest of
 * the app handles forms.
 *
 * Every hook runs before any conditional return. A hook placed after an early
 * return reorders the hook list between renders and React rejects it — that has
 * broken a page in this codebase, so the "no website" guard lives inside JSX.
 */

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ApiError } from "@/lib/api-client";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import {
  getCategoryTree,
  getCategorySummary,
  createCategory,
  updateCategory,
  moveCategory,
  deleteCategory,
  importWordpressCategories,
  flattenTree,
  CATEGORY_SOURCE_LABELS_FA,
  type CategoryNode,
  type CategorySummary,
} from "@/lib/categories";
import { formatNumberFa, labelFa } from "@/lib/insights";
import {
  AlertCircle,
  ChevronLeft,
  CornerDownLeft,
  Download,
  FolderTree,
  Layers,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";
import toast from "react-hot-toast";

export default function WebsiteCategoriesPage() {
  const params = useParams();
  const websiteId = params.id as string;

  const [tree, setTree] = useState<CategoryNode[]>([]);
  const [summary, setSummary] = useState<CategorySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<CategoryNode | null>(null);

  // Inline form state. `addUnder` is a parent id ("" = new root); `editingId`
  // is the row being renamed. Only one of the two is active at a time.
  const [addUnder, setAddUnder] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [nameDraft, setNameDraft] = useState("");
  const [descDraft, setDescDraft] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (!websiteId) return;
    setLoading(true);
    setError(null);
    try {
      const [t, s] = await Promise.all([
        getCategoryTree(websiteId),
        getCategorySummary(websiteId),
      ]);
      setTree(Array.isArray(t) ? t : []);
      setSummary(s);
    } catch (err: any) {
      setError(
        err instanceof ApiError ? err.message : "خطا در دریافت ساختار دسته‌ها"
      );
      setTree([]);
    } finally {
      setLoading(false);
    }
  }, [websiteId]);

  useEffect(() => {
    load();
  }, [load]);

  const rows = useMemo(() => flattenTree(tree), [tree]);

  const resetForm = () => {
    setAddUnder(null);
    setEditingId(null);
    setNameDraft("");
    setDescDraft("");
  };

  const openAdd = (parentId: string | null) => {
    resetForm();
    setAddUnder(parentId ?? "");
  };

  const openEdit = (node: CategoryNode) => {
    resetForm();
    setEditingId(node.id);
    setNameDraft(node.name);
    setDescDraft(node.description ?? "");
  };

  const submitCreate = async () => {
    const name = nameDraft.trim();
    if (!name) {
      toast.error("نام دسته را وارد کنید");
      return;
    }
    setSaving(true);
    try {
      await createCategory({
        website_id: websiteId,
        parent_id: addUnder ? addUnder : null,
        name,
        description: descDraft.trim() || null,
      });
      toast.success("دسته جدید ساخته شد");
      resetForm();
      await load();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در ساخت دسته"
      );
    } finally {
      setSaving(false);
    }
  };

  const submitEdit = async () => {
    const name = nameDraft.trim();
    if (!name || !editingId) {
      toast.error("نام دسته را وارد کنید");
      return;
    }
    setSaving(true);
    try {
      await updateCategory(editingId, {
        name,
        description: descDraft.trim() || null,
      });
      toast.success("دسته ویرایش شد");
      resetForm();
      await load();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در ویرایش دسته"
      );
    } finally {
      setSaving(false);
    }
  };

  const handleMoveToRoot = async (node: CategoryNode) => {
    if (node.parent_id === null) return;
    setBusyId(node.id);
    try {
      await moveCategory(node.id, null);
      toast.success("دسته به ریشه منتقل شد");
      await load();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در انتقال دسته"
      );
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async () => {
    const node = pendingDelete;
    if (!node) return;
    setBusyId(node.id);
    try {
      const res = await deleteCategory(node.id);
      toast.success(`${formatNumberFa(res.deleted)} دسته حذف شد`);
      setPendingDelete(null);
      await load();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در حذف دسته"
      );
    } finally {
      setBusyId(null);
    }
  };

  const handleImport = async () => {
    setImporting(true);
    setError(null);
    try {
      const res = await importWordpressCategories(websiteId);
      toast.success(
        `درون‌ریزی وردپرس: ${formatNumberFa(res.created)} جدید، ${formatNumberFa(
          res.updated
        )} بروزرسانی، ${formatNumberFa(res.skipped)} رد‌شده`
      );
      await load();
    } catch (err: any) {
      const message =
        err instanceof ApiError
          ? err.message
          : "خطا در درون‌ریزی دسته‌های وردپرس";
      setError(message);
      toast.error(message);
    } finally {
      setImporting(false);
    }
  };

  const isEmpty = !loading && !error && rows.length === 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">
            ساختار سایت و دسته‌بندی‌ها
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            درخت دسته‌ها و زیردسته‌های این سایت؛ مبنای سازمان‌دهی محتوا و پیلارها
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => openAdd(null)}
            disabled={!websiteId}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-emerald-500/20 transition hover:from-emerald-600 hover:to-teal-700 disabled:opacity-50"
          >
            <Plus className="h-4 w-4" />
            دسته ریشه جدید
          </button>
          <button
            onClick={handleImport}
            disabled={importing || !websiteId}
            className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-white/10 disabled:opacity-50"
          >
            {importing ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            {importing ? "در حال درون‌ریزی..." : "درون‌ریزی از وردپرس"}
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "کل دسته‌ها", value: summary?.total, icon: FolderTree },
          { label: "دسته‌های ریشه", value: summary?.roots, icon: Layers },
          { label: "بیشترین عمق", value: summary?.max_depth, icon: ChevronLeft },
          {
            label: "درون‌ریزی وردپرس",
            value: summary?.by_source?.wordpress ?? 0,
            icon: Download,
          },
        ].map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.label}
              className="rounded-2xl border border-white/10 bg-card/80 p-5 backdrop-blur-md"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">
                  {card.label}
                </span>
                <Icon className="h-4 w-4 text-emerald-400" />
              </div>
              <p className="mt-2 text-2xl font-bold text-white">
                {formatNumberFa(card.value)}
              </p>
            </div>
          );
        })}
      </div>

      {/* New root category inline form */}
      {addUnder === "" && (
        <CategoryForm
          title="افزودن دسته ریشه"
          name={nameDraft}
          desc={descDraft}
          saving={saving}
          onName={setNameDraft}
          onDesc={setDescDraft}
          onSubmit={submitCreate}
          onCancel={resetForm}
        />
      )}

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs text-red-300">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Tree */}
      <div className="rounded-2xl border border-white/10 bg-card/60 p-2 backdrop-blur-md">
        {loading ? (
          <div className="space-y-2 p-3">
            {[0, 1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="h-12 animate-pulse rounded-xl bg-white/5"
                style={{ marginRight: `${(i % 3) * 24}px` }}
              />
            ))}
          </div>
        ) : isEmpty ? (
          <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-white/15 p-12 text-center">
            <FolderTree className="h-10 w-10 text-muted-foreground/50" />
            <p className="text-sm font-medium text-white">
              هنوز دسته‌ای ساخته نشده است
            </p>
            <p className="max-w-md text-xs text-muted-foreground">
              یک دسته ریشه بسازید یا دسته‌های سایت وردپرسی متصل را درون‌ریزی کنید.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-white/5">
            {rows.map((node) =>
              editingId === node.id ? (
                <div key={node.id} className="p-2">
                  <CategoryForm
                    title="ویرایش دسته"
                    name={nameDraft}
                    desc={descDraft}
                    saving={saving}
                    onName={setNameDraft}
                    onDesc={setDescDraft}
                    onSubmit={submitEdit}
                    onCancel={resetForm}
                  />
                </div>
              ) : (
                <div key={node.id}>
                  <div
                    className="group flex items-center gap-3 rounded-xl px-3 py-2.5 transition hover:bg-white/5"
                    style={{ paddingRight: `${12 + node.depth * 22}px` }}
                  >
                    {node.depth > 0 && (
                      <CornerDownLeft className="h-3.5 w-3.5 shrink-0 -scale-x-100 text-muted-foreground/40" />
                    )}
                    <FolderTree className="h-4 w-4 shrink-0 text-emerald-400/80" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-sm font-medium text-white">
                          {node.name}
                        </span>
                        <span
                          className="shrink-0 rounded-md bg-white/5 px-1.5 py-0.5 text-[10px] text-muted-foreground"
                          dir="ltr"
                        >
                          /{node.slug}
                        </span>
                        {node.source === "wordpress" && (
                          <span className="shrink-0 rounded-md bg-sky-500/15 px-1.5 py-0.5 text-[10px] text-sky-300">
                            {labelFa(CATEGORY_SOURCE_LABELS_FA, node.source)}
                          </span>
                        )}
                      </div>
                      {node.description && (
                        <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
                          {node.description}
                        </p>
                      )}
                    </div>
                    <span className="shrink-0 rounded-md bg-white/5 px-2 py-0.5 text-[10px] text-muted-foreground">
                      {formatNumberFa(node.content_count)} محتوا
                    </span>
                    <div className="flex shrink-0 items-center gap-1 opacity-0 transition group-hover:opacity-100">
                      <button
                        onClick={() => openAdd(node.id)}
                        disabled={busyId === node.id}
                        title="افزودن زیردسته"
                        className="rounded-lg p-1.5 text-muted-foreground transition hover:bg-emerald-500/15 hover:text-emerald-400 disabled:opacity-50"
                      >
                        <Plus className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => openEdit(node)}
                        disabled={busyId === node.id}
                        title="ویرایش"
                        className="rounded-lg p-1.5 text-muted-foreground transition hover:bg-white/10 hover:text-white disabled:opacity-50"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      {node.parent_id !== null && (
                        <button
                          onClick={() => handleMoveToRoot(node)}
                          disabled={busyId === node.id}
                          title="انتقال به ریشه"
                          className="rounded-lg p-1.5 text-muted-foreground transition hover:bg-white/10 hover:text-white disabled:opacity-50"
                        >
                          <Layers className="h-4 w-4" />
                        </button>
                      )}
                      <button
                        onClick={() => setPendingDelete(node)}
                        disabled={busyId === node.id}
                        title="حذف"
                        className="rounded-lg p-1.5 text-muted-foreground transition hover:bg-red-500/15 hover:text-red-400 disabled:opacity-50"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>

                  {/* Add-child inline form under this node */}
                  {addUnder === node.id && (
                    <div
                      className="p-2"
                      style={{ paddingRight: `${12 + (node.depth + 1) * 22}px` }}
                    >
                      <CategoryForm
                        title={`افزودن زیردسته زیرِ «${node.name}»`}
                        name={nameDraft}
                        desc={descDraft}
                        saving={saving}
                        onName={setNameDraft}
                        onDesc={setDescDraft}
                        onSubmit={submitCreate}
                        onCancel={resetForm}
                      />
                    </div>
                  )}
                </div>
              )
            )}
          </div>
        )}
      </div>

      <ConfirmDialog
        isOpen={!!pendingDelete}
        title="حذف دسته"
        description={
          pendingDelete
            ? (pendingDelete.children?.length ?? 0) > 0
              ? `«${pendingDelete.name}» و همه زیردسته‌هایش حذف شوند؟ این عمل بازگشت‌پذیر نیست.`
              : `«${pendingDelete.name}» حذف شود؟`
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

// -------------------------------------------------------------- inline form

function CategoryForm({
  title,
  name,
  desc,
  saving,
  onName,
  onDesc,
  onSubmit,
  onCancel,
}: {
  title: string;
  name: string;
  desc: string;
  saving: boolean;
  onName: (v: string) => void;
  onDesc: (v: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-semibold text-emerald-300">{title}</span>
        <button
          onClick={onCancel}
          className="rounded-lg p-1 text-muted-foreground transition hover:bg-white/10 hover:text-white"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="flex flex-col gap-3">
        <input
          value={name}
          onChange={(e) => onName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") onSubmit();
          }}
          autoFocus
          placeholder="نام دسته"
          className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none placeholder:text-muted-foreground/60 focus:border-emerald-500/50"
        />
        <input
          value={desc}
          onChange={(e) => onDesc(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") onSubmit();
          }}
          placeholder="توضیح کوتاه (اختیاری)"
          className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none placeholder:text-muted-foreground/60 focus:border-emerald-500/50"
        />
        <div className="flex items-center justify-end gap-2">
          <button
            onClick={onCancel}
            className="rounded-lg px-3 py-1.5 text-xs text-muted-foreground transition hover:text-white"
          >
            انصراف
          </button>
          <button
            onClick={onSubmit}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-4 py-1.5 text-xs font-semibold text-white transition hover:bg-emerald-600 disabled:opacity-50"
          >
            {saving ? (
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <CornerDownLeft className="h-3.5 w-3.5" />
            )}
            ذخیره
          </button>
        </div>
      </div>
    </div>
  );
}
