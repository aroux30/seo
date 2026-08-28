"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/context/auth-context";
import NotificationBell from "@/components/notification-bell";
import {
  LayoutDashboard,
  Globe,
  Building2,
  FolderKanban,
  Settings,
  LogOut,
  ChevronDown,
  Sparkles,
  Menu,
  X,
  BarChart2,
  KeyRound,
  Plug,
  Lightbulb,
  ShieldAlert,
  ShieldCheck,
  Activity,
  FileBarChart2,
  Gauge,
} from "lucide-react";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const {
    user,
    organizations,
    currentOrg,
    setCurrentOrg,
    websites,
    currentWebsite,
    setCurrentWebsite,
    logout,
    loading,
  } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [orgDropdownOpen, setOrgDropdownOpen] = useState(false);
  const [siteDropdownOpen, setSiteDropdownOpen] = useState(false);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-xs text-muted-foreground">در حال بارگذاری سیستم...</p>
        </div>
      </div>
    );
  }

  const navigation = [
    { name: "داشبورد مرکزی", href: "/", icon: LayoutDashboard },
    { name: "وب‌سایت‌ها", href: "/websites", icon: Globe },
    ...(currentWebsite
      ? [
          {
            name: "تحلیل سرچ کنسول",
            href: `/websites/${currentWebsite.id}/analytics`,
            icon: BarChart2,
          },
          {
            name: "کلمات کلیدی هدف",
            href: `/websites/${currentWebsite.id}/keywords`,
            icon: KeyRound,
          },
          {
            name: "فرصت‌های رشد سئو",
            href: `/websites/${currentWebsite.id}/opportunities`,
            icon: Lightbulb,
          },
          {
            name: "اتصالات و وردپرس",
            href: `/websites/${currentWebsite.id}/integrations`,
            icon: Plug,
          },
        ]
      : []),
    { name: "هشدارهای سئو", href: "/alerts", icon: ShieldAlert },
    { name: "صف تأییدها", href: "/approvals", icon: ShieldCheck },
    { name: "گزارش‌ها", href: "/reports", icon: FileBarChart2 },
    { name: "شاخص‌های عملکرد", href: "/kpi", icon: Gauge },
    { name: "فعالیت عامل‌های AI", href: "/agent-activity", icon: Activity },
    { name: "سازمان‌ها و اعضا", href: "/organizations", icon: Building2 },
    { name: "پروژه‌ها", href: "/projects", icon: FolderKanban },
    { name: "تنظیمات", href: "/settings", icon: Settings },
  ];

  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar - RTL on Right */}
      <aside
        className={`fixed inset-y-0 right-0 z-40 flex w-64 flex-col border-l border-white/10 bg-card/80 backdrop-blur-xl transition-transform duration-300 md:translate-x-0 ${
          mobileMenuOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Logo Header */}
        <div className="flex h-16 items-center justify-between border-b border-white/10 px-6">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/20 text-primary shadow-inner">
              <Sparkles className="h-5 w-5" />
            </div>
            <span className="text-base font-bold tracking-tight text-white">
              AI SEO OS
            </span>
          </Link>
          <button
            onClick={() => setMobileMenuOpen(false)}
            className="rounded-lg p-1 text-muted-foreground hover:bg-white/5 md:hidden"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Organization Selector */}
        <div className="relative border-b border-white/10 p-4">
          <button
            onClick={() => {
              setOrgDropdownOpen(!orgDropdownOpen);
              setSiteDropdownOpen(false);
            }}
            className="flex w-full items-center justify-between rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-xs text-white transition hover:bg-white/5"
          >
            <div className="flex items-center gap-2 overflow-hidden">
              <Building2 className="h-4 w-4 shrink-0 text-primary" />
              <span className="truncate font-medium">
                {currentOrg ? currentOrg.name : "بدون سازمان فعال"}
              </span>
            </div>
            <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          </button>

          {orgDropdownOpen && (
            <div className="absolute top-14 right-4 left-4 z-50 rounded-xl border border-white/10 bg-card p-1 shadow-xl">
              <div className="px-2 py-1 text-[10px] font-semibold text-muted-foreground">
                انتخاب سازمان فعال
              </div>
              {organizations.map((org) => (
                <button
                  key={org.id}
                  onClick={() => {
                    setCurrentOrg(org);
                    setOrgDropdownOpen(false);
                  }}
                  className={`flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-xs transition ${
                    currentOrg?.id === org.id
                      ? "bg-primary/20 text-primary font-medium"
                      : "text-white hover:bg-white/5"
                  }`}
                >
                  <span className="truncate">{org.name}</span>
                  <span className="rounded-md bg-white/5 px-1.5 py-0.5 text-[10px] uppercase">
                    {org.plan}
                  </span>
                </button>
              ))}
              <Link
                href="/organizations"
                onClick={() => setOrgDropdownOpen(false)}
                className="mt-1 block w-full rounded-lg bg-white/5 px-2.5 py-1.5 text-center text-[11px] text-primary transition hover:bg-white/10"
              >
                + مدیریت یا افزودن سازمان
              </Link>
            </div>
          )}
        </div>

        {/* Website Selector */}
        {currentOrg && (
          <div className="relative border-b border-white/10 px-4 py-3">
            <button
              onClick={() => {
                setSiteDropdownOpen(!siteDropdownOpen);
                setOrgDropdownOpen(false);
              }}
              className="flex w-full items-center justify-between rounded-xl border border-white/10 bg-black/20 px-3 py-1.5 text-xs text-muted-foreground transition hover:text-white"
            >
              <div className="flex items-center gap-2 overflow-hidden">
                <Globe className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
                <span className="truncate">
                  {currentWebsite ? currentWebsite.domain : "انتخاب وب‌سایت"}
                </span>
              </div>
              <ChevronDown className="h-3 w-3 shrink-0" />
            </button>

            {siteDropdownOpen && (
              <div className="absolute top-12 right-4 left-4 z-50 rounded-xl border border-white/10 bg-card p-1 shadow-xl">
                <div className="px-2 py-1 text-[10px] font-semibold text-muted-foreground">
                  انتخاب وب‌سایت
                </div>
                {websites.length === 0 ? (
                  <div className="px-2 py-2 text-center text-xs text-muted-foreground">
                    وب‌سایتی ثبت نشده است
                  </div>
                ) : (
                  websites.map((site) => (
                    <button
                      key={site.id}
                      onClick={() => {
                        setCurrentWebsite(site);
                        setSiteDropdownOpen(false);
                      }}
                      className={`flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-xs transition ${
                        currentWebsite?.id === site.id
                          ? "bg-emerald-500/20 text-emerald-400 font-medium"
                          : "text-white hover:bg-white/5"
                      }`}
                    >
                      <span className="truncate">{site.domain}</span>
                    </button>
                  ))
                )}
                <Link
                  href="/websites"
                  onClick={() => setSiteDropdownOpen(false)}
                  className="mt-1 block w-full rounded-lg bg-white/5 px-2 py-1 text-center text-[11px] text-emerald-400 transition hover:bg-white/10"
                >
                  + افزودن وب‌سایت جدید
                </Link>
              </div>
            )}
          </div>
        )}

        {/* Navigation Links */}
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {navigation.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition ${
                  isActive
                    ? "bg-primary text-primary-foreground shadow-md shadow-primary/20"
                    : "text-muted-foreground hover:bg-white/5 hover:text-white"
                }`}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>

        {/* User Footer */}
        <div className="relative border-t border-white/10 p-4">
          <button
            onClick={() => setUserDropdownOpen(!userDropdownOpen)}
            className="flex w-full items-center justify-between rounded-xl p-2 transition hover:bg-white/5"
          >
            <div className="flex items-center gap-2.5 overflow-hidden">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/20 text-xs font-bold text-primary">
                {user.full_name.charAt(0)}
              </div>
              <div className="overflow-hidden text-right">
                <p className="truncate text-xs font-semibold text-white">
                  {user.full_name}
                </p>
                <p className="truncate text-[10px] text-muted-foreground">
                  {user.email}
                </p>
              </div>
            </div>
          </button>

          {userDropdownOpen && (
            <div className="absolute bottom-16 right-4 left-4 z-50 rounded-xl border border-white/10 bg-card p-1 shadow-xl">
              <Link
                href="/settings"
                onClick={() => setUserDropdownOpen(false)}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-white transition hover:bg-white/5"
              >
                <Settings className="h-4 w-4 text-muted-foreground" />
                <span>تنظیمات پروفایل</span>
              </Link>
              <button
                onClick={logout}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-red-400 transition hover:bg-red-500/10"
              >
                <LogOut className="h-4 w-4" />
                <span>خروج از حساب</span>
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col md:mr-64">
        {/* Header */}
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-white/10 bg-background/80 px-6 backdrop-blur-md">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="rounded-lg p-2 text-muted-foreground hover:bg-white/5 md:hidden"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span>{currentOrg ? currentOrg.name : "بدون سازمان"}</span>
              {currentWebsite && (
                <>
                  <span>/</span>
                  <span className="font-semibold text-emerald-400">
                    {currentWebsite.domain}
                  </span>
                </>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <NotificationBell />
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
