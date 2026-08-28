"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@/context/auth-context";
import {
  User,
  Shield,
  Key,
  Cpu,
  Sparkles,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  Plus,
  Trash2,
  Zap,
  RefreshCw,
  Power,
  Server,
  Activity,
  Bot,
} from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api-client";
import {
  AiProviderKey,
  getAiProviderKeys,
  createAiProviderKey,
  updateAiProviderKey,
  deleteAiProviderKey,
  testStoredAiKey,
  testRawAiKey,
} from "@/lib/ai-providers";
import toast from "react-hot-toast";

const PROVIDER_OPTIONS = [
  { id: "gemini", name: "Google Gemini (پیشنهادی)", defaultModel: "gemini-2.5-flash", color: "from-blue-500 to-indigo-600" },
  { id: "openai", name: "OpenAI (GPT-4o / Mini)", defaultModel: "gpt-4o-mini", color: "from-emerald-500 to-teal-600" },
  { id: "claude", name: "Anthropic Claude", defaultModel: "claude-3-5-haiku-20241022", color: "from-amber-500 to-orange-600" },
  { id: "deepseek", name: "DeepSeek AI", defaultModel: "deepseek-chat", color: "from-cyan-500 to-blue-600" },
  { id: "openrouter", name: "OpenRouter", defaultModel: "google/gemini-2.5-flash-001", color: "from-purple-500 to-pink-600" },
];

