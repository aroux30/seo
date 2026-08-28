"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth, Website } from "@/context/auth-context";
import { api, ApiError } from "@/lib/api-client";
import {
  Globe,
  Plus,
  Shield,
  Zap,
  CheckCircle2,
  ExternalLink,
  Sparkles,
  Pencil,
  Trash2,
  X,
  AlertTriangle,
} from "lucide-react";
import toast from "react-hot-toast";

export default function WebsitesPage() {
  const { currentOrg, websites, currentWebsite, setCurrentWebsite, refreshOrgsAndWebsites } =
    useAuth();
  const [projects, setProjects] = useState<any[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [websiteType, setWebsiteType] = useState("blog");
  const [automationMode, setAutomationMode] = useState("ai_assist");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  // Edit & Delete Modals
  const [editSiteModal, setEditSiteModal] = useState<{
    open: boolean;
    site: any;
    name: string;
    domain: string;
    baseUrl: string;
    websiteType: string;
    automationMode: string;
    loading: boolean;
  }>({
    open: false,
    site: null,
    name: "",
    domain: "",
    baseUrl: "",
    websiteType: "blog",
    automationMode: "ai_assist",
    loading: false,
  });

  const [deleteSiteModal, setDeleteSiteModal] = useState<{
    open: boolean;
    site: any;
    loading: boolean;
  }>({
    open: false,
    site: null,
    loading: false,
  });

  useEffect(() => {
    if (currentOrg) {
      loadProjects(currentOrg.id);
    }
  }, [currentOrg]);

  const loadProjects = async (orgId: string) => {
    try {
      const data = await api.get("/projects");
      const list = data || [];
      setProjects(list);
      if (list.length > 0) {
        setSelectedProjectId(list[0].id);
      }
    } catch {
      setProjects([]);
    }
  };

  const handleCreateWebsite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentOrg) return;
    setLoading(true);
    setError(null);

    try {
      let projId = selectedProjectId;
      if (!projId) {
        const defaultProj = await api.post("/projects", {
          name: "پروژه اصلی",
          description: "پروژه پیش‌فرض سازمان",
        });
        projId = defaultProj.id;
      }

      const res = await api.post<Website>("/websites", {
        project_id: projId,
        name,
        domain: domain.replace(/^https?:\/\//, "").replace(/\/.*$/, ""),
        base_url: baseUrl || `https://${domain}`,
        website_type: websiteType,
        automation_mode: automationMode,
      });

      setName("");
      setDomain("");
      setBaseUrl("");
      setModalOpen(false);
      await refreshOrgsAndWebsites();
      if (res && res.id) {
        setCurrentWebsite(res);
      }
      toast.success("وب‌سایت جدید با موفقیت اضافه شد");
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("خطا در افزودن وب‌سایت");
      }
    } finally {
      setLoading(false);
    }
  };

  const submitEditWebsite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editSiteModal.site) return;
    setEditSiteModal((prev) => ({ ...prev, loading: true }));
    try {
      const updated = await api.patch(`/websites/${editSiteModal.site.id}`, {
        name: editSiteModal.name,
        domain: editSiteModal.domain.replace(/^https?:\/\//, "").replace(/\/.*$/, ""),
        base_url: editSiteModal.baseUrl,
        website_type: editSiteModal.websiteType,
        automation_mode: editSiteModal.automationMode,
      });
      await refreshOrgsAndWebsites();
      if (currentWebsite?.id === editSiteModal.site.id) {
        setCurrentWebsite(updated);
      }
      toast.success("اطلاعات وب‌سایت به‌روزرسانی شد");
      setEditSiteModal({
        open: false,
        site: null,
        name: "",
        domain: "",
        baseUrl: "",
        websiteType: "blog",
        automationMode: "ai_assist",
        loading: false,
      });
    } catch (err: any) {
      toast.error(err.message || "خطا در ویرایش وب‌سایت");
      setEditSiteModal((prev) => ({ ...prev, loading: false }));
    }
  };

  const submitDeleteWebsite = async () => {
    if (!deleteSiteModal.site) return;
    setDeleteSiteModal((prev) => ({ ...prev, loading: true }));
    try {
      await api.delete(`/websites/${deleteSiteModal.site.id}`);
      await refreshOrgsAndWebsites();
      if (currentWebsite?.id === deleteSiteModal.site.id) {
        const remaining = websites.filter((w) => w.id !== deleteSiteModal.site.id);
        setCurrentWebsite(remaining.length > 0 ? remaining[0] : null);
      }
      toast.success("وب‌سایت با موفقیت حذف شد");
      setDeleteSiteModal({ open: false, site: null, loading: false });
    } catch (err: any) {
      toast.error(err.message || "خطا در حذف وب‌سایت");
      setDeleteSiteModal((prev) => ({ ...prev, loading: false }));
    }
  };

  if (!currentOrg) {
    return (
      <div className="flex h-96 flex-col items-center justify-center rounded-2xl border border-white/10 bg-card/40 p-8 text-center">
        <Globe className="h-12 w-12 text-muted-foreground/50" />
        <h3 className="mt-4 text-base font-bold text-white">
          هیچ سازمانی انتخاب نشده است
        </h3>
        <p className="mt-1 text-xs text-muted-foreground">
          برای افزودن وب‌سایت، ابتدا از منوی کناری یک سازمان را انتخاب کنید یا سازمان جدید بسازید.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            مدیریت وب‌سایت‌های سازمان «{currentOrg.name}»
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            اتصال وب‌سایت‌ها، تنظیم دامنه و تعیین سطح اتوماسیون هوش مصنوعی
          </p>
        </div>

        <button
          onClick={() => setModalOpen(true)}
          className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-xs font-semibold text-primary-foreground shadow-lg shadow-primary/25 transition hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          <span>افزودن وب‌سایت جدید</span>
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Website Cards Grid */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        {websites.map((site) => {
          const isCurrent = currentWebsite?.id === site.id;
          return (
            <div
              key={site.id}
              onClick={() => setCurrentWebsite(site)}
              className={`group relative flex cursor-pointer flex-col justify-between rounded-2xl border p-6 transition ${
                isCurrent
                  ? "border-emerald-500/50 bg-emerald-500/5 shadow-xl shadow-emerald-500/5"
                  : "border-white/10 bg-card/60 hover:border-white/20 hover:bg-card"
              }`}
            >
              <div>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400">
                      <Globe className="h-6 w-6" />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-white">
                        {site.name}
                      </h3>
                      <p className="text-xs font-medium text-emerald-400" dir="ltr">
                        {site.domain}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={`rounded-full px-2.5 py-1 text-[10px] font-semibold ${
                        isCurrent
                          ? "bg-emerald-500/20 text-emerald-400"
                          : "bg-white/5 text-muted-foreground"
                      }`}
                    >
                      {isCurrent ? "وب‌سایت فعال" : "انتخاب"}
                    </span>
                    {(currentOrg?.my_role === "owner" || currentOrg?.my_role === "admin" || currentOrg?.my_role === "seo_manager") && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditSiteModal({
                            open: true,
                            site,
                            name: site.name,
                            domain: site.domain,
                            baseUrl: site.base_url,
                            websiteType: site.website_type || "blog",
                            automationMode: site.automation_mode || "ai_assist",
                            loading: false,
                          });
                        }}
                        className="rounded-lg bg-blue-500/10 p-1.5 text-blue-400 hover:bg-blue-500/20 transition"
                        title="ویرایش سریع"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                    )}
                    {(currentOrg?.my_role === "owner" || currentOrg?.my_role === "admin") && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeleteSiteModal({ open: true, site, loading: false });
                        }}
                        className="rounded-lg bg-red-500/10 p-1.5 text-red-400 hover:bg-red-500/20 transition"
                        title="حذف وب‌سایت"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                <div className="mt-6 space-y-2 border-t border-white/10 pt-4 text-xs text-muted-foreground">
                  <div className="flex justify-between">
                    <span>نوع وب‌سایت:</span>
                    <span className="font-medium text-white">
                      {site.website_type}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>زبان / کشور:</span>
                    <span className="font-medium text-white">
                      {site.language || "fa"} - IR
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>حالت اتوماسیون:</span>
                    <span className="rounded-md bg-purple-500/15 px-2 py-0.5 font-semibold text-purple-400">
                      {site.automation_mode === "ai_assist"
                        ? "دستیار هوشمند (AI Assist)"
                        : site.automation_mode === "autopilot"
                        ? "خودکار (Autopilot)"
                        : "دستی (Manual)"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="mt-6 flex items-center justify-between border-t border-white/5 pt-4 text-xs">
                <Link
                  href={`/websites/${site.id}/analytics`}
                  onClick={(e) => e.stopPropagation()}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-primary/20 px-3 py-1.5 font-semibold text-primary transition hover:bg-primary hover:text-primary-foreground"
                >
                  <span>مدیریت سئو و اتصالات</span>
                </Link>
                <a
                  href={site.base_url}
                  target="_blank"
                  rel="noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="flex items-center gap-1 text-muted-foreground hover:text-white"
                >
                  <span>بازدید سایت</span>
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </div>
            </div>
          );
        })}

        {/* Add New Box Card */}
        <button
          onClick={() => setModalOpen(true)}
          className="flex h-full min-h-[260px] flex-col items-center justify-center rounded-2xl border border-dashed border-white/15 bg-card/30 p-6 text-center transition hover:border-primary hover:bg-card/50"
        >
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Plus className="h-6 w-6" />
          </div>
          <h3 className="text-sm font-bold text-white">ثبت وب‌سایت جدید</h3>
          <p className="mt-1 max-w-[200px] text-xs text-muted-foreground">
            اتصال سایت برای رصد سرچ کنسول، وردپرس و اجرای عملیات سئو
          </p>
        </button>
      </div>

      {/* Add Website Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-white/10 bg-card p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-white">
                افزودن وب‌سایت جدید
              </h3>
              <button
                onClick={() => setModalOpen(false)}
                className="rounded-lg p-1 text-muted-foreground hover:bg-white/10"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleCreateWebsite} className="space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  نام وب‌سایت
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="مثال: مجله فناوری دیجی‌سئو"
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-sm text-white placeholder-muted-foreground focus:border-primary focus:outline-none"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  دامنه سایت (Domain)
                </label>
                <input
                  type="text"
                  required
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  placeholder="example.com"
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-sm text-white placeholder-muted-foreground focus:border-primary focus:outline-none"
                  dir="ltr"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  آدرس کامل سایت (Base URL)
                </label>
                <input
                  type="url"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="https://example.com"
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-sm text-white placeholder-muted-foreground focus:border-primary focus:outline-none"
                  dir="ltr"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    نوع سایت
                  </label>
                  <select
                    value={websiteType}
                    onChange={(e) => setWebsiteType(e.target.value)}
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2.5 text-xs text-white focus:border-primary focus:outline-none"
                  >
                    <option value="blog">وبلاگ / مجله (Blog)</option>
                    <option value="ecommerce">فروشگاهی (E-commerce)</option>
                    <option value="corporate">شرکتی (Corporate)</option>
                    <option value="saas">سرویس آنلاین (SaaS)</option>
                  </select>
                </div>

                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    حالت اتوماسیون
                  </label>
                  <select
                    value={automationMode}
                    onChange={(e) => setAutomationMode(e.target.value)}
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2.5 text-xs text-white focus:border-primary focus:outline-none"
                  >
                    <option value="ai_assist">دستیار هوشمند (AI Assist)</option>
                    <option value="manual">دستی (Manual)</option>
                    <option value="autopilot">خودکار (Autopilot)</option>
                  </select>
                </div>
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
                  disabled={loading}
                  className="rounded-xl bg-primary px-5 py-2 text-xs font-semibold text-primary-foreground shadow-lg shadow-primary/25 hover:bg-primary/90 disabled:opacity-50"
                >
                  {loading ? "در حال ثبت..." : "افزودن وب‌سایت"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Edit Website */}
      {editSiteModal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-white/10 bg-card p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-white">ویرایش مشخصات وب‌سایت</h3>
              <button
                onClick={() =>
                  setEditSiteModal({
                    open: false,
                    site: null,
                    name: "",
                    domain: "",
                    baseUrl: "",
                    websiteType: "blog",
                    automationMode: "ai_assist",
                    loading: false,
                  })
                }
                className="rounded-lg p-1 text-muted-foreground hover:bg-white/10"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={submitEditWebsite} className="space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  نام وب‌سایت
                </label>
                <input
                  type="text"
                  required
                  value={editSiteModal.name}
                  onChange={(e) =>
                    setEditSiteModal((prev) => ({ ...prev, name: e.target.value }))
                  }
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-sm text-white focus:border-primary focus:outline-none"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  دامنه (Domain)
                </label>
                <input
                  type="text"
                  required
                  value={editSiteModal.domain}
                  onChange={(e) =>
                    setEditSiteModal((prev) => ({ ...prev, domain: e.target.value }))
                  }
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-sm text-white focus:border-primary focus:outline-none"
                  dir="ltr"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  آدرس کامل سایت (Base URL)
                </label>
                <input
                  type="url"
                  required
                  value={editSiteModal.baseUrl}
                  onChange={(e) =>
                    setEditSiteModal((prev) => ({ ...prev, baseUrl: e.target.value }))
                  }
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-sm text-white focus:border-primary focus:outline-none"
                  dir="ltr"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    نوع سایت
                  </label>
                  <select
                    value={editSiteModal.websiteType}
                    onChange={(e) =>
                      setEditSiteModal((prev) => ({ ...prev, websiteType: e.target.value }))
                    }
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2.5 text-xs text-white focus:border-primary focus:outline-none"
                  >
                    <option value="blog">وبلاگ / مجله</option>
                    <option value="ecommerce">فروشگاهی</option>
                    <option value="corporate">شرکتی</option>
                    <option value="saas">سرویس آنلاین</option>
                  </select>
                </div>

                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    حالت اتوماسیون
                  </label>
                  <select
                    value={editSiteModal.automationMode}
                    onChange={(e) =>
                      setEditSiteModal((prev) => ({ ...prev, automationMode: e.target.value }))
                    }
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2.5 text-xs text-white focus:border-primary focus:outline-none"
                  >
                    <option value="ai_assist">دستیار هوشمند</option>
                    <option value="manual">دستی</option>
                    <option value="autopilot">خودکار</option>
                  </select>
                </div>
              </div>

              <div className="mt-6 flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() =>
                    setEditSiteModal({
                      open: false,
                      site: null,
                      name: "",
                      domain: "",
                      baseUrl: "",
                      websiteType: "blog",
                      automationMode: "ai_assist",
                      loading: false,
                    })
                  }
                  className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-muted-foreground hover:bg-white/5"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  disabled={editSiteModal.loading}
                  className="rounded-xl bg-primary px-5 py-2 text-xs font-semibold text-primary-foreground shadow-lg hover:bg-primary/90 disabled:opacity-50"
                >
                  {editSiteModal.loading ? "در حال ذخیره..." : "ذخیره تغییرات"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Delete Website Confirm */}
      {deleteSiteModal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-red-500/30 bg-card p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-red-400">
              <AlertTriangle className="h-6 w-6 shrink-0" />
              <h3 className="text-base font-bold text-white">حذف وب‌سایت «{deleteSiteModal.site?.name}»</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              آیا از حذف کامل این وب‌سایت مطمئن هستید؟ با حذف وب‌سایت، تمامی گزارش‌های سئو، مقالات و تنظیمات مرتبط برای همیشه پاک خواهند شد.
            </p>
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setDeleteSiteModal({ open: false, site: null, loading: false })}
                className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-muted-foreground hover:bg-white/5"
              >
                انصراف
              </button>
              <button
                type="button"
                onClick={submitDeleteWebsite}
                disabled={deleteSiteModal.loading}
                className="rounded-xl bg-red-600 px-5 py-2 text-xs font-semibold text-white shadow-lg hover:bg-red-500 disabled:opacity-50"
              >
                {deleteSiteModal.loading ? "در حال حذف..." : "حذف وب‌سایت"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
