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
} from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api-client";
import toast from "react-hot-toast";

export default function SettingsPage() {
  const { user, currentOrg } = useAuth();

  // Profile Form
  const [profileForm, setProfileForm] = useState({ full_name: "" });
  const [profileLoading, setProfileLoading] = useState(false);

  // Password Form
  const [passwordForm, setPasswordForm] = useState({ current_password: "", new_password: "", confirm_password: "" });
  const [passwordLoading, setPasswordLoading] = useState(false);


  useEffect(() => {
    if (user) setProfileForm({ full_name: user.full_name || "" });

  }, [user, currentOrg]);

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
        new_password: passwordForm.new_password
      });
      toast.success("رمز عبور با موفقیت تغییر یافت");
      setPasswordForm({ current_password: "", new_password: "", confirm_password: "" });
    } catch (err: any) {
      toast.error(err.message || "خطا در تغییر رمز عبور");
    } finally {
      setPasswordLoading(false);
    }
  };


  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">
          تنظیمات سیستم و پروفایل کاربری
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          پیکربندی حساب، ارائه‌دهندگان هوش مصنوعی، و کلیدهای اتصال سرویس‌ها
        </p>
      </div>

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
                  onChange={(e) => setProfileForm(p => ({ ...p, full_name: e.target.value }))}
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
                  onChange={(e) => setPasswordForm(p => ({ ...p, current_password: e.target.value }))}
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
                    onChange={(e) => setPasswordForm(p => ({ ...p, new_password: e.target.value }))}
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
                    onChange={(e) => setPasswordForm(p => ({ ...p, confirm_password: e.target.value }))}
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
              اتصال Google Search Console (پیش‌نیاز فاز ۲)
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