export default function SettingsPage() {
  const { user, currentOrg } = useAuth();

  // Profile Form
  const [profileForm, setProfileForm] = useState({ full_name: "" });
  const [profileLoading, setProfileLoading] = useState(false);

  // Password Form
  const [passwordForm, setPasswordForm] = useState({ current_password: "", new_password: "", confirm_password: "" });
  const [passwordLoading, setPasswordLoading] = useState(false);

  // AI Provider Keys
  const [aiKeys, setAiKeys] = useState<AiProviderKey[]>([]);
  const [loadingKeys, setLoadingKeys] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [testingKeyId, setTestingKeyId] = useState<string | null>(null);
  const [testingRaw, setTestingRaw] = useState(false);

  // New Key Form
  const [newKeyForm, setNewKeyForm] = useState({
    provider_name: "gemini",
    label: "",
    api_key: "",
    model_name: "gemini-2.5-flash",
    priority: 1,
  });

  useEffect(() => {
    if (user) setProfileForm({ full_name: user.full_name || "" });
    fetchAiKeys();
  }, [user, currentOrg]);

  const fetchAiKeys = async () => {
    try {
      setLoadingKeys(true);
      const data = await getAiProviderKeys();
      setAiKeys(data);
    } catch (err: any) {
      console.error("Error fetching AI keys:", err);
    } finally {
      setLoadingKeys(false);
    }
  };

  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileLoading(true);
    try {
      await api.patch("/auth/me", profileForm);
      toast.success("پروفایل با موفقیت بروزرسانی شد");
      setTimeout(() => window.location.reload(), 1000);
    } catch (err: any) {
      toast.error(err.message || "خطا در بروزرسانی پروفایل");
    } finally {
      setProfileLoading(false);
    }
  };

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      toast.error("تکرار رمز عبور جدید تطابق ندارد");
      return;
    }
    setPasswordLoading(true);
    try {
      await api.put("/auth/me/password", {
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password,
      });
      toast.success("رمز عبور با موفقیت تغییر یافت");
      setPasswordForm({ current_password: "", new_password: "", confirm_password: "" });
    } catch (err: any) {
      toast.error(err.message || "خطا در تغییر رمز عبور");
    } finally {
      setPasswordLoading(false);
    }
  };

  const handleProviderSelect = (providerId: string) => {
    const prov = PROVIDER_OPTIONS.find((p) => p.id === providerId);
    setNewKeyForm((prev) => ({
      ...prev,
      provider_name: providerId,
      model_name: prov?.defaultModel || prev.model_name,
    }));
  };

  const handleTestRawKey = async () => {
    if (!newKeyForm.api_key.trim()) {
      toast.error("لطفاً ابتدا کلید API را وارد کنید.");
      return;
    }
    setTestingRaw(true);
    try {
      const res = await testRawAiKey({
        provider_name: newKeyForm.provider_name,
        api_key: newKeyForm.api_key,
        model_name: newKeyForm.model_name,
      });
      toast.success(`اتصال برقرار شد! زمان پاسخ: ${res.latency_ms} میلی‌ثانیه`);
    } catch (err: any) {
      toast.error(err.message || "تست اتصال ناموفق بود. کلید یا مدل را بررسی کنید.");
    } finally {
      setTestingRaw(false);
    }
  };

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyForm.label.trim() || !newKeyForm.api_key.trim()) {
      toast.error("لطفاً تمام فیلدها را تکمیل کنید.");
      return;
    }
    try {
      await createAiProviderKey({
        provider_name: newKeyForm.provider_name,
        label: newKeyForm.label,
        api_key: newKeyForm.api_key,
        model_name: newKeyForm.model_name,
        priority: Number(newKeyForm.priority) || 1,
        is_active: true,
      });
      toast.success("کلید هوش مصنوعی با موفقیت به استخر اضافه شد.");
      setShowAddModal(false);
      setNewKeyForm({
        provider_name: "gemini",
        label: "",
        api_key: "",
        model_name: "gemini-2.5-flash",
        priority: aiKeys.length + 1,
      });
      fetchAiKeys();
    } catch (err: any) {
      toast.error(err.message || "خطا در ثبت کلید.");
    }
  };

  const handleToggleKeyActive = async (key: AiProviderKey) => {
    try {
      await updateAiProviderKey(key.id, { is_active: !key.is_active });
      toast.success(`کلید ${!key.is_active ? "فعال" : "غیرفعال"} شد.`);
      fetchAiKeys();
    } catch (err: any) {
      toast.error(err.message || "خطا در تغییر وضعیت کلید.");
    }
  };

  const handleDeleteKey = async (key: AiProviderKey) => {
    if (!confirm(`آیا از حذف کلید "${key.label}" اطمینان دارید؟`)) return;
    try {
      await deleteAiProviderKey(key.id);
      toast.success("کلید با موفقیت حذف شد.");
      fetchAiKeys();
    } catch (err: any) {
      toast.error(err.message || "خطا در حذف کلید.");
    }
  };

  const handleTestStoredKey = async (key: AiProviderKey) => {
    setTestingKeyId(key.id);
    try {
      const res = await testStoredAiKey(key.id);
      toast.success(`کلید "${key.label}" فعال است! تاخیر: ${res.latency_ms}ms`);
      fetchAiKeys();
    } catch (err: any) {
      toast.error(err.message || "تست ناموفق بود.");
      fetchAiKeys();
    } finally {
      setTestingKeyId(null);
    }
  };

  return (
    <div className="space-y-8 pb-12">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">
          تنظیمات سیستم و ارائه‌دهندگان هوش مصنوعی
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          مدیریت استخر کلیدهای هوش مصنوعی (Gemini Pro, OpenAI, Claude)، چرخش خودکار سهمیه‌ها و پروفایل کاربری
        </p>
      </div>

      {/* --- AI PROVIDERS & MULTI-KEY POOL CARD --- */}
      <div className="rounded-2xl border border-primary/20 bg-card/70 p-6 shadow-2xl backdrop-blur-xl">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-white/10 pb-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/20 text-primary">
              <Bot className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                استخر کلیدهای هوش مصنوعی (AI Key Pool & Auto-Rotation)
                <span className="rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-400 border border-emerald-500/20">
                  اتصال مستقیم (بدون n8n)
                </span>
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                کلیدهای پرو (Gemini, OpenAI, Claude) را وارد کنید؛ سیستم در صورت اتمام سهمیه یا خطای 429 به طور خودکار بین کلیدها سوئیچ می‌کند.
              </p>
            </div>
          </div>

          <button
            onClick={() => {
              setNewKeyForm((prev) => ({ ...prev, priority: aiKeys.length + 1 }));
              setShowAddModal(true);
            }}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-xs font-semibold text-primary-foreground shadow-lg shadow-primary/20 transition hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" />
            افزودن کلید جدید به استخر
          </button>
        </div>

        {/* Informational Rotation Banner */}
        <div className="mt-4 rounded-xl border border-white/5 bg-black/30 p-3.5 flex items-start gap-3 text-xs text-muted-foreground">
          <Zap className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold text-white">منطق چرخش هوشمند و اولویت:</span> کلیدها به ترتیب اولویت (اولویت ۱، سپس ۲ و ...) برای تولید مقالات و بریف‌ها فراخوانی می‌شوند. در صورت بروز محدودیت سهمیه (Quota Exhausted / 429)، کلید موقتاً در حالت خنک‌سازی قرار گرفته و درخواست فوراً با کلید بعدی پردازش می‌شود.
          </div>
        </div>

        {/* Keys List */}
        <div className="mt-6 space-y-3">
          {loadingKeys ? (
            <div className="py-8 text-center text-xs text-muted-foreground">
              در حال بارگذاری کلیدهای هوش مصنوعی...
            </div>
          ) : aiKeys.length === 0 ? (
            <div className="rounded-xl border border-dashed border-white/10 p-8 text-center">
              <Bot className="mx-auto h-8 w-8 text-muted-foreground/50 mb-2" />
              <p className="text-xs font-medium text-white">هنوز کلیدی در استخر ثبت نشده است</p>
              <p className="text-[11px] text-muted-foreground mt-1">
                برای تولید سریع مقالات با اکانت‌های جمینای پرو یا OpenAI، دکمه «افزودن کلید جدید» را بزنید.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3">
              {aiKeys.map((k) => {
                const prov = PROVIDER_OPTIONS.find((p) => p.id === k.provider_name);
                const isTesting = testingKeyId === k.id;

                let statusBadge = (
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-400 border border-emerald-500/20">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    آماده به کار
                  </span>
                );

                if (!k.is_active) {
                  statusBadge = (
                    <span className="inline-flex items-center gap-1 rounded-full bg-zinc-500/10 px-2 py-0.5 text-[11px] font-medium text-zinc-400 border border-zinc-500/20">
                      غیرفعال
                    </span>
                  );
                } else if (k.status === "rate_limited") {
                  statusBadge = (
                    <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-400 border border-amber-500/20">
                      <AlertTriangle className="h-3 w-3" />
                      محدودیت سهمیه (Cooldown)
                    </span>
                  );
                } else if (k.error_count > 0) {
                  statusBadge = (
                    <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/10 px-2 py-0.5 text-[11px] font-medium text-rose-400 border border-rose-500/20">
                      دارای خطا ({k.error_count})
                    </span>
                  );
                }

                return (
                  <div
                    key={k.id}
                    className={`rounded-xl border p-4 transition-all flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 ${
                      k.is_active
                        ? "border-white/10 bg-black/40 hover:border-white/20"
                        : "border-white/5 bg-black/20 opacity-60"
                    }`}
                  >
                    <div className="flex items-start sm:items-center gap-3.5">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-white/10 to-white/5 border border-white/10 text-white font-bold text-xs shrink-0">
                        #{k.priority}
                      </div>
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="text-sm font-bold text-white">{k.label}</h3>
                          <span className="rounded-md bg-white/5 px-2 py-0.5 text-[10px] font-medium text-muted-foreground border border-white/5 uppercase">
                            {k.provider_name}
                          </span>
                          {statusBadge}
                        </div>
                        <div className="mt-1 flex items-center gap-3 text-[11px] text-muted-foreground">
                          <span>مدل: <strong className="text-white/80">{k.model_name}</strong></span>
                          <span>•</span>
                          <span className="font-mono text-[10px]" dir="ltr">{k.masked_api_key}</span>
                          <span>•</span>
                          <span>مصرف: {k.usage_count} درخواست</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 self-end sm:self-center">
                      <button
                        onClick={() => handleTestStoredKey(k)}
                        disabled={isTesting}
                        title="تست اتصال زنده"
                        className="inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-2.5 py-1.5 text-xs text-white transition hover:bg-white/10 disabled:opacity-50"
                      >
                        <Zap className={`h-3.5 w-3.5 text-amber-400 ${isTesting ? "animate-spin" : ""}`} />
                        <span>{isTesting ? "در حال تست..." : "تست زنده"}</span>
                      </button>

                      <button
                        onClick={() => handleToggleKeyActive(k)}
                        title={k.is_active ? "غیرفعال‌سازی کلید" : "فعال‌سازی کلید"}
                        className={`rounded-lg border px-2.5 py-1.5 text-xs transition ${
                          k.is_active
                            ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"
                            : "border-zinc-500/30 bg-zinc-500/10 text-zinc-400 hover:bg-zinc-500/20"
                        }`}
                      >
                        <Power className="h-3.5 w-3.5" />
                      </button>

                      <button
                        onClick={() => handleDeleteKey(k)}
                        title="حذف کلید"
                        className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-1.5 text-xs text-rose-400 transition hover:bg-rose-500/20"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* --- ADD NEW KEY MODAL --- */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-zinc-950 p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-4 mb-4">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Key className="h-5 w-5 text-primary" />
                افزودن کلید API هوش مصنوعی به استخر
              </h3>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-muted-foreground hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateKey} className="space-y-4 text-xs">
              <div>
                <label className="mb-1.5 block font-medium text-muted-foreground">انتخاب ارائه‌دهنده</label>
                <div className="grid grid-cols-2 gap-2">
                  {PROVIDER_OPTIONS.map((p) => (
                    <button
                      type="button"
                      key={p.id}
                      onClick={() => handleProviderSelect(p.id)}
                      className={`rounded-xl border p-2.5 text-right transition flex items-center justify-between ${
                        newKeyForm.provider_name === p.id
                          ? "border-primary bg-primary/10 text-white font-bold"
                          : "border-white/10 bg-black/40 text-muted-foreground hover:border-white/20"
                      }`}
                    >
                      <span>{p.name}</span>
                      {newKeyForm.provider_name === p.id && <CheckCircle2 className="h-4 w-4 text-primary" />}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="mb-1 block font-medium text-muted-foreground">نام یا برچسب کلید (جهت تشخیص)</label>
                <input
                  type="text"
                  required
                  placeholder="مثلاً: اکانت شماره ۱ جمینای پرو"
                  value={newKeyForm.label}
                  onChange={(e) => setNewKeyForm((p) => ({ ...p, label: e.target.value }))}
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-white focus:border-primary focus:outline-none"
                />
              </div>

              <div>
                <label className="mb-1 block font-medium text-muted-foreground">کلید API (API Key)</label>
                <input
                  type="password"
                  required
                  placeholder="AIzaSy..."
                  value={newKeyForm.api_key}
                  onChange={(e) => setNewKeyForm((p) => ({ ...p, api_key: e.target.value }))}
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-white focus:border-primary focus:outline-none font-mono text-[11px]"
                  dir="ltr"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block font-medium text-muted-foreground">مدل پیش‌فرض</label>
                  <input
                    type="text"
                    required
                    value={newKeyForm.model_name}
                    onChange={(e) => setNewKeyForm((p) => ({ ...p, model_name: e.target.value }))}
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-white focus:border-primary focus:outline-none font-mono text-[11px]"
                    dir="ltr"
                  />
                </div>
                <div>
                  <label className="mb-1 block font-medium text-muted-foreground">اولویت استفاده (۱ = بالاترین)</label>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    required
                    value={newKeyForm.priority}
                    onChange={(e) => setNewKeyForm((p) => ({ ...p, priority: Number(e.target.value) }))}
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-white focus:border-primary focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex items-center justify-between pt-4 border-t border-white/10">
                <button
                  type="button"
                  onClick={handleTestRawKey}
                  disabled={testingRaw}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs font-semibold text-amber-400 transition hover:bg-amber-500/20 disabled:opacity-50"
                >
                  <Zap className={`h-3.5 w-3.5 ${testingRaw ? "animate-spin" : ""}`} />
                  <span>{testingRaw ? "در حال تست اتصال..." : "تست زنده اتصال"}</span>
                </button>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setShowAddModal(false)}
                    className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-xs font-semibold text-white hover:bg-white/10"
                  >
                    انصراف
                  </button>
                  <button
                    type="submit"
                    className="rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground shadow-lg shadow-primary/20 hover:bg-primary/90"
                  >
                    ذخیره و ثبت در استخر
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* --- PROFILE & PASSWORD CARDS --- */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          {/* User Profile Card */}
          <div className="rounded-2xl border border-white/10 bg-card/60 p-6 shadow-xl backdrop-blur-md">
            <div className="mb-4 flex items-center gap-2 text-primary">
              <User className="h-5 w-5" />
              <h2 className="text-base font-bold text-white">ویرایش اطلاعات کاربری</h2>
            </div>

            <form onSubmit={handleProfileSubmit} className="space-y-4 text-xs">
              <div>
                <label className="mb-1 block font-medium text-muted-foreground">ایمیل متصل (غیرقابل تغییر)</label>
                <input
                  type="email"
                  disabled
                  value={user?.email || ""}
                  className="w-full rounded-xl border border-white/5 bg-black/20 px-3.5 py-2 text-white opacity-50 cursor-not-allowed"
                  dir="ltr"
                />
              </div>
              <div>
                <label className="mb-1 block font-medium text-muted-foreground">نام و نام خانوادگی</label>
                <input
                  type="text"
                  required
                  value={profileForm.full_name}
                  onChange={(e) => setProfileForm((p) => ({ ...p, full_name: e.target.value }))}
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-white focus:border-primary focus:outline-none"
                />
              </div>
              <div className="flex justify-end pt-2">
                <button
                  type="submit"
                  disabled={profileLoading}
                  className="rounded-xl bg-primary px-4 py-2 font-semibold text-primary-foreground shadow-lg shadow-primary/20 hover:bg-primary/90 disabled:opacity-50"
                >
                  {profileLoading ? "در حال ذخیره..." : "ذخیره تغییرات"}
                </button>
              </div>
            </form>
          </div>
        </div>

        <div>
          {/* Password Card */}
          <div className="rounded-2xl border border-white/10 bg-card/60 p-6 shadow-xl backdrop-blur-md">
            <div className="mb-4 flex items-center gap-2 text-amber-500">
              <Shield className="h-5 w-5" />
              <h2 className="text-base font-bold text-white">تغییر رمز عبور</h2>
            </div>

            <form onSubmit={handlePasswordSubmit} className="space-y-4 text-xs">
              <div>
                <label className="mb-1 block font-medium text-muted-foreground">رمز عبور فعلی</label>
                <input
                  type="password"
                  required
                  value={passwordForm.current_password}
                  onChange={(e) => setPasswordForm((p) => ({ ...p, current_password: e.target.value }))}
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-white focus:border-amber-500 focus:outline-none"
                  dir="ltr"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block font-medium text-muted-foreground">رمز عبور جدید</label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    value={passwordForm.new_password}
                    onChange={(e) => setPasswordForm((p) => ({ ...p, new_password: e.target.value }))}
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-white focus:border-amber-500 focus:outline-none"
                    dir="ltr"
                  />
                </div>
                <div>
                  <label className="mb-1 block font-medium text-muted-foreground">تکرار رمز عبور جدید</label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    value={passwordForm.confirm_password}
                    onChange={(e) => setPasswordForm((p) => ({ ...p, confirm_password: e.target.value }))}
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-white focus:border-amber-500 focus:outline-none"
                    dir="ltr"
                  />
                </div>
              </div>
              <div className="flex justify-end pt-2">
                <button
                  type="submit"
                  disabled={passwordLoading}
                  className="rounded-xl bg-amber-500 px-4 py-2 font-semibold text-white shadow-lg shadow-amber-500/20 hover:bg-amber-600 disabled:opacity-50"
                >
                  {passwordLoading ? "در حال تغییر..." : "تغییر رمز عبور"}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>

      {/* OAuth Integration Status Banner */}
      <div className="rounded-2xl border border-blue-500/30 bg-blue-500/10 p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-base font-bold text-blue-300">
              اتصال Google Search Console
            </h3>
            <p className="mt-1 text-xs text-blue-200/80">
              برای آغاز دریافت کلمات کلیدی، کلیک‌ها و ایمپرشن‌های وب‌سایت‌ها، باید کلیدهای OAuth در کنسول Google Cloud ساخته شود.
            </p>
          </div>
          <Link
            href="/guides"
            className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-blue-600/30 transition hover:bg-blue-500"
          >
            <span>راهنمای گام‌به‌گام ساخت OAuth</span>
            <ExternalLink className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>
    </div>
  );
}
