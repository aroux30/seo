"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/context/auth-context";
import { api, ApiError } from "@/lib/api-client";
import { FolderKanban, Plus, Sparkles, Globe, Pencil, Trash2, X, AlertTriangle } from "lucide-react";
import toast from "react-hot-toast";

export default function ProjectsPage() {
  const { currentOrg } = useAuth();
  const [projects, setProjects] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  // Edit & Delete Modals
  const [editProjectModal, setEditProjectModal] = useState<{
    open: boolean;
    project: any;
    name: string;
    description: string;
    loading: boolean;
  }>({
    open: false,
    project: null,
    name: "",
    description: "",
    loading: false,
  });

  const [deleteProjectModal, setDeleteProjectModal] = useState<{
    open: boolean;
    project: any;
    loading: boolean;
  }>({
    open: false,
    project: null,
    loading: false,
  });

  useEffect(() => {
    if (currentOrg) {
      loadProjects();
    }
  }, [currentOrg]);

  const loadProjects = async () => {
    setLoading(true);
    try {
      const data = await api.get("/projects");
      setProjects(data || []);
    } catch {
      setProjects([]);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !currentOrg) return;
    setCreating(true);
    setError(null);

    try {
      await api.post("/projects", {
        name: name.trim(),
        description: description.trim() || undefined,
      });
      setName("");
      setDescription("");
      setModalOpen(false);
      await loadProjects();
      toast.success("پروژه جدید با موفقیت ایجاد شد");
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("خطا در ایجاد پروژه");
      }
    } finally {
      setCreating(false);
    }
  };

  const submitEditProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editProjectModal.project || !editProjectModal.name.trim()) return;
    setEditProjectModal((prev) => ({ ...prev, loading: true }));
    try {
      await api.put(`/projects/${editProjectModal.project.id}`, {
        name: editProjectModal.name.trim(),
        description: editProjectModal.description.trim() || undefined,
      });
      await loadProjects();
      toast.success("پروژه با موفقیت ویرایش شد");
      setEditProjectModal({ open: false, project: null, name: "", description: "", loading: false });
    } catch (err: any) {
      toast.error(err.message || "خطا در ویرایش پروژه");
      setEditProjectModal((prev) => ({ ...prev, loading: false }));
    }
  };

  const submitDeleteProject = async () => {
    if (!deleteProjectModal.project) return;
    setDeleteProjectModal((prev) => ({ ...prev, loading: true }));
    try {
      await api.delete(`/projects/${deleteProjectModal.project.id}`);
      await loadProjects();
      toast.success("پروژه با موفقیت حذف شد");
      setDeleteProjectModal({ open: false, project: null, loading: false });
    } catch (err: any) {
      toast.error(err.message || "خطا در حذف پروژه");
      setDeleteProjectModal((prev) => ({ ...prev, loading: false }));
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            پروژه‌های سازمان «{currentOrg?.name || "---"}»
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            دسته‌بندی و گروه بندی وب‌سایت‌های مرتبط زیر مجموعه پروژه‌های مجزا
          </p>
        </div>

        <button
          onClick={() => setModalOpen(true)}
          className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-xs font-semibold text-primary-foreground shadow-lg shadow-primary/25 transition hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          <span>افزودن پروژه جدید</span>
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {loading ? (
        <div className="py-12 text-center text-xs text-muted-foreground">
          در حال بارگذاری پروژه‌ها...
        </div>
      ) : projects.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-white/10 p-12 text-center">
          <FolderKanban className="mx-auto h-12 w-12 text-muted-foreground/50" />
          <h3 className="mt-3 text-base font-bold text-white">
            هیچ پروژه‌ای در این سازمان وجود ندارد
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            پروژه‌ها به شما کمک می‌کنند وب‌سایت‌ها و کمپین‌های سئو را سازمان‌دهی کنید.
          </p>
          <button
            onClick={() => setModalOpen(true)}
            className="mt-4 inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground shadow-md shadow-primary/20"
          >
            <Plus className="h-4 w-4" />
            <span>ایجاد اولین پروژه</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <div
              key={p.id}
              className="rounded-2xl border border-white/10 bg-card/60 p-6 shadow-xl backdrop-blur-md transition hover:border-white/20"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/15 text-primary">
                  <FolderKanban className="h-6 w-6" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">{p.name}</h3>
                  <p className="text-xs text-muted-foreground">
                    شناسه: {p.slug}
                  </p>
                </div>
              </div>
              {p.description && (
                <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
                  {p.description}
                </p>
              )}
              <div className="mt-6 flex items-center justify-between border-t border-white/10 pt-4 text-[11px] text-muted-foreground">
                <span>
                  تاریخ ایجاد:{" "}
                  {p.created_at
                    ? new Date(p.created_at).toLocaleDateString("fa-IR")
                    : "---"}
                </span>
                
                <div className="flex items-center gap-2">
                  {(currentOrg?.my_role === "owner" || currentOrg?.my_role === "admin" || currentOrg?.my_role === "seo_manager") && (
                    <button
                      onClick={() =>
                        setEditProjectModal({
                          open: true,
                          project: p,
                          name: p.name,
                          description: p.description || "",
                          loading: false,
                        })
                      }
                      className="rounded bg-blue-500/10 p-1.5 text-blue-400 hover:bg-blue-500/20 transition"
                      title="ویرایش پروژه"
                    >
                      <Pencil className="h-4 w-4" />
                    </button>
                  )}
                  {(currentOrg?.my_role === "owner" || currentOrg?.my_role === "admin") && (
                    <button
                      onClick={() =>
                        setDeleteProjectModal({ open: true, project: p, loading: false })
                      }
                      className="rounded bg-red-500/10 p-1.5 text-red-400 hover:bg-red-500/20 transition"
                      title="حذف پروژه"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal: Create Project */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-white/10 bg-card p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-white">ایجاد پروژه جدید</h3>
              <button
                onClick={() => setModalOpen(false)}
                className="rounded-lg p-1 text-muted-foreground hover:bg-white/10"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  نام پروژه
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="مثال: پروژه وبلاگ‌های فناوری"
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-sm text-white placeholder-muted-foreground focus:border-primary focus:outline-none"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  توضیحات (اختیاری)
                </label>
                <textarea
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="توضیحات کوتاه درباره هدف و دامنه پروژه..."
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-sm text-white placeholder-muted-foreground focus:border-primary focus:outline-none"
                />
              </div>

              <div className="mt-6 flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-muted-foreground hover:bg-white/5"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="rounded-xl bg-primary px-5 py-2 text-xs font-semibold text-primary-foreground shadow-lg shadow-primary/25 hover:bg-primary/90 disabled:opacity-50"
                >
                  {creating ? "در حال ایجاد..." : "ایجاد پروژه"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Edit Project */}
      {editProjectModal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-white/10 bg-card p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-white">ویرایش پروژه</h3>
              <button
                onClick={() =>
                  setEditProjectModal({ open: false, project: null, name: "", description: "", loading: false })
                }
                className="rounded-lg p-1 text-muted-foreground hover:bg-white/10"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={submitEditProject} className="space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  نام پروژه
                </label>
                <input
                  type="text"
                  required
                  value={editProjectModal.name}
                  onChange={(e) =>
                    setEditProjectModal((prev) => ({ ...prev, name: e.target.value }))
                  }
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-sm text-white focus:border-primary focus:outline-none"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  توضیحات
                </label>
                <textarea
                  rows={3}
                  value={editProjectModal.description}
                  onChange={(e) =>
                    setEditProjectModal((prev) => ({ ...prev, description: e.target.value }))
                  }
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-sm text-white focus:border-primary focus:outline-none"
                />
              </div>

              <div className="mt-6 flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() =>
                    setEditProjectModal({ open: false, project: null, name: "", description: "", loading: false })
                  }
                  className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-muted-foreground hover:bg-white/5"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  disabled={editProjectModal.loading}
                  className="rounded-xl bg-primary px-5 py-2 text-xs font-semibold text-primary-foreground shadow-lg shadow-primary/25 hover:bg-primary/90 disabled:opacity-50"
                >
                  {editProjectModal.loading ? "در حال ذخیره..." : "ذخیره تغییرات"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Delete Project Confirm */}
      {deleteProjectModal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-red-500/30 bg-card p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-red-400">
              <AlertTriangle className="h-6 w-6 shrink-0" />
              <h3 className="text-base font-bold text-white">حذف پروژه «{deleteProjectModal.project?.name}»</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              آیا از حذف این پروژه مطمئن هستید؟ با حذف پروژه تمام اطلاعات مربوط به دسته‌بندی و سایت‌های زیرمجموعه متاثر خواهند شد. این عمل غیرقابل بازگشت است.
            </p>
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setDeleteProjectModal({ open: false, project: null, loading: false })}
                className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-muted-foreground hover:bg-white/5"
              >
                انصراف
              </button>
              <button
                type="button"
                onClick={submitDeleteProject}
                disabled={deleteProjectModal.loading}
                className="rounded-xl bg-red-600 px-5 py-2 text-xs font-semibold text-white shadow-lg hover:bg-red-500 disabled:opacity-50"
              >
                {deleteProjectModal.loading ? "در حال حذف..." : "حذف پروژه"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
