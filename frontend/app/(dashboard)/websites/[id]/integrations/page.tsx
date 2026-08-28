"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError } from "@/lib/api-client";
import {
  Plug,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  Sparkles,
  Lock,
  Info,
  RefreshCw,
} from "lucide-react";
import toast from "react-hot-toast";

export default function WebsiteIntegrationsPage() {
  const params = useParams();
  const websiteId = params.id as string;

  const [gscStatus, setGscStatus] = useState<{ is_connected: boolean; provider?: string } | null>(null);
  const [wpStatus, setWpStatus] = useState<{ is_connected: boolean; wp_url?: string; username?: string } | null>(null);
  const [loading, setLoading] = useState(true);

  // WP Form
  const [wpUrl, setWpUrl] = useState("");
  const [wpUsername, setWpUsername] = useState("");
  const [wpPassword, setWpPassword] = useState("");
  const [wpConnecting, setWpConnecting] = useState(false);
  const [wpError, setWpError] = useState<string | null>(null);
  const [wpSuccess, setWpSuccess] = useState<string | null>(null);

  // GSC Sync
  const [gscSyncing, setGscSyncing] = useState(false);
  const [gscSyncResult, setGscSyncResult] = useState<string | null>(null);

  useEffect(() => {
    loadStatus();
  }, [websiteId]);

  const loadStatus = async () => {
    setLoading(true);
    try {
      const [gsc, wp] = await Promise.all([
        api.get(`/integrations/gsc/status/${websiteId}`),
        api.get(`/integrations/wordpress/status/${websiteId}`),
      ]);
      setGscStatus(gsc);
      setWpStatus(wp);
      if (wp && wp.is_connected) {
        setWpUrl(wp.wp_url || "");
        setWpUsername(wp.username || "");
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const handleConnectGsc = async () => {
    try {
      const res = await api.get<{ auth_url: string }>(
        `/integrations/gsc/auth-url?website_id=${websiteId}`
      );
      if (res && res.auth_url) {
        // Redirect user to Google Consent screen
        window.location.href = res.auth_url;
      }
    } catch (err: any) {
      toast.error(err.message || "خطا در دریافت آدرس ورود گوگل");
    }
  };

  const handleSyncGsc = async () => {
    setGscSyncing(true);
    setGscSyncResult(null);
    try {
      const res = await api.post(`/integrations/gsc/sync/${websiteId}`);
      setGscSyncResult(
        `همگام‌سازی انجام شد: ${res.queries_added} کلمه کلیدی و ${res.pages_added} صفحه به روز شد.`
      );
      await loadStatus();
    } catch {
      setGscSyncResult("خطا در همگام‌سازی داده‌ها از سرچ کنسول");
    } finally {
      setGscSyncing(false);
    }
  };

  const handleConnectWp = async (e: React.FormEvent) => {
    e.preventDefault();
    setWpConnecting(true);
    setWpError(null);
    setWpSuccess(null);

    try {
      await api.post(`/integrations/wordpress/connect?website_id=${websiteId}`, {
        wp_url: wpUrl,
        username: wpUsername,
        app_password: wpPassword,
      });
      setWpSuccess("اتصال وب‌سایت وردپرسی با موفقیت برقرار و تأیید شد.");
      setWpPassword("");
      await loadStatus();
    } catch (err: any) {
      if (err instanceof ApiError) {
        setWpError(err.message);
      } else {
        setWpError("خطا در برقراری اتصال با وردپرس");
      }
    } finally {
      setWpConnecting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-bold text-white">
          اتصال سرویس‌ها (Integrations & Connectors)
        </h2>
        <p className="text-xs text-muted-foreground">
          اتصال وب‌سایت به Search Console و WordPress REST API برای اتوماسیون کامل سئو
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Google Search Console Card */}
        <div className="rounded-2xl border border-white/10 bg-card/60 p-6 shadow-xl backdrop-blur-md">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-500/15 text-blue-400">
                <Plug className="h-6 w-6" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">
                  Google Search Console
                </h3>
                <p className="text-xs text-muted-foreground">
                  دریافت کلیک‌ها، ایمپرشن‌ها، CTR و جایگاه کلمات کلیدی در نتایج گوگل
                </p>
              </div>
            </div>

            <span
              className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold ${
                gscStatus?.is_connected
                  ? "bg-emerald-500/15 text-emerald-400"
                  : "bg-white/5 text-muted-foreground"
              }`}
            >
              {gscStatus?.is_connected ? (
                <>
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  <span>متصل</span>
                </>
              ) : (
                <span>متصل نشده</span>
              )}
            </span>
          </div>

          <div className="mt-6 border-t border-white/10 pt-4">
            <p className="text-xs leading-relaxed text-muted-foreground">
              با اتصال سرچ کنسول، پلتفرم هر روز به صورت خودکار داده‌های سئو را از گوگل استخراج کرده و روند پیشرفت وب‌سایت را تحلیل می‌کند.
            </p>

            {gscSyncResult && (
              <div className="mt-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-300">
                {gscSyncResult}
              </div>
            )}

            <div className="mt-5 flex flex-wrap items-center gap-3">
              <button
                onClick={handleConnectGsc}
                className="flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-blue-600/30 transition hover:bg-blue-500"
              >
                <span>
                  {gscStatus?.is_connected
                    ? "تغییر اکانت متصل (Google OAuth)"
                    : "اتصال با حساب گوگل (Google OAuth)"}
                </span>
                <ExternalLink className="h-4 w-4" />
              </button>

              <button
                onClick={handleSyncGsc}
                disabled={gscSyncing}
                className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-white/10 disabled:opacity-50"
              >
                <RefreshCw className={`h-4 w-4 ${gscSyncing ? "animate-spin" : ""}`} />
                <span>{gscSyncing ? "در حال دریافت داده..." : "همگام‌سازی دستی اکنون"}</span>
              </button>
            </div>
          </div>
        </div>

        {/* WordPress REST API Card */}
        <div className="rounded-2xl border border-white/10 bg-card/60 p-6 shadow-xl backdrop-blur-md">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-purple-500/15 text-purple-400">
                <Sparkles className="h-6 w-6" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">
                  WordPress REST API
                </h3>
                <p className="text-xs text-muted-foreground">
                  اتصال به وردپرس برای انتشار خودکار یا پیش‌نویس مقالات سئوشده
                </p>
              </div>
            </div>

            <span
              className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold ${
                wpStatus?.is_connected
                  ? "bg-emerald-500/15 text-emerald-400"
                  : "bg-white/5 text-muted-foreground"
              }`}
            >
              {wpStatus?.is_connected ? (
                <>
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  <span>متصل و تأییدشده</span>
                </>
              ) : (
                <span>متصل نشده</span>
              )}
            </span>
          </div>

          <form onSubmit={handleConnectWp} className="mt-6 space-y-4 border-t border-white/10 pt-4">
            {wpError && (
              <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-400">
                {wpError}
              </div>
            )}
            {wpSuccess && (
              <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-300">
                {wpSuccess}
              </div>
            )}
            
            <div className="rounded-xl border border-blue-500/30 bg-blue-500/10 p-4 text-xs text-blue-200">
              <div className="mb-2 flex items-center gap-2 font-semibold text-blue-300">
                <Info className="h-4 w-4" />
                راهنمای ساخت رمز اپلیکیشن وردپرس
              </div>
              <ul className="list-inside list-decimal space-y-1.5 opacity-90">
                <li>وارد پیشخوان وردپرس سایت خود شوید.</li>
                <li>از منوی کناری، به بخش <strong>کاربران &gt; شناسه شما</strong> (Profile) بروید.</li>
                <li>به پایین صفحه (بخش <strong>رمزهای عبور برنامه</strong> یا Application Passwords) اسکرول کنید.</li>
                <li>یک نام دلخواه (مثلاً <code>SEO-App</code>) وارد کرده و روی <strong>افزودن رمز عبور جدید برنامه</strong> کلیک کنید.</li>
                <li>رمز تولید شده را کپی کرده و در فیلد زیر قرار دهید. (این رمز شامل فضاهای خالی است که مشکلی ایجاد نمی‌کند)</li>
              </ul>
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                آدرس سایت وردپرس (URL)
              </label>
              <input
                type="url"
                required
                value={wpUrl}
                onChange={(e) => setWpUrl(e.target.value)}
                placeholder="https://example.com"
                className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-xs text-white placeholder-muted-foreground focus:border-primary focus:outline-none"
                dir="ltr"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  نام کاربری (Username)
                </label>
                <input
                  type="text"
                  required
                  value={wpUsername}
                  onChange={(e) => setWpUsername(e.target.value)}
                  placeholder="admin"
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-xs text-white placeholder-muted-foreground focus:border-primary focus:outline-none"
                  dir="ltr"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  رمز اپلیکیشن (Application Password)
                </label>
                <div className="relative">
                  <input
                    type="password"
                    required
                    value={wpPassword}
                    onChange={(e) => setWpPassword(e.target.value)}
                    placeholder="xxxx xxxx xxxx xxxx"
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-xs text-white placeholder-muted-foreground focus:border-primary focus:outline-none"
                    dir="ltr"
                  />
                </div>
              </div>
            </div>

            <div className="pt-2">
              <button
                type="submit"
                disabled={wpConnecting}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-purple-600 py-2.5 text-xs font-semibold text-white shadow-lg shadow-purple-600/30 transition hover:bg-purple-500 disabled:opacity-50"
              >
                <Lock className="h-3.5 w-3.5" />
                <span>
                  {wpConnecting ? "در حال بررسی و ذخیره رمزنگاری‌شده..." : "ذخیره و تست اتصال وردپرس"}
                </span>
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
