"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api-client";
import { Bell, CheckCircle2, RefreshCw, AlertTriangle, Info, X } from "lucide-react";

const POLL_INTERVAL_MS = 45000;

interface NotificationItem {
  id: string;
  event_type: string;
  title: string;
  body?: string | null;
  action_url?: string | null;
  read_at?: string | null;
  created_at: string;
  channel?: string | null;
  status?: string | null;
}

/** Persian relative time. Falls back to an absolute fa-IR date for older items. */
function formatRelativeFa(iso?: string | null): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diffSec = Math.floor((Date.now() - then) / 1000);
  if (diffSec < 60) return "چند لحظه پیش";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} دقیقه پیش`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} ساعت پیش`;
  if (diffSec < 604800) return `${Math.floor(diffSec / 86400)} روز پیش`;
  return new Date(iso).toLocaleDateString("fa-IR");
}

function eventIcon(eventType: string) {
  if (eventType.includes("critical") || eventType.includes("failure")) {
    return <AlertTriangle className="h-3.5 w-3.5 text-rose-400" />;
  }
  if (eventType.includes("alert") || eventType.includes("drop")) {
    return <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />;
  }
  if (eventType.includes("opportunity")) {
    return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />;
  }
  return <Info className="h-3.5 w-3.5 text-blue-400" />;
}

export default function NotificationBell() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const loadUnreadCount = useCallback(async () => {
    try {
      const res = await api.get<{ unread: number }>("/notifications/unread-count");
      setUnread(typeof res?.unread === "number" ? res.unread : 0);
    } catch {
      // A failed poll must not break the header. Keep the last known count.
    }
  }, []);

  const loadList = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<NotificationItem[]>("/notifications?limit=15");
      setItems(Array.isArray(res) ? res : []);
    } catch {
      setError("خطا در دریافت اعلان‌ها");
    } finally {
      setLoading(false);
    }
  }, []);

  // Poll the unread badge. The interval is cleared on unmount so a remounted
  // header (org switch, route change) never stacks up timers.
  useEffect(() => {
    let cancelled = false;

    const tick = () => {
      if (!cancelled) loadUnreadCount();
    };

    tick();
    const timer = setInterval(tick, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [loadUnreadCount]);

  // Close on outside click / Escape.
  useEffect(() => {
    if (!open) return;

    const onPointerDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const handleToggle = () => {
    const next = !open;
    setOpen(next);
    if (next) loadList();
  };

  const markRead = async (ids: string[] | null) => {
    const previousItems = items;
    const previousUnread = unread;
    const nowIso = new Date().toISOString();

    // Optimistic: flip the affected rows to read, then reconcile with the server.
    setItems((prev) =>
      prev.map((n) =>
        ids === null || ids.includes(n.id) ? { ...n, read_at: n.read_at || nowIso } : n
      )
    );
    setUnread((prev) =>
      ids === null
        ? 0
        : Math.max(0, prev - previousItems.filter((n) => ids.includes(n.id) && !n.read_at).length)
    );

    try {
      await api.post("/notifications/mark-read", { notification_ids: ids });
      await loadUnreadCount();
    } catch {
      setItems(previousItems);
      setUnread(previousUnread);
      setError("خطا در علامت‌گذاری اعلان‌ها به‌عنوان خوانده‌شده");
    }
  };

  const handleItemClick = async (item: NotificationItem) => {
    setOpen(false);
    if (!item.read_at) {
      await markRead([item.id]);
    }
    if (item.action_url) {
      router.push(item.action_url);
    }
  };

  return (
    <div className="relative" ref={containerRef}>
      <button
        onClick={handleToggle}
        aria-label="اعلان‌ها"
        aria-expanded={open}
        className="relative rounded-xl border border-white/10 bg-card p-2 text-muted-foreground transition hover:text-white"
      >
        <Bell className="h-4 w-4" />
        {unread > 0 && (
          <span className="absolute -top-1.5 -left-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[9px] font-bold text-primary-foreground shadow-md">
            {unread > 99 ? "۹۹+" : unread.toLocaleString("fa-IR")}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute top-12 left-0 z-50 w-80 rounded-2xl border border-white/10 bg-card p-4 shadow-2xl backdrop-blur-xl">
          <div className="mb-3 flex items-center justify-between border-b border-white/10 pb-3">
            <h3 className="text-sm font-bold text-white">
              اعلان‌ها
              {unread > 0 && (
                <span className="mr-1.5 text-[10px] font-medium text-primary">
                  ({unread.toLocaleString("fa-IR")} خوانده‌نشده)
                </span>
              )}
            </h3>
            <div className="flex items-center gap-2">
              {unread > 0 && (
                <button
                  onClick={() => markRead(null)}
                  className="text-xs text-primary transition hover:text-primary/80"
                >
                  خواندن همه
                </button>
              )}
              <button
                onClick={() => setOpen(false)}
                aria-label="بستن"
                className="rounded-lg p-0.5 text-muted-foreground transition hover:bg-white/10 hover:text-white"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          {error && (
            <div className="mb-3 flex items-center justify-between gap-2 rounded-xl border border-rose-500/20 bg-rose-500/10 p-2.5 text-[11px] text-rose-300">
              <span>{error}</span>
              <button
                onClick={loadList}
                className="inline-flex items-center gap-1 font-semibold text-rose-200 hover:underline"
              >
                <RefreshCw className="h-3 w-3" />
                تلاش مجدد
              </button>
            </div>
          )}

          <div className="max-h-80 overflow-y-auto">
            {loading ? (
              <div className="flex flex-col gap-2">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="animate-pulse rounded-xl bg-white/5 p-3">
                    <div className="h-2.5 w-2/3 rounded bg-white/10" />
                    <div className="mt-2 h-2 w-full rounded bg-white/[0.07]" />
                    <div className="mt-2 h-2 w-1/3 rounded bg-white/[0.05]" />
                  </div>
                ))}
              </div>
            ) : items.length === 0 ? (
              <div className="py-6 text-center">
                <Bell className="mx-auto h-8 w-8 text-muted-foreground/40" />
                <p className="mt-2 text-xs font-semibold text-white">اعلانی وجود ندارد</p>
                <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                  به‌محض ثبت افت ترافیک، هشدار سئو یا کشف فرصت جدید، اطلاع‌رسانی همین‌جا نمایش داده
                  می‌شود.
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {items.map((n) => (
                  <button
                    key={n.id}
                    onClick={() => handleItemClick(n)}
                    className={`w-full rounded-xl p-3 text-right transition hover:bg-white/10 ${
                      n.read_at ? "bg-white/[0.02]" : "bg-white/5"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-1.5">
                        {eventIcon(n.event_type)}
                        <p
                          className={`text-xs ${
                            n.read_at ? "font-medium text-muted-foreground" : "font-semibold text-white"
                          }`}
                        >
                          {n.title}
                        </p>
                      </div>
                      {!n.read_at && (
                        <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                      )}
                    </div>
                    {n.body && (
                      <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">
                        {n.body}
                      </p>
                    )}
                    <span className="mt-2 block text-[10px] text-muted-foreground/60">
                      {formatRelativeFa(n.created_at)}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="mt-3 flex items-center justify-between border-t border-white/10 pt-3">
            <Link
              href="/alerts"
              onClick={() => setOpen(false)}
              className="text-xs text-primary transition hover:underline"
            >
              مشاهده همه هشدارها
            </Link>
            <Link
              href="/settings"
              onClick={() => setOpen(false)}
              className="text-xs text-muted-foreground transition hover:text-white"
            >
              تنظیمات اعلان‌ها
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
