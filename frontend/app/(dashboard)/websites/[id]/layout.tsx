"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useParams } from "next/navigation";
import { useAuth } from "@/context/auth-context";
import {
  Globe,
  BarChart2,
  KeyRound,
  Plug,
  ExternalLink,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  FileText,
  Zap,
  Settings,
  Lightbulb,
  Link2,
  FolderTree,
  CalendarDays,
} from "lucide-react";

export default function WebsiteWorkspaceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const params = useParams();
  const websiteId = params.id as string;
  const pathname = usePathname();
  const { organizations, currentOrg, setCurrentOrg, websites, currentWebsite, setCurrentWebsite } = useAuth();

  const site = websites.find((w) => w.id === websiteId) || currentWebsite;

  useEffect(() => {
    if (site) {
      if (site.id !== currentWebsite?.id) {
        setCurrentWebsite(site);
      }
      if (site.organization_id && site.organization_id !== currentOrg?.id) {
        const targetOrg = organizations.find((o) => o.id === site.organization_id);
        if (targetOrg) {
          setCurrentOrg(targetOrg);
        } else {
          localStorage.setItem("current_org_id", site.organization_id);
        }
      }
    }
  }, [site, currentWebsite, currentOrg, organizations]);

  const navTabs = [
    {
      name: "تحلیل سرچ کنسول",
      href: `/websites/${websiteId}/analytics`,
      icon: BarChart2,
    },
    {
      name: "کلمات کلیدی هدف",
      href: `/websites/${websiteId}/keywords`,
      icon: KeyRound,
    },
    {
      name: "حسابرسی فنی سایت",
      href: `/websites/${websiteId}/audits`,
      icon: ShieldCheck,
    },
    {
      name: "فرصت‌های رشد سئو",
      href: `/websites/${websiteId}/opportunities`,
      icon: Lightbulb,
    },
    {
      name: "استراتژی هوشمند AI",
      href: `/websites/${websiteId}/strategies`,
      icon: Sparkles,
    },
    {
      name: "ساختار و دسته‌ها",
      href: `/websites/${websiteId}/categories`,
      icon: FolderTree,
    },
    {
      name: "تقویم محتوا",
      href: `/websites/${websiteId}/calendar`,
      icon: CalendarDays,
    },
    {
      name: "تولید محتوا و پیلار",
      href: `/websites/${websiteId}/content`,
      icon: FileText,
    },
    {
      name: "لینک‌سازی داخلی",
      href: `/websites/${websiteId}/internal-links`,
      icon: Link2,
    },
    {
      name: "اتوماسیون‌های n8n",
      href: `/websites/${websiteId}/automations`,
      icon: Zap,
    },
    {
      name: "اتصالات و وردپرس",
      href: `/websites/${websiteId}/integrations`,
      icon: Plug,
    },
    {
      name: "تنظیمات سایت",
      href: `/websites/${websiteId}/settings`,
      icon: Settings,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Website Top Banner */}
      <div className="rounded-2xl border border-white/10 bg-card/60 p-6 shadow-xl backdrop-blur-md">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div className="flex items-center gap-4">
            <Link
              href="/websites"
              className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-black/20 text-muted-foreground transition hover:text-white"
              title="بازگشت به لیست وب‌سایت‌ها"
            >
              <ArrowRight className="h-5 w-5" />
            </Link>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold text-white">
                  {site ? site.name : "در حال بارگذاری وب‌سایت..."}
                </h1>
                <span className="rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-400" dir="ltr">
                  {site ? site.domain : ""}
                </span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                مرکز فرماندهی سئو، مدیریت محتوا و اتوماسیون اختصاصی این دامنه
              </p>
            </div>
          </div>

          {site && (
            <div className="flex items-center gap-3">
              <span className="rounded-lg bg-purple-500/15 px-3 py-1.5 text-xs font-semibold text-purple-400">
                حالت:{" "}
                {site.automation_mode === "ai_assist"
                  ? "دستیار هوشمند (AI Assist)"
                  : site.automation_mode === "autopilot"
                  ? "خودکار (Autopilot)"
                  : "دستی (Manual)"}
              </span>
              <a
                href={site.base_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3.5 py-2 text-xs font-medium text-white transition hover:bg-white/10"
              >
                <span>مشاهده سایت</span>
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </div>
          )}
        </div>

        {/* Workspace Sub-navigation Tabs */}
        <div className="mt-6 flex flex-wrap gap-2 border-t border-white/10 pt-4">
          {navTabs.map((tab) => {
            const isActive = pathname.startsWith(tab.href);
            const Icon = tab.icon;
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold transition ${
                  isActive
                    ? "bg-primary text-primary-foreground shadow-md shadow-primary/20"
                    : "text-muted-foreground hover:bg-white/5 hover:text-white"
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{tab.name}</span>
              </Link>
            );
          })}
        </div>
      </div>

      {/* Child Content */}
      <div>{children}</div>
    </div>
  );
}
