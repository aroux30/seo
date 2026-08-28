"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/context/auth-context";
import { api, ApiError } from "@/lib/api-client";
import { Save, Trash2, Globe, Settings2, AlertTriangle, X } from "lucide-react";
import toast from "react-hot-toast";

export default function WebsiteSettingsPage() {
  const params = useParams();
  const router = useRouter();
  const websiteId = params.id as string;
  const { currentWebsite, setCurrentWebsite, refreshOrgsAndWebsites, websites } = useAuth();

  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [language, setLanguage] = useState("fa");
  const [country, setCountry] = useState("IR");
  const [saving, setSaving] = useState(false);

  // Delete Modal State
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (currentWebsite) {
      setName(currentWebsite.name);
      setDomain(currentWebsite.domain);
      setBaseUrl(currentWebsite.base_url);
      setLanguage(currentWebsite.language || "fa");
      setCountry(currentWebsite.country || "IR");
    }
  }, [currentWebsite]);

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await api.patch(`/websites/${websiteId}`, {
        name,
        domain,
        base_url: baseUrl,
        language,
        country,
      });
      setCurrentWebsite(res);
      await refreshOrgsAndWebsites();
      toast.success("تنظیمات سایت با موفقیت ذخیره شد");
    } catch (err: any) {
      toast.error(err.message || "خطا در ذخیره تنظیمات");
    } finally {
      setSaving(false);
    }
  };

  const submitDelete = async () => {
    setDeleting(true);
    try {
      await api.delete(`/websites/${websiteId}`);
      await refreshOrgsAndWebsites();
      const remaining = websites.filter((w) => w.id !== websiteId);
      setCurrentWebsite(remaining.length > 0 ? remaining[0] : null);
      toast.success("سایت با موفقیت حذف شد");
      router.push("/websites");
    } catch (err: any) {
      toast.error(err.message || "خطا در حذف سایت");
      setDeleting(false);
    }
  };

  if (!currentWebsite) {
    return <div className="py-12 text-center text-xs text-muted-foreground">در حال بارگذاری...</div>;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="rounded-2xl border border-white/10 bg-card/60 p-6 shadow-xl backdrop-blur-md">
        <div className="mb-6 flex items-center gap-3 border-b border-white/10 pb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/15 text-blue-400">
            <Settings2 className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">تنظیمات وب‌سایت</h2>
            <p className="text-xs text-muted-foreground">ویرایش اطلاعات پایه و مشخصات دامنه</p>
          </div>
        </div>

        <form onSubmit={handleUpdate} className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
              نام وب‌سایت
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-sm text-white focus:border-primary focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                دامنه (مثال: example.com)
              </label>
              <input
                type="text"
                required
                dir="ltr"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-sm text-white focus:border-primary focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                آدرس کامل سایت (URL)
              </label>
              <input
                type="url"
                required
                dir="ltr"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-sm text-white focus:border-primary focus:outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                زبان محتوا (Language)
              </label>
              <input
                type="text"
                dir="ltr"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-sm text-white focus:border-primary focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                کشور هدف (Country)
              </label>
              <input
                type="text"
                dir="ltr"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-sm text-white focus:border-primary focus:outline-none"
              />
            </div>
          </div>

          <div className="mt-6 flex justify-end pt-4">
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/25 hover:bg-primary/90 disabled:opacity-50"
            >
              <Save className="h-4 w-4" />
              <span>{saving ? "در حال ذخیره..." : "ذخیره تغییرات"}</span>
            </button>
          </div>
        </form>
      </div>

      <div className="rounded-2xl border border-red-500/30 bg-red-500/5 p-6 shadow-xl backdrop-blur-md">
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-red-500/15 text-red-500">
            <Trash2 className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">حذف وب‌سایت (Danger Zone)</h2>
            <p className="text-xs text-muted-foreground">حذف کامل این وب‌سایت و تمام داده‌های مرتبط با آن</p>
          </div>
        </div>
        
        <p className="mb-6 text-xs leading-relaxed text-red-200">
          با انجام این کار، تمام گزارش‌ها، کلمات کلیدی، استراتژی‌ها و تنظیمات مرتبط با این وب‌سایت برای همیشه حذف خواهند شد و قابل بازیابی نخواهند بود.
        </p>

        <button
          onClick={() => setDeleteModalOpen(true)}
          className="flex items-center gap-2 rounded-xl bg-red-600 px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-red-600/30 hover:bg-red-500"
        >
          <Trash2 className="h-4 w-4" />
          <span>حذف کامل وب‌سایت</span>
        </button>
      </div>

      {/* Delete Confirmation Modal */}
      {deleteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-red-500/30 bg-card p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-red-400">
              <AlertTriangle className="h-6 w-6 shrink-0" />
              <h3 className="text-base font-bold text-white">تایید حذف وب‌سایت</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              آیا از حذف وب‌سایت «{currentWebsite.name}» مطمئن هستید؟ این عمل غیرقابل بازگشت است و تمامی داده‌ها پاک می‌شوند.
            </p>
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setDeleteModalOpen(false)}
                className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-muted-foreground hover:bg-white/5"
              >
                انصراف
              </button>
              <button
                type="button"
                onClick={submitDelete}
                disabled={deleting}
                className="rounded-xl bg-red-600 px-5 py-2 text-xs font-semibold text-white shadow-lg hover:bg-red-500 disabled:opacity-50"
              >
                {deleting ? "در حال حذف..." : "حذف قطعی وب‌سایت"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
