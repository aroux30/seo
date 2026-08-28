'use client';

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import toast from 'react-hot-toast';
import { api } from '@/lib/api-client';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import {
  Zap,
  Play,
  Plus,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ExternalLink,
  Activity,
  Layers,
  Settings,
  Power,
  X,
  FileCode,
  RefreshCw,
  TrendingUp,
  Trash2,
} from 'lucide-react';

interface AutomationTemplate {
  key: string;
  name: string;
  description: string;
  category: string;
  default_trigger: string;
  default_cron: string;
  sample_webhook_url: string;
  parameters_schema: { name: string; label: string; default: any }[];
}

interface AutomationWorkflow {
  id: string;
  name: string;
  description?: string;
  template_key?: string;
  trigger_type: string;
  cron_expression?: string;
  n8n_webhook_url: string;
  is_active: boolean;
  last_run_at?: string;
  last_run_status?: string;
  created_at: string;
}

interface AutomationLog {
  id: string;
  workflow_id: string;
  status: string;
  execution_time_ms?: number;
  payload_json: any;
  result_json: any;
  error_message?: string;
  created_at: string;
}

export default function AutomationsHubPage() {
  const params = useParams();
  const websiteId = params.id as string;

  const [activeTab, setActiveTab] = useState<'workflows' | 'templates' | 'logs'>('workflows');
  const [workflows, setWorkflows] = useState<AutomationWorkflow[]>([]);
  const [templates, setTemplates] = useState<AutomationTemplate[]>([]);
  const [logs, setLogs] = useState<AutomationLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Modal State
  const [showModal, setShowModal] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<AutomationTemplate | null>(null);
  const [customName, setCustomName] = useState('');
  const [customWebhookUrl, setCustomWebhookUrl] = useState('');
  const [customCron, setCustomCron] = useState('0 9 * * 1');
  const [submitting, setSubmitting] = useState(false);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<AutomationWorkflow | null>(null);

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [websiteId]);

  const fetchData = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [wfData, tmplData, logData] = await Promise.all([
        api.get(`/automations/workflows/${websiteId}`),
        api.get(`/automations/templates`),
        api.get(`/automations/logs/${websiteId}`),
      ]);
      setWorkflows(wfData || []);
      setTemplates(tmplData || []);
      setLogs(logData || []);
    } catch (err) {
      console.error('Error fetching automations data:', err);
      setLoadError('بارگذاری مرکز اتوماسیون ناموفق بود. اتصال خود را بررسی کنید.');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateWorkflow = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customName || !customWebhookUrl) return;
    setSubmitting(true);
    try {
      await api.post(`/automations/workflows/${websiteId}`, {
        name: customName,
        n8n_webhook_url: customWebhookUrl,
        description: selectedTemplate ? selectedTemplate.description : 'اتوماسیون اختصاصی سئو n8n',
        template_key: selectedTemplate ? selectedTemplate.key : undefined,
        trigger_type: selectedTemplate ? selectedTemplate.default_trigger : 'cron',
        cron_expression: customCron || undefined,
        is_active: true,
      });
      toast.success('اتوماسیون ثبت و فعال شد.');
      setShowModal(false);
      setCustomName('');
      setCustomWebhookUrl('');
      setSelectedTemplate(null);
      await fetchData();
      setActiveTab('workflows');
    } catch (err) {
      console.error('Error creating workflow:', err);
      toast.error('ثبت اتوماسیون ناموفق بود. آدرس وب‌هوک را بررسی کنید.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleActive = async (workflowId: string, currentStatus: boolean) => {
    try {
      await api.patch(`/automations/workflows/detail/${workflowId}/toggle`, {
        is_active: !currentStatus,
      });
      toast.success(!currentStatus ? 'اتوماسیون فعال شد.' : 'اتوماسیون غیرفعال شد.');
      await fetchData();
    } catch (err) {
      console.error('Error toggling workflow:', err);
      toast.error('تغییر وضعیت اتوماسیون ناموفق بود.');
    }
  };

  const handleRunNow = async (workflowId: string) => {
    setRunningId(workflowId);
    try {
      // The endpoint always returns 201 with an AutomationLog: a webhook that
      // answers 4xx/5xx is still a *completed* run whose outcome lives in the
      // log, so the toast must read the log, not the HTTP status.
      const log = await api.post<{ status: string; error_message?: string }>(
        `/automations/workflows/detail/${workflowId}/run`
      );
      if (log && log.status === 'success') {
        toast.success(`اجرا موفق بود (${log.error_message || 'پاسخ معتبر از n8n'}).`);
      } else {
        toast.error(`اجرا ناموفق بود: ${log?.error_message || 'وب‌هوک پاسخ معتبر نداد.'}`);
      }
      await fetchData();
    } catch (err) {
      console.error('Error running workflow:', err);
      toast.error('اجرای اتوماسیون ناموفق بود.');
    } finally {
      setRunningId(null);
    }
  };

  const handleDeleteWorkflow = async () => {
    if (!pendingDelete) return;
    const wf = pendingDelete;
    setDeletingId(wf.id);
    try {
      await api.delete(`/automations/workflows/detail/${wf.id}`);
      toast.success('اتوماسیون حذف شد.');
      setPendingDelete(null);
      await fetchData();
    } catch (err) {
      console.error('Error deleting workflow:', err);
      toast.error('حذف اتوماسیون ناموفق بود.');
    } finally {
      setDeletingId(null);
    }
  };

  const getStatusBadge = (status?: string) => {
    switch (status) {
      case 'success':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3.5 h-3.5" />
            موفق (Success)
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20">
            <AlertTriangle className="w-3.5 h-3.5" />
            خطا در اجرا
          </span>
        );
      case 'running':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20 animate-pulse">
            <Clock className="w-3.5 h-3.5" />
            در حال اجرا...
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-500/10 text-slate-400 border border-slate-500/20">
            اجرا نشده
          </span>
        );
    }
  };

  return (
    <div className="space-y-6" dir="rtl">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-slate-900/60 p-6 rounded-2xl border border-slate-800 backdrop-blur-xl">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Zap className="w-7 h-7 text-amber-400" />
            مرکز اتوماسیون‌ها و ورک‌فلوهای n8n (SEO Automation OS)
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            اتصال هوشمند رویدادهای سئو و حسابرسی‌ها به n8n برای ارسال هشدار تلگرام، بررسی لینک‌های شکسته و گزارش‌های خودکار
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              setSelectedTemplate(null);
              setCustomName('');
              setCustomWebhookUrl('');
              setShowModal(true);
            }}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 text-white text-sm font-medium transition-all shadow-lg shadow-amber-500/20"
          >
            <Plus className="w-4 h-4" />
            افزودن اتوماسیون n8n
          </button>
        </div>
      </div>

      {/* Load failure banner */}
      {loadError && (
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 justify-between bg-red-500/10 border border-red-500/30 rounded-2xl p-4">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />
            <span className="text-sm text-red-300">{loadError}</span>
          </div>
          <button
            onClick={fetchData}
            className="px-4 py-2 rounded-xl bg-red-500/20 hover:bg-red-500/30 text-red-200 text-xs font-medium transition-all border border-red-500/30 shrink-0"
          >
            تلاش مجدد
          </button>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-800">
        <button
          onClick={() => setActiveTab('workflows')}
          className={`flex items-center gap-2.5 px-6 py-3.5 text-sm font-medium border-b-2 transition-all ${
            activeTab === 'workflows'
              ? 'border-amber-500 text-amber-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Zap className="w-4 h-4" />
          اتوماسیون‌های فعال ({workflows.length})
        </button>
        <button
          onClick={() => setActiveTab('templates')}
          className={`flex items-center gap-2.5 px-6 py-3.5 text-sm font-medium border-b-2 transition-all ${
            activeTab === 'templates'
              ? 'border-amber-500 text-amber-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Layers className="w-4 h-4" />
          الگوهای آماده سئو ({templates.length})
        </button>
        <button
          onClick={() => setActiveTab('logs')}
          className={`flex items-center gap-2.5 px-6 py-3.5 text-sm font-medium border-b-2 transition-all ${
            activeTab === 'logs'
              ? 'border-amber-500 text-amber-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Activity className="w-4 h-4" />
          تاریخچه و لاگ اجراها ({logs.length})
        </button>
      </div>

      {/* Main Tab Content */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500"></div>
        </div>
      ) : !loadError && activeTab === 'workflows' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {workflows.length === 0 ? (
            <div className="col-span-full bg-slate-900/40 border border-slate-800/80 rounded-2xl p-12 text-center">
              <Zap className="w-12 h-12 text-slate-600 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-white mb-2">هیچ اتوماسیون فعالی ثبت نشده است</h3>
              <p className="text-slate-400 text-sm max-w-md mx-auto mb-6">
                شما می‌توانید از الگوهای آماده سئو (مانند هشدار افت سرچ کنسول یا بررسی ۴۰۴) یا وب‌هوک اختصاصی استفاده کنید.
              </p>
              <button
                onClick={() => setActiveTab('templates')}
                className="px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-900 text-sm font-bold transition-all"
              >
                مشاهده الگوهای آماده n8n
              </button>
            </div>
          ) : (
            workflows.map((wf) => (
              <div
                key={wf.id}
                className="bg-slate-900/60 border border-slate-800 hover:border-amber-500/30 rounded-2xl p-6 flex flex-col justify-between transition-all"
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    {getStatusBadge(wf.last_run_status)}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setPendingDelete(wf)}
                        disabled={deletingId === wf.id}
                        title="حذف اتوماسیون"
                        className="rounded-lg p-1.5 text-slate-500 transition-all hover:bg-red-500/15 hover:text-red-400 disabled:opacity-50"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleToggleActive(wf.id, wf.is_active)}
                        className={`px-3 py-1 rounded-full text-xs font-medium transition-all flex items-center gap-1.5 ${
                          wf.is_active
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                            : 'bg-slate-800 text-slate-400 border border-slate-700'
                        }`}
                      >
                        <Power className="w-3.5 h-3.5" />
                        {wf.is_active ? 'فعال' : 'غیرفعال'}
                      </button>
                    </div>
                  </div>

                  <h3 className="text-base font-bold text-white mb-2">{wf.name}</h3>
                  <p className="text-xs text-slate-400 leading-relaxed line-clamp-2 mb-4">
                    {wf.description || 'اتوماسیون متصل به وب‌هوک n8n'}
                  </p>

                  <div className="space-y-1.5 bg-slate-950/60 border border-slate-800/80 rounded-xl p-3 text-xs mb-4">
                    <div className="flex items-center justify-between text-slate-400">
                      <span>نوع تریگر:</span>
                      <span className="text-amber-400 font-mono font-medium">
                        {wf.trigger_type === 'cron' ? `زمان‌بندی (${wf.cron_expression})` : 'وب‌هوک رویداد'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-slate-400">
                      <span>آخرین اجرا:</span>
                      <span>
                        {wf.last_run_at
                          ? new Date(wf.last_run_at).toLocaleString('fa-IR')
                          : 'تاکنون اجرا نشده'}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="pt-4 border-t border-slate-800/80 flex items-center justify-between">
                  <span className="text-xs text-slate-400 font-mono truncate max-w-[180px]">
                    {wf.n8n_webhook_url}
                  </span>

                  <button
                    onClick={() => handleRunNow(wf.id)}
                    disabled={runningId === wf.id}
                    className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/20 text-xs font-medium transition-all disabled:opacity-50"
                  >
                    {runningId === wf.id ? (
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Play className="w-3.5 h-3.5" />
                    )}
                    اجرای دستی
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      ) : activeTab === 'templates' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {templates.map((tmpl) => (
            <div
              key={tmpl.key}
              className="bg-slate-900/60 border border-slate-800 hover:border-amber-500/40 rounded-2xl p-6 flex flex-col justify-between transition-all"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="px-3 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                    الگوی آماده n8n
                  </span>
                  <span className="text-xs text-slate-400 font-mono">{tmpl.default_cron || 'Webhook Event'}</span>
                </div>
                <h3 className="text-lg font-bold text-white mb-2">{tmpl.name}</h3>
                <p className="text-xs text-slate-300 leading-relaxed mb-4">{tmpl.description}</p>
              </div>

              <div className="pt-4 border-t border-slate-800/80 flex items-center justify-between">
                <span className="text-xs text-slate-400">دسته‌بندی: {tmpl.category}</span>
                <button
                  onClick={() => {
                    setSelectedTemplate(tmpl);
                    setCustomName(tmpl.name);
                    setCustomWebhookUrl(tmpl.sample_webhook_url);
                    setCustomCron(tmpl.default_cron || '0 9 * * 1');
                    setShowModal(true);
                  }}
                  className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-900 text-xs font-bold transition-all shadow-md shadow-amber-500/10"
                >
                  فعال‌سازی این الگو
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* Execution Logs Table */
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden">
          {logs.length === 0 ? (
            <div className="p-12 text-center text-slate-400 text-sm">
              هیچ لاگی از اجرای اتوماسیون‌ها ثبت نشده است.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse" dir="rtl">
                <thead>
                  <tr className="border-b border-slate-800 text-xs font-semibold text-slate-400 bg-slate-900">
                    <th className="py-4 px-6">وضعیت</th>
                    <th className="py-4 px-6">شناسه ورک‌فلو</th>
                    <th className="py-4 px-6">زمان اجرا (ms)</th>
                    <th className="py-4 px-6">پیام خطا / پاسخ</th>
                    <th className="py-4 px-6">تاریخ اجرا</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-sm">
                  {logs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="py-4 px-6">{getStatusBadge(log.status)}</td>
                      <td className="py-4 px-6 font-mono text-xs text-slate-300">
                        {log.workflow_id.slice(0, 8)}...
                      </td>
                      <td className="py-4 px-6 font-mono text-xs text-indigo-400">
                        {log.execution_time_ms ? `${log.execution_time_ms} ms` : '-'}
                      </td>
                      <td className="py-4 px-6 text-xs text-slate-300 max-w-xs truncate">
                        {log.error_message || 'بدون خطا (پاسخ معتبر دریافت شد)'}
                      </td>
                      <td className="py-4 px-6 text-xs text-slate-400">
                        {new Date(log.created_at).toLocaleString('fa-IR')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Create / Configure Workflow Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 w-full max-w-lg space-y-5">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <Zap className="w-5 h-5 text-amber-400" />
                {selectedTemplate ? 'تنظیم الگوی آماده n8n' : 'افزودن اتوماسیون اختصاصی n8n'}
              </h3>
              <button
                onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateWorkflow} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  نام اتوماسیون / ورک‌فلو
                </label>
                <input
                  type="text"
                  value={customName}
                  onChange={(e) => setCustomName(e.target.value)}
                  placeholder="مثال: گزارش هفتگی سئو به تلگرام"
                  required
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-amber-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  آدرس وب‌هوک (n8n Webhook URL)
                </label>
                <input
                  type="url"
                  value={customWebhookUrl}
                  onChange={(e) => setCustomWebhookUrl(e.target.value)}
                  placeholder="https://n8n.yourdomain.com/webhook/..."
                  required
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white font-mono text-xs focus:outline-none focus:border-amber-500"
                />
                <p className="text-[11px] text-slate-400 mt-1">
                  آدرس Webhook Node در n8n که داده‌های سئو به آن POST می‌شود.
                </p>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  عبارت زمان‌بندی (Cron Expression)
                </label>
                <input
                  type="text"
                  value={customCron}
                  onChange={(e) => setCustomCron(e.target.value)}
                  placeholder="0 9 * * 1"
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white font-mono text-sm focus:outline-none focus:border-amber-500"
                />
              </div>

              <div className="pt-3 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 rounded-xl text-slate-400 hover:text-white text-sm"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  disabled={submitting || !customName || !customWebhookUrl}
                  className="px-6 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-slate-900 text-sm font-bold transition-all"
                >
                  {submitting ? 'در حال ثبت...' : 'ذخیره و فعال‌سازی'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete confirmation */}
      <ConfirmDialog
        isOpen={!!pendingDelete}
        title="حذف اتوماسیون"
        description={
          pendingDelete
            ? `اتوماسیون «${pendingDelete.name}» حذف شود؟ تاریخچه اجراهای آن هم پاک می‌شود.`
            : ""
        }
        confirmLabel="حذف کن"
        loading={deletingId !== null}
        onConfirm={handleDeleteWorkflow}
        onClose={() => setPendingDelete(null)}
      />
    </div>
  );
}
