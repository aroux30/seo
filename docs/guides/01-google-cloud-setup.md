# راهنمای ساخت پروژه در Google Cloud و دریافت اطلاعات OAuth (برای اتصال Search Console)
# Google Cloud Project & OAuth Setup Guide (Search Console API)

این راهنما مراحل ساخت پروژه در **Google Cloud Platform** و دریافت `GOOGLE_CLIENT_ID` و `GOOGLE_CLIENT_SECRET` را گام‌به‌گام توضیح می‌دهد.
این اطلاعات برای اتصال وب‌سایت‌ها به **Google Search Console** در مرحله دوم (Phase 2) مورد نیاز است.

---

## مرحله ۱: ورود به کنسول Google Cloud
1. وارد لینک زیر شوید (با حساب گوگل خود):
   👉 [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. در بالای صفحه، روی دکمه انتخاب پروژه (**Select a project**) کلیک کنید و سپس دکمه **New Project** را بزنید.
3. یک نام برای پروژه انتخاب کنید (مثلاً `AI-SEO-OS` یا `SEO-Control-Center`) و روی **Create** کلیک کنید.

---

## مرحله ۲: فعال‌سازی API سرچ کنسول (Enable Google Search Console API)
1. در منوی سمت چپ (یا نوار جستجوی بالای صفحه)، عبارت **Google Search Console API** را جستجو کنید.
2. روی نتیجه **Google Search Console API** کلیک کنید.
3. روی دکمه آبی‌رنگ **Enable** (فعال‌سازی) کلیک کنید.

---

## مرحله ۳: تنظیم صفحه رضایت‌نامه (OAuth Consent Screen)
1. از منوی سمت چپ، وارد بخش **APIs & Services** > **OAuth consent screen** شوید.
2. نوع کاربران را **External** (خارجی) انتخاب کنید و روی **Create** کلیک کنید.
3. اطلاعات زیر را وارد کنید:
   - **App name**: `AI SEO OS`
   - **User support email**: ایمیل خودتان را انتخاب کنید.
   - **Developer contact information**: ایمیل خودتان را وارد کنید.
4. روی **Save and Continue** کلیک کنید.
5. در بخش **Scopes**، نیازی به اضافه کردن اسکوپ در اینجا نیست (توسط اپلیکیشن درخواست می‌شود)، روی **Save and Continue** کلیک کنید.
6. در بخش **Test users** (کاربران آزمایشی)، روی **Add Users** کلیک کنید و آدرس جیمیل خودتان (و ایمیل‌هایی که سرچ کنسول وب‌سایت‌ها روی آن‌هاست) را وارد کنید.

---

## مرحله ۴: ساخت اطلاعات ورود (Create Credentials)
1. از منوی سمت چپ، وارد بخش **APIs & Services** > **Credentials** شوید.
2. در بالای صفحه روی **+ CREATE CREDENTIALS** کلیک کرده و گزینه **OAuth client ID** را انتخاب کنید.
3. در کادر **Application type**، گزینه **Web application** را انتخاب کنید.
4. در کادر **Name**، نامی مانند `SEO OS Web Client` بنویسید.
5. در بخش **Authorized redirect URIs**، روی **+ ADD URI** کلیک کنید و آدرس زیر را وارد کنید:
   ```
   http://localhost:8000/api/v1/integrations/gsc/callback
   ```
   *(در صورت استقرار روی سرور اصلی، آدرس دامنه سرور را هم اضافه خواهید کرد: `https://api.yourdomain.com/api/v1/integrations/gsc/callback`)*
6. روی دکمه **Create** کلیک کنید.

---

## مرحله ۵: ذخیره اطلاعات در فایل `.env`
پس از ساخت Client ID، پنجره‌ای باز می‌شود که دو مقدار مهم را نمایش می‌دهد:
- **Your Client ID** (شبیه: `1234567890-abc...apps.googleusercontent.com`)
- **Your Client Secret** (شبیه: `GOCSPX-abc...`)

این دو مقدار را کپی کرده و در فایل `.env` پروژه در ریشه کدهای خود جایگذاری کنید:

```env
GOOGLE_CLIENT_ID=1234567890-abc...apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-abc...
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/integrations/gsc/callback
```

✅ **پایان! اکنون پروژه شما آماده اتصال به سرچ کنسول در فاز ۲ است.**
