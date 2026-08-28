"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api-client";
import { Lock, ArrowLeft, Key, CheckCircle2 } from "lucide-react";
import toast from "react-hot-toast";

import { Suspense } from "react";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (!token) {
      setError("توکن بازیابی نامعتبر است یا وجود ندارد. لطفاً دوباره درخواست دهید.");
    }
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;

    if (password !== confirmPassword) {
      setError("رمز عبور و تکرار آن تطابق ندارند.");
      return;
    }
    
    if (password.length < 8) {
      setError("رمز عبور باید حداقل ۸ کاراکتر باشد.");
      return;
    }

    setError(null);
    setLoading(true);

    try {
      await api.post("/auth/reset-password", { token, new_password: password });
      setSuccess(true);
      toast.success("رمز عبور با موفقیت تغییر کرد.");
      setTimeout(() => {
        router.push("/login");
      }, 3000);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("خطا در برقراری ارتباط با سرور. ممکن است توکن منقضی شده باشد.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4">
      <div className="pointer-events-none absolute -top-40 -left-40 h-96 w-96 rounded-full bg-primary/20 blur-[120px]" />
      <div className="pointer-events-none absolute -bottom-40 -right-40 h-96 w-96 rounded-full bg-emerald-600/15 blur-[120px]" />

      <div className="relative z-10 w-full max-w-md rounded-2xl border border-white/10 bg-card/60 p-8 shadow-2xl backdrop-blur-xl">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/20 text-primary shadow-inner">
            <Key className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            تنظیم رمز عبور جدید
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            رمز عبور جدید خود را وارد کنید.
          </p>
        </div>

        {error && (
          <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {success ? (
          <div className="space-y-6 text-center">
            <div className="flex flex-col items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-6 text-emerald-400">
              <CheckCircle2 className="h-12 w-12 mb-3" />
              <p className="text-sm font-medium">رمز عبور با موفقیت تغییر یافت.</p>
              <p className="mt-2 text-xs opacity-80">در حال انتقال به صفحه ورود...</p>
            </div>
            <Link
              href="/login"
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-primary py-3 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/25 transition hover:bg-primary/90"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>ورود با رمز جدید</span>
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                رمز عبور جدید
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 right-3 flex items-center text-muted-foreground">
                  <Lock className="h-4 w-4" />
                </span>
                <input
                  type="password"
                  required
                  disabled={!token || loading}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-xl border border-white/10 bg-black/40 py-2.5 pr-10 pl-4 text-sm text-white placeholder-muted-foreground transition focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                  dir="ltr"
                />
              </div>
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                تکرار رمز عبور جدید
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 right-3 flex items-center text-muted-foreground">
                  <Lock className="h-4 w-4" />
                </span>
                <input
                  type="password"
                  required
                  disabled={!token || loading}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-xl border border-white/10 bg-black/40 py-2.5 pr-10 pl-4 text-sm text-white placeholder-muted-foreground transition focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                  dir="ltr"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !token}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary py-3 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/25 transition hover:bg-primary/90 disabled:opacity-50"
            >
              {loading ? (
                <span>در حال ذخیره...</span>
              ) : (
                <span>تغییر رمز عبور</span>
              )}
            </button>
          </form>
        )}

        <div className="mt-8 border-t border-white/10 pt-6 text-center text-xs text-muted-foreground">
          <Link
            href="/login"
            className="font-medium text-primary transition hover:underline"
          >
            بازگشت به صفحه ورود
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-[#0a0a0a] text-white">در حال بارگذاری...</div>}>
      <ResetPasswordForm />
    </Suspense>
  );
}
