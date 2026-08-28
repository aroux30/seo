"use client";

/**
 * Styled dark dropdown replacing the native <select>.
 *
 * Native selects render with the OS light theme (grey/white popup) and clash
 * with the panel's dark UI; they also cannot be styled. This component mimics
 * the app's other popovers: slate-900 panel, white/10 border, rounded-xl,
 * closes on outside click / Escape, check mark on the active option.
 *
 * Props mirror <select>: value + onChange(value) + options [{value, label}].
 */

import React, { useEffect, useRef, useState } from "react";
import { Check, ChevronDown } from "lucide-react";

export interface SelectOption {
  value: string;
  label: string;
}

interface StyledSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  className?: string;
  disabled?: boolean;
}

export function StyledSelect({
  value,
  onChange,
  options,
  placeholder = "انتخاب کنید",
  className = "",
  disabled = false,
}: StyledSelectProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const current = options.find((o) => o.value === value);

  return (
    <div ref={ref} className={`relative ${className}`}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 rounded-xl border border-white/10 bg-black/30 px-3.5 py-2.5 text-sm text-white transition hover:border-white/25 focus:outline-none focus:border-indigo-500/60 disabled:opacity-50"
      >
        <span className={current ? "" : "text-muted-foreground"}>
          {current ? current.label : placeholder}
        </span>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="absolute z-50 mt-1.5 w-full overflow-hidden rounded-xl border border-white/10 bg-slate-900 shadow-2xl shadow-black/50">
          <div className="max-h-64 overflow-y-auto p-1">
            {options.map((opt) => {
              const active = opt.value === value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => {
                    onChange(opt.value);
                    setOpen(false);
                  }}
                  className={`flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-right text-sm transition ${
                    active
                      ? "bg-indigo-500/15 text-indigo-300"
                      : "text-slate-200 hover:bg-white/10 hover:text-white"
                  }`}
                >
                  <span className="min-w-0 truncate">{opt.label}</span>
                  {active && <Check className="h-4 w-4 shrink-0" />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
