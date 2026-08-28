import React from "react";
import { BookOpen, Shield, Users, Layers, Zap } from "lucide-react";

export const metadata = {
  title: "راهنما و مستندات سیستم - AI SEO OS",
};

export default function GuidesPage() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
          <BookOpen className="h-6 w-6 text-primary" />
          راهنمای سیستم و مدیریت دسترسی‌ها (RBAC)
        </h1>
        <p className="text-sm text-muted-foreground">
          آشنایی با مفاهیم پایه‌ای پلتفرم، سطوح دسترسی کاربران و نحوه کارکرد سازمان‌ها و پروژه‌ها.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        
        {/* Section 1: Hierarchy */}
        <div className="rounded-2xl border border-white/10 bg-card/60 p-6 shadow-xl backdrop-blur-md">
          <div className="mb-4 flex items-center gap-2 border-b border-white/10 pb-4">
            <Layers className="h-5 w-5 text-blue-400" />
            <h2 className="text-lg font-bold text-white">ساختار و سلسله مراتب سیستم</h2>
          </div>
          <div className="space-y-4 text-sm text-muted-foreground leading-relaxed">
            <p>
              سیستم مدیریت سئو بر پایه سه مفهوم اصلی بنا شده است:
            </p>
            <ul className="list-disc pl-5 space-y-2 text-white/80" dir="rtl">
              <li>
                <strong className="text-blue-400">سازمان‌ها (Organizations):</strong> بالاترین سطح در سیستم. هر سازمان می‌تواند دارای چندین پروژه و اعضای مختلف باشد. هزینه‌ها و طرح‌های اشتراک بر اساس سازمان محاسبه می‌شوند.
              </li>
              <li>
                <strong className="text-purple-400">پروژه‌ها (Projects):</strong> زیرمجموعه یک سازمان هستند. هر پروژه می‌تواند نماینده یک دپارتمان یا یک دسته خاص از کارهای سئو باشد.
              </li>
              <li>
                <strong className="text-emerald-400">وب‌سایت‌ها (Websites):</strong> زیرمجموعه پروژه‌ها هستند. اطلاعات سئو، کلمات کلیدی، و تسک‌ها در سطح وب‌سایت تعریف و مدیریت می‌شوند.
              </li>
            </ul>
          </div>
        </div>

        {/* Section 2: Roles (RBAC) */}
        <div className="rounded-2xl border border-white/10 bg-card/60 p-6 shadow-xl backdrop-blur-md">
          <div className="mb-4 flex items-center gap-2 border-b border-white/10 pb-4">
            <Shield className="h-5 w-5 text-purple-400" />
            <h2 className="text-lg font-bold text-white">سطوح دسترسی (Role-Based Access)</h2>
          </div>
          <div className="space-y-4 text-sm text-muted-foreground leading-relaxed">
            <p>
              سیستم امنیتی (RBAC) ما بر اساس یک سلسله مراتب سخت‌گیرانه کار می‌کند. هر نقش دارای یک «ارزش دسترسی» است و نقش‌های بالاتر دسترسی نقش‌های پایین‌تر را به ارث می‌برند:
            </p>
            <div className="space-y-3">
              <div className="rounded-lg bg-white/5 p-3 border border-white/10">
                <div className="font-bold text-white flex items-center gap-2 mb-1">
                  <span className="bg-red-500/20 text-red-400 px-2 py-0.5 rounded text-xs">مالک (Owner) - بالاترین سطح [سطح ۶۰]</span>
                </div>
                <p className="text-xs">دسترسی کامل به تمامی بخش‌های سازمان، امکان حذف سازمان، ارتقای طرح و مدیریت تمامی کاربران.</p>
              </div>

              <div className="rounded-lg bg-white/5 p-3 border border-white/10">
                <div className="font-bold text-white flex items-center gap-2 mb-1">
                  <span className="bg-orange-500/20 text-orange-400 px-2 py-0.5 rounded text-xs">مدیر کل (Admin) [سطح ۵۰]</span>
                </div>
                <p className="text-xs">دسترسی به ایجاد و حذف پروژه‌ها، مدیریت وب‌سایت‌ها، و امکان دعوت/حذف اعضای تیم (فقط اعضایی با سطح پایین‌تر از خود).</p>
              </div>

              <div className="rounded-lg bg-white/5 p-3 border border-white/10">
                <div className="font-bold text-white flex items-center gap-2 mb-1">
                  <span className="bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded text-xs">مدیر سئو (SEO Manager) [سطح ۴۰]</span>
                </div>
                <p className="text-xs">امکان مدیریت و پیکربندی تنظیمات سئو، افزودن/ویرایش محتواها، اتصال سرچ کنسول و مشاهده تمامی گزارش‌ها.</p>
              </div>

              <div className="rounded-lg bg-white/5 p-3 border border-white/10">
                <div className="font-bold text-white flex items-center gap-2 mb-1">
                  <span className="bg-green-500/20 text-green-400 px-2 py-0.5 rounded text-xs">ویرایشگر (Editor) [سطح ۳۰]</span>
                </div>
                <p className="text-xs">دسترسی فقط برای ایجاد و ویرایش محتواها (مقالات)، انجام تسک‌ها و تغییر وضعیت کارهای روزمره.</p>
              </div>

              <div className="rounded-lg bg-white/5 p-3 border border-white/10">
                <div className="font-bold text-white flex items-center gap-2 mb-1">
                  <span className="bg-teal-500/20 text-teal-300 px-2 py-0.5 rounded text-xs">ناظر (Reviewer) [سطح ۲۰]</span>
                </div>
                <p className="text-xs">امکان مشاهده داشبورد و تأیید یا رد محتواهای تولید شده بدون دسترسی به ایجاد محتوای جدید.</p>
              </div>

              <div className="rounded-lg bg-white/5 p-3 border border-white/10">
                <div className="font-bold text-white flex items-center gap-2 mb-1">
                  <span className="bg-gray-500/20 text-gray-300 px-2 py-0.5 rounded text-xs">بیننده (Viewer) - کمترین سطح [سطح ۱۰]</span>
                </div>
                <p className="text-xs">فقط دسترسی خواندن (Read-only) به داشبورد، گزارش‌ها و وضعیت پروژه‌ها. امکان هیچ‌گونه تغییری را ندارند.</p>
              </div>
            </div>
          </div>
        </div>

        {/* Section 3: Inviting Members */}
        <div className="rounded-2xl border border-white/10 bg-card/60 p-6 shadow-xl backdrop-blur-md lg:col-span-2">
          <div className="mb-4 flex items-center gap-2 border-b border-white/10 pb-4">
            <Users className="h-5 w-5 text-emerald-400" />
            <h2 className="text-lg font-bold text-white">چگونه هم‌تیمی‌های خود را اضافه کنیم؟</h2>
          </div>
          <div className="space-y-4 text-sm text-muted-foreground leading-relaxed">
            <p>
              برای اضافه کردن یک شخص جدید به سازمان خود:
            </p>
            <ol className="list-decimal pl-5 space-y-2 text-white/80" dir="rtl">
              <li>ابتدا شخص مورد نظر باید در سامانه ثبت نام کرده و حساب کاربری داشته باشد.</li>
              <li>از منوی کناری وارد بخش <strong>«سازمان‌ها و اعضا»</strong> شوید.</li>
              <li>در باکس <strong>اعضای سازمان</strong>، روی دکمه <strong>«دعوت عضو جدید»</strong> کلیک کنید.</li>
              <li>ایمیل کاربر را وارد کرده و سطح دسترسی مناسب را انتخاب کنید.</li>
            </ol>
            <div className="mt-4 rounded-xl border border-primary/20 bg-primary/5 p-4 text-primary">
              <div className="flex items-center gap-2 mb-1 font-bold">
                <Zap className="h-4 w-4" />
                <span>نکته مهم امنیتی</span>
              </div>
              <p className="text-xs opacity-90">
                هرگز نقش Owner یا Admin را به کاربرانی که کاملاً به آن‌ها اعتماد ندارید ندهید، چرا که آن‌ها می‌توانند پروژه‌ها را به طور کامل حذف کنند.
              </p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
