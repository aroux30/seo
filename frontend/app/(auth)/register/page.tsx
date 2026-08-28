"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/auth-context";
import { api, ApiError } from "@/lib/api-client";
import { Lock, Mail, User, Building, ArrowLeft, Sparkles } from "lucide-react";

export default function RegisterPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [orgName, setOrgName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      // 1. Register User
      await api.post("/auth/register", {
        email,
        password,
        full_name: fullName,
      });

      // 2. Login
      const res = await api.post<{
        access_token: string;
        refresh_token: string;
      }>("/auth/login", {
        email,
        password,
      });

      // 3. Store tokens in context
      await login(res.access_token, res.refresh_token);

      // 4. Create initial Organization if orgName was filled
      if (orgName.trim()) {
        await api.post("/organizations", {
          name: orgName.trim(),
        });
      }

      router.push("/");
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("خطا در ثبت‌نام. لطفاً مجدداً تلاش کنید.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4 py-8">
      {/* Background Subtle Gradient Glows */}
      <div className="pointer-events-none absolute -top-40 -left-40 h-96 w-96 rounded-full bg-primary/20 blur-[120px]" />
      <div className="pointer-events-none absolute -bottom-40 -right-40 h-96 w-96 rounded-full bg-purple-600/15 blur-[120px]" />

      <div className="relative z-10 w-full max-w-md rounded-2xl border border-white/10 bg-card/60 p-8 shadow-2xl backdrop-blur-xl">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/20 text-primary shadow-inner">
            <Sparkles className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            ثبت‌نام در AI SEO OS
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            ایجاد حساب کاربری و سازمان برای مدیریت هوشمند سئو
          </p>
        </div>

        {error && (
          <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
              نام و نام خانوادگی
            </label>
            <div className="relative">
              <span className="absolute inset-y-0 right-3 flex items-center text-muted-foreground">
                <User className="h-4 w-4" />
              </span>
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="علی رضایی"
                className="w-full rounded-xl border border-white/10 bg-black/40 py-2.5 pr-10 pl-4 text-sm text-white placeholder-muted-foreground transition focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
              پست الکترونیک (ایمیل)
            </label>
            <div className="relative">
              <span className="absolute inset-y-0 right-3 flex items-center text-muted-foreground">
                <Mail className="h-4 w-4" />
              </span>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                className="w-full rounded-xl border border-white/10 bg-black/40 py-2.5 pr-10 pl-4 text-sm text-white placeholder-muted-foreground transition focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                dir="ltr"
              />
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
              رمز عبور (حداقل ۶ کاراکتر)
            </label>
            <div className="relative">
              <span className="absolute inset-y-0 right-3 flex items-center text-muted-foreground">
                <Lock className="h-4 w-4" />
              </span>
              <input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full rounded-xl border border-white/10 bg-black/40 py-2.5 pr-10 pl-4 text-sm text-white placeholder-muted-foreground transition focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                dir="ltr"
              />
            </div>
          </div>

          <div className="pt-2">
            <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
              نام سازمان یا شرکت شما (اختیاری)
            </label>
            <div className="relative">
              <span className="absolute inset-y-0 right-3 flex items-center text-muted-foreground">
                <Building className="h-4 w-4" />
              </span>
              <input
                type="text"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                placeholder="مثال: دیجی سئو یا سازمان من"
                className="w-full rounded-xl border border-white/10 bg-black/40 py-2.5 pr-10 pl-4 text-sm text-white placeholder-muted-foreground transition focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-primary py-3 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/25 transition hover:bg-primary/90 disabled:opacity-50"
          >
            {loading ? (
              <span>در حال ایجاد حساب...</span>
            ) : (
              <>
                <span>ایجاد حساب و ورود</span>
                <ArrowLeft className="h-4 w-4" />
              </>
            )}
          </button>
        </form>

        <div className="mt-6 border-t border-white/10 pt-6 text-center text-xs text-muted-foreground">
          قبلاً ثبت‌نام کرده‌اید؟{" "}
          <Link
            href="/login"
            className="font-medium text-primary transition hover:underline"
          >
            ورود به سیستم
          </Link>
        </div>
      </div>
    </div>
  );
}
