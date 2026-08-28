"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/context/auth-context";
import { api, ApiError } from "@/lib/api-client";
import { Building2, Plus, Users, Shield, Sparkles, Pencil, Trash2, X, AlertTriangle } from "lucide-react";
import toast from "react-hot-toast";

export default function OrganizationsPage() {
  const { organizations, currentOrg, setCurrentOrg, refreshOrgsAndWebsites } =
    useAuth();
  const [newOrgName, setNewOrgName] = useState("");
  const [newOrgDescription, setNewOrgDescription] = useState("");
  const [loadingCreate, setLoadingCreate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [members, setMembers] = useState<any[]>([]);
  const [loadingMembers, setLoadingMembers] = useState(false);

  // Modal States
  const [editOrgModal, setEditOrgModal] = useState<{ open: boolean; org: any; name: string; loading: boolean }>({
    open: false,
    org: null,
    name: "",
    loading: false,
  });

  const [deleteOrgModal, setDeleteOrgModal] = useState<{ open: boolean; org: any; loading: boolean }>({
    open: false,
    org: null,
    loading: false,
  });

  const [roleModal, setRoleModal] = useState<{ open: boolean; member: any; role: string; loading: boolean }>({
    open: false,
    member: null,
    role: "viewer",
    loading: false,
  });

  const [removeMemberModal, setRemoveMemberModal] = useState<{ open: boolean; member: any; loading: boolean }>({
    open: false,
    member: null,
    loading: false,
  });

  const [inviteModal, setInviteModal] = useState<{ open: boolean; email: string; role: string; loading: boolean }>({
    open: false,
    email: "",
    role: "viewer",
    loading: false,
  });

  useEffect(() => {
    if (currentOrg) {
      loadMembers(currentOrg.id);
    }
  }, [currentOrg]);

  const loadMembers = async (orgId: string) => {
    setLoadingMembers(true);
    try {
      const data = await api.get(`/organizations/${orgId}/members`);
      setMembers(data || []);
    } catch {
      setMembers([]);
    } finally {
      setLoadingMembers(false);
    }
  };

  const handleCreateOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newOrgName.trim()) return;
    setLoadingCreate(true);
    setError(null);

    try {
      const res = await api.post("/organizations", {
        name: newOrgName.trim(),
        description: newOrgDescription.trim() || undefined,
      });
      setNewOrgName("");
      setNewOrgDescription("");
      await refreshOrgsAndWebsites();
      if (res && res.id) {
        setCurrentOrg(res);
      }
      toast.success("سازمان جدید با موفقیت ایجاد شد");
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("خطا در ساخت سازمان جدید");
      }
    } finally {
      setLoadingCreate(false);
    }
  };

  const submitEditOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editOrgModal.org || !editOrgModal.name.trim()) return;
    setEditOrgModal((prev) => ({ ...prev, loading: true }));
    try {
      await api.put(`/organizations/${editOrgModal.org.id}`, { name: editOrgModal.name.trim() });
      await refreshOrgsAndWebsites();
      if (currentOrg?.id === editOrgModal.org.id) {
        setCurrentOrg({ ...editOrgModal.org, name: editOrgModal.name.trim() });
      }
      toast.success("نام سازمان با موفقیت ویرایش شد");
      setEditOrgModal({ open: false, org: null, name: "", loading: false });
    } catch (err: any) {
      toast.error(err.message || "خطا در ویرایش سازمان");
      setEditOrgModal((prev) => ({ ...prev, loading: false }));
    }
  };

  const submitDeleteOrg = async () => {
    if (!deleteOrgModal.org) return;
    setDeleteOrgModal((prev) => ({ ...prev, loading: true }));
    try {
      await api.delete(`/organizations/${deleteOrgModal.org.id}`);
      await refreshOrgsAndWebsites();
      if (currentOrg?.id === deleteOrgModal.org.id) {
        const remaining = organizations.filter((o) => o.id !== deleteOrgModal.org.id);
        setCurrentOrg(remaining.length > 0 ? remaining[0] : null);
      }
      toast.success("سازمان با موفقیت حذف شد");
      setDeleteOrgModal({ open: false, org: null, loading: false });
    } catch (err: any) {
      toast.error(err.message || "خطا در حذف سازمان");
      setDeleteOrgModal((prev) => ({ ...prev, loading: false }));
    }
  };

  const submitChangeRole = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentOrg || !roleModal.member) return;
    setRoleModal((prev) => ({ ...prev, loading: true }));
    try {
      await api.put(`/organizations/${currentOrg.id}/members/${roleModal.member.user_id}`, { role: roleModal.role });
      await loadMembers(currentOrg.id);
      toast.success("سطح دسترسی کاربر تغییر یافت");
      setRoleModal({ open: false, member: null, role: "viewer", loading: false });
    } catch (err: any) {
      toast.error(err.message || "خطا در تغییر دسترسی");
      setRoleModal((prev) => ({ ...prev, loading: false }));
    }
  };

  const submitRemoveMember = async () => {
    if (!currentOrg || !removeMemberModal.member) return;
    setRemoveMemberModal((prev) => ({ ...prev, loading: true }));
    try {
      await api.delete(`/organizations/${currentOrg.id}/members/${removeMemberModal.member.user_id}`);
      await loadMembers(currentOrg.id);
      toast.success("عضو سازمان حذف شد");
      setRemoveMemberModal({ open: false, member: null, loading: false });
    } catch (err: any) {
      toast.error(err.message || "خطا در حذف کاربر");
      setRemoveMemberModal((prev) => ({ ...prev, loading: false }));
    }
  };

  const submitInviteMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentOrg || !inviteModal.email.trim()) return;
    setInviteModal((prev) => ({ ...prev, loading: true }));
    try {
      await api.post(`/organizations/${currentOrg.id}/members`, { 
        email: inviteModal.email.trim(), 
        role: inviteModal.role 
      });
      await loadMembers(currentOrg.id);
      toast.success("عضو جدید با موفقیت به سازمان اضافه شد");
      setInviteModal({ open: false, email: "", role: "viewer", loading: false });
    } catch (err: any) {
      toast.error(err.message || "خطا در افزودن کاربر");
      setInviteModal((prev) => ({ ...prev, loading: false }));
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            مدیریت سازمان‌ها و اعضای تیم
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            ساخت سازمان‌های چندگانه، مدیریت سطح دسترسی (RBAC) و اعضای پروژه
          </p>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Two Column Layout: Orgs + New Org Form */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Organizations List */}
        <div className="rounded-2xl border border-white/10 bg-card/60 p-6 shadow-xl backdrop-blur-md lg:col-span-2">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-bold text-white">سازمان‌های شما</h2>
            <span className="rounded-full bg-primary/20 px-2.5 py-0.5 text-xs font-semibold text-primary">
              {organizations.length} سازمان
            </span>
          </div>

          <div className="space-y-3">
            {organizations.map((org) => (
              <div
                key={org.id}
                onClick={() => setCurrentOrg(org)}
                className={`flex cursor-pointer items-center justify-between rounded-xl border p-4 transition ${
                  currentOrg?.id === org.id
                    ? "border-primary bg-primary/10 shadow-lg shadow-primary/5"
                    : "border-white/10 bg-black/20 hover:bg-white/5"
                }`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`flex h-10 w-10 items-center justify-center rounded-xl ${
                      currentOrg?.id === org.id
                        ? "bg-primary text-primary-foreground"
                        : "bg-white/10 text-muted-foreground"
                    }`}
                  >
                    <Building2 className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">{org.name}</h3>
                    <p className="text-xs text-muted-foreground">
                      شناسه: {org.slug} | طرح:{" "}
                      <span className="uppercase text-emerald-400">
                        {org.plan}
                      </span>
                    </p>
                    {org.description && (
                      <p className="mt-1 text-[11px] text-muted-foreground/80 max-w-[250px] truncate" title={org.description}>
                        {org.description}
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-medium ${
                      currentOrg?.id === org.id
                        ? "bg-primary/20 text-primary"
                        : "bg-white/5 text-muted-foreground"
                    }`}
                  >
                    {currentOrg?.id === org.id ? "سازمان فعال" : "انتخاب"}
                  </span>

                  <div className="flex items-center gap-1.5">
                    {org.my_role === "owner" && (
                      <>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditOrgModal({ open: true, org, name: org.name, loading: false });
                          }}
                          className="rounded-lg bg-blue-500/10 p-2 text-blue-400 hover:bg-blue-500/20 transition"
                          title="ویرایش سازمان"
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeleteOrgModal({ open: true, org, loading: false });
                          }}
                          className="rounded-lg bg-red-500/10 p-2 text-red-400 hover:bg-red-500/20 transition"
                          title="حذف سازمان"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Create New Org Box */}
        <div className="rounded-2xl border border-white/10 bg-card/60 p-6 shadow-xl backdrop-blur-md">
          <div className="mb-4 flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <h2 className="text-base font-bold text-white">
              ایجاد سازمان جدید
            </h2>
          </div>
          <p className="mb-4 text-xs text-muted-foreground">
            هر سازمان دارای پروژه‌ها، وب‌سایت‌ها و اعضای مستقل است.
          </p>

          <form onSubmit={handleCreateOrg} className="space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                نام سازمان
              </label>
              <input
                type="text"
                required
                value={newOrgName}
                onChange={(e) => setNewOrgName(e.target.value)}
                placeholder="مثال: تیم سئو آلفا"
                className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-sm text-white placeholder-muted-foreground transition focus:border-primary focus:outline-none"
              />
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                توضیحات سازمان (اختیاری)
              </label>
              <textarea
                value={newOrgDescription}
                onChange={(e) => setNewOrgDescription(e.target.value)}
                placeholder="مثال: تیم بررسی پروژه‌های شرکتی..."
                className="w-full min-h-[80px] rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-sm text-white placeholder-muted-foreground transition focus:border-primary focus:outline-none resize-none"
              />
            </div>

            <button
              type="submit"
              disabled={loadingCreate}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary py-2.5 text-xs font-semibold text-primary-foreground shadow-md shadow-primary/20 transition hover:bg-primary/90 disabled:opacity-50"
            >
              <Plus className="h-4 w-4" />
              <span>{loadingCreate ? "در حال ایجاد..." : "ساخت سازمان"}</span>
            </button>
          </form>
        </div>
      </div>

      {/* Members Table */}
      {currentOrg && (
        <div className="rounded-2xl border border-white/10 bg-card/60 p-6 shadow-xl backdrop-blur-md">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-white">
                اعضای سازمان «{currentOrg.name}»
              </h2>
              <p className="text-xs text-muted-foreground mt-1">
                سطوح دسترسی: مالک (Owner)، مدیر (Admin)، مدیر سئو (SEO Manager)، ویرایشگر (Editor)، ناظر (Reviewer)، بیننده (Viewer)
              </p>
            </div>
            {(currentOrg.my_role === "owner" || currentOrg.my_role === "admin") && (
              <button
                onClick={() => setInviteModal({ open: true, email: "", role: "viewer", loading: false })}
                className="flex items-center gap-2 rounded-xl bg-primary/20 px-4 py-2 text-xs font-semibold text-primary transition hover:bg-primary/30"
              >
                <Plus className="h-4 w-4" />
                <span>دعوت عضو جدید</span>
              </button>
            )}
          </div>

          {loadingMembers ? (
            <div className="py-8 text-center text-xs text-muted-foreground">
              در حال بارگذاری اعضا...
            </div>
          ) : members.length === 0 ? (
            <div className="py-8 text-center text-xs text-muted-foreground">
              عضوی یافت نشد
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-white/10 text-muted-foreground">
                  <tr>
                    <th className="pb-3 text-right">کاربر</th>
                    <th className="pb-3 text-right">ایمیل</th>
                    <th className="pb-3 text-right">سطح دسترسی (Role)</th>
                    <th className="pb-3 text-right">تاریخ عضویت</th>
                    <th className="pb-3 text-right">عملیات</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {members.map((m) => (
                    <tr key={m.id} className="transition hover:bg-white/5">
                      <td className="py-3.5 text-right font-medium text-white">
                        <div className="flex items-center gap-2">
                          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/20 text-xs font-bold text-primary">
                            {m.user_name ? m.user_name.charAt(0) : "?"}
                          </div>
                          <span>{m.user_name || "کاربر ناشناس"}</span>
                        </div>
                      </td>
                      <td className="py-3.5 text-right text-muted-foreground" dir="ltr">
                        {m.user_email}
                      </td>
                      <td className="py-3.5 text-right">
                        <span className="inline-flex items-center gap-1 rounded-full bg-purple-500/10 px-2.5 py-1 text-[11px] font-semibold text-purple-400">
                          <Shield className="h-3 w-3" />
                          {m.role}
                        </span>
                      </td>
                      <td className="py-3.5 text-right text-muted-foreground" dir="ltr">
                        {m.joined_at
                          ? new Date(m.joined_at).toLocaleDateString("fa-IR")
                          : "---"}
                      </td>
                      <td className="py-3.5 text-right">
                        <div className="flex items-center gap-2">
                          {(currentOrg.my_role === "owner" || currentOrg.my_role === "admin") && m.role !== "owner" && (
                            <>
                              <button
                                onClick={() => setRoleModal({ open: true, member: m, role: m.role || "viewer", loading: false })}
                                className="rounded bg-blue-500/10 p-1.5 text-blue-400 hover:bg-blue-500/20 transition"
                                title="تغییر نقش"
                              >
                                <Pencil className="h-4 w-4" />
                              </button>
                              <button
                                onClick={() => setRemoveMemberModal({ open: true, member: m, loading: false })}
                                className="rounded bg-red-500/10 p-1.5 text-red-400 hover:bg-red-500/20 transition"
                                title="حذف کاربر"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Modal 1: Edit Org Name */}
      {editOrgModal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-white/10 bg-card p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-white">ویرایش نام سازمان</h3>
              <button onClick={() => setEditOrgModal({ open: false, org: null, name: "", loading: false })} className="text-muted-foreground hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={submitEditOrg} className="space-y-4">
              <div>
                <label className="mb-1 block text-xs text-muted-foreground">نام جدید سازمان</label>
                <input
                  type="text"
                  required
                  value={editOrgModal.name}
                  onChange={(e) => setEditOrgModal((prev) => ({ ...prev, name: e.target.value }))}
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-sm text-white focus:border-primary focus:outline-none"
                />
              </div>
              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setEditOrgModal({ open: false, org: null, name: "", loading: false })}
                  className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-muted-foreground hover:bg-white/5"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  disabled={editOrgModal.loading}
                  className="rounded-xl bg-primary px-5 py-2 text-xs font-semibold text-primary-foreground shadow-lg hover:bg-primary/90 disabled:opacity-50"
                >
                  {editOrgModal.loading ? "در حال ذخیره..." : "ذخیره تغییرات"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal 2: Delete Org Confirm */}
      {deleteOrgModal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-red-500/30 bg-card p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-red-400">
              <AlertTriangle className="h-6 w-6 shrink-0" />
              <h3 className="text-base font-bold text-white">حذف سازمان «{deleteOrgModal.org?.name}»</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              آیا از حذف این سازمان مطمئن هستید؟ با حذف سازمان، تمام پروژه‌ها و وب‌سایت‌های زیرمجموعه نیز غیرفعال یا حذف خواهند شد. این عمل غیرقابل بازگشت است.
            </p>
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setDeleteOrgModal({ open: false, org: null, loading: false })}
                className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-muted-foreground hover:bg-white/5"
              >
                انصراف
              </button>
              <button
                type="button"
                onClick={submitDeleteOrg}
                disabled={deleteOrgModal.loading}
                className="rounded-xl bg-red-600 px-5 py-2 text-xs font-semibold text-white shadow-lg hover:bg-red-500 disabled:opacity-50"
              >
                {deleteOrgModal.loading ? "در حال حذف..." : "حذف کامل سازمان"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 3: Change Member Role */}
      {roleModal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-white/10 bg-card p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-white">تغییر سطح دسترسی کاربر</h3>
              <button onClick={() => setRoleModal({ open: false, member: null, role: "viewer", loading: false })} className="text-muted-foreground hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={submitChangeRole} className="space-y-4">
              <div>
                <label className="mb-1 block text-xs text-muted-foreground">کاربر: {roleModal.member?.user_email}</label>
                <select
                  value={roleModal.role}
                  onChange={(e) => setRoleModal((prev) => ({ ...prev, role: e.target.value }))}
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-xs text-white focus:border-primary focus:outline-none"
                >
                  <option value="owner">مالک (Owner)</option>
                  <option value="admin">مدیر کل (Admin)</option>
                  <option value="seo_manager">مدیر سئو (SEO Manager)</option>
                  <option value="editor">ویرایشگر (Editor)</option>
                  <option value="reviewer">ناظر (Reviewer)</option>
                  <option value="viewer">بیننده (Viewer)</option>
                </select>
              </div>
              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setRoleModal({ open: false, member: null, role: "viewer", loading: false })}
                  className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-muted-foreground hover:bg-white/5"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  disabled={roleModal.loading}
                  className="rounded-xl bg-primary px-5 py-2 text-xs font-semibold text-primary-foreground shadow-lg hover:bg-primary/90 disabled:opacity-50"
                >
                  {roleModal.loading ? "در حال بروزرسانی..." : "ذخیره نقش جدید"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal 4: Remove Member Confirm */}
      {removeMemberModal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-red-500/30 bg-card p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-red-400">
              <AlertTriangle className="h-6 w-6 shrink-0" />
              <h3 className="text-base font-bold text-white">حذف کاربر از سازمان</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              آیا از حذف کاربر «{removeMemberModal.member?.user_email}» از سازمان اطمینان دارید؟
            </p>
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setRemoveMemberModal({ open: false, member: null, loading: false })}
                className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-muted-foreground hover:bg-white/5"
              >
                انصراف
              </button>
              <button
                type="button"
                onClick={submitRemoveMember}
                disabled={removeMemberModal.loading}
                className="rounded-xl bg-red-600 px-5 py-2 text-xs font-semibold text-white shadow-lg hover:bg-red-500 disabled:opacity-50"
              >
                {removeMemberModal.loading ? "در حال حذف..." : "حذف کاربر"}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Modal 5: Invite Member */}
      {inviteModal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-white/10 bg-card p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-white">دعوت عضو جدید</h3>
              <button onClick={() => setInviteModal({ open: false, email: "", role: "viewer", loading: false })} className="text-muted-foreground hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={submitInviteMember} className="space-y-4">
              <div>
                <label className="mb-1 block text-xs text-muted-foreground">ایمیل هم‌تیمی</label>
                <input
                  type="email"
                  required
                  placeholder="name@example.com"
                  dir="ltr"
                  value={inviteModal.email}
                  onChange={(e) => setInviteModal((prev) => ({ ...prev, email: e.target.value }))}
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-sm text-white focus:border-primary focus:outline-none"
                />
                <p className="mt-1.5 text-[10px] text-muted-foreground">
                  کاربر مورد نظر باید ابتدا در سیستم ثبت‌نام کرده باشد.
                </p>
              </div>
              <div>
                <label className="mb-1 block text-xs text-muted-foreground">سطح دسترسی</label>
                <select
                  value={inviteModal.role}
                  onChange={(e) => setInviteModal((prev) => ({ ...prev, role: e.target.value }))}
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-xs text-white focus:border-primary focus:outline-none"
                >
                  <option value="owner">مالک (Owner)</option>
                  <option value="admin">مدیر کل (Admin)</option>
                  <option value="seo_manager">مدیر سئو (SEO Manager)</option>
                  <option value="editor">ویرایشگر (Editor)</option>
                  <option value="reviewer">ناظر (Reviewer)</option>
                  <option value="viewer">بیننده (Viewer)</option>
                </select>
              </div>
              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setInviteModal({ open: false, email: "", role: "viewer", loading: false })}
                  className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-muted-foreground hover:bg-white/5"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  disabled={inviteModal.loading}
                  className="rounded-xl bg-primary px-5 py-2 text-xs font-semibold text-primary-foreground shadow-lg hover:bg-primary/90 disabled:opacity-50"
                >
                  {inviteModal.loading ? "در حال دعوت..." : "دعوت و افزودن"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
