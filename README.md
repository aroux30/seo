# AI SEO OS — سیستم عامل و مرکز فرماندهی هوشمند سئو (Phase 1)

پلتفرم پیشرفته مدیریت هوشمند سئو برای نظارت، تحلیل، برنامه‌ریزی، اتوماسیون (از طریق عوامل هوش مصنوعی و n8n) و اجرای عملیات سئو روی وب‌سایت‌های چندگانه از یک داشبورد مرکزی.

---

## ویژگی‌های فاز ۱ (Foundation Platform)
- **معماری چندسازمانی (Multi-Tenant & Organization Scoped):** امکان تعریف چندین سازمان مستقل با اعضا و سطوح دسترسی (RBAC) مختلف (Owner, Admin, SEO Manager, Editor, Reviewer, Viewer).
- **مدیریت وب‌سایت‌ها و پروژه‌ها:** پشتیبانی از دسته‌بندی وب‌سایت‌ها در پروژه‌ها، تنظیم دامنه و انتخاب سطح اتوماسیون (دستی، دستیار هوشمند AI Assist، یا خودکار Autopilot).
- **بک‌اند قدرتمند با FastAPI و PostgreSQL:** پیاده‌سازی کامل احراز هویت (JWT Access/Refresh Token) با هشینگ ایمن Bcrypt و رمزنگاری متقارن Fernet برای توکن‌های حساس، به همراه ۷ جدول اصلی در دیتابیس (مدیریت‌شده با Alembic).
- **فرانت‌اند مدرن با Next.js 15 (Persian RTL):** طراحی بسیار زیبا و پیشرفته با Dark Mode، فونت فارسی Vazirmatn، و داشبورد مرکزی کامل به زبان فارسی.
- **مستندات و راهنمای راه‌اندازی OAuth سرچ کنسول:** راهنمای گام‌به‌گام به همراه آدرس‌های دقیق جهت آمادگی برای ورود به فاز ۲ (اتصال سرچ کنسول).

---

## ساختار پروژه
```
SEO/
├── backend/                  # کدهای سرور (FastAPI + SQLAlchemy + Alembic)
│   ├── app/                  # منطق برنامه (Models, Schemas, Services, API, Security)
│   ├── migrations/           # مایگریشن‌های دیتابیس
│   ├── Dockerfile            # داکر بک‌اند
│   └── pyproject.toml        # وابستگی‌های پایتون (مدیریت با uv)
├── frontend/                 # کدهای فرانت‌اند (Next.js 15 + Tailwind CSS + RTL)
│   ├── app/                  # صفحات برنامه (Auth, Dashboard, Websites, Orgs, Settings)
│   ├── context/              # مدیریت وضعیت (AuthContext)
│   ├── lib/                  # کلاینت ارتباط با API
│   └── Dockerfile            # داکر فرانت‌اند
├── docs/                     # مستندات پروژه
│   ├── architecture/         # معماری سیستم، ERD، و طراحی API
│   └── guides/               # راهنمای اتصال به Google Cloud OAuth
├── docker-compose.yml        # ارکستراسیون کل سرویس‌ها (Postgres, Redis, API, UI)
└── .env.example              # نمونه متغیرهای محیطی
```

---

## نحوه راه‌اندازی سریع با Docker Compose (پیشنهادی)

### ۱. تنظیم متغیرهای محیطی
ابتدا فایل `.env.example` را کپی کرده و به `.env` تغییر نام دهید:
```bash
cp .env.example .env
```

### ۲. اجرای سرویس‌ها با داکر
در دایرکتوری اصلی پروژه، دستور زیر را اجرا کنید:
```bash
docker compose up -d --build
```

پس از بالا آمدن کانتینرها:
- **داشبورد فارسی (Frontend):** در آدرس `http://localhost:3000` در دسترس است.
- **مستندات API (Swagger UI):** در آدرس `http://localhost:8000/docs` در دسترس است.
- **وضعیت سلامت سیستم (Health Check):** در آدرس `http://localhost:8000/health` در دسترس است.

---

## نحوه اجرای محلی (بدون داکر) برای توسعه‌دهندگان

### ۱. اجرای بک‌اند (FastAPI)
ابتدا اطمینان حاصل کنید که PostgreSQL و Redis روی سیستم شما فعال هستند و اطلاعات اتصال در `.env` ثبت شده است.
```bash
cd backend
# نصب وابستگی‌ها با uv
uv sync
# اجرای مایگریشن‌های دیتابیس
uv run alembic upgrade head
# اجرای سرور توسعه
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### ۲. اجرای فرانت‌اند (Next.js 15)
```bash
cd frontend
# نصب وابستگی‌ها
npm install
# اجرای سرور توسعه
npm run dev
```

---

## راهنمای ساخت اطلاعات OAuth در Google Cloud (پیش‌نیاز فاز ۲)
برای دریافت `GOOGLE_CLIENT_ID` و `GOOGLE_CLIENT_SECRET` جهت اتصال وب‌سایت‌ها به سرچ کنسول در فاز بعدی، به مستندات زیر مراجعه کنید:
👉 [مستندات ساخت پروژه در Google Cloud](docs/guides/01-google-cloud-setup.md)

---

## 🚀 استقرار نهایی روی سرور Single VPS (Production Deployment)

برای استقرار و اجرای کامل پروداکشن روی یک سرور مجازی (Single VPS) با استفاده از **Docker Compose + Nginx + PostgreSQL + Redis + Celery + FastAPI + Next.js**:

### ۱. تنظیم متغیرهای محیطی پروداکشن
ابتدا فایل نمونه `.env.production.example` را کپی کرده و اطلاعات واقعی (کلیدهای API اوپن‌ای‌آی، کلاد، جیمینای، سرچ کنسول و رمز عبور دیتابیس) را وارد کنید:
```bash
cp .env.production.example .env.production
nano .env.production
```

### ۲. اجرای اسکریپت استقرار خودکار (Linux VPS)
در سرورهای لینوکس (Ubuntu / Debian / CentOS)، دستور زیر را اجرا کنید:
```bash
chmod +x deploy.sh
./deploy.sh
```

### ۳. اجرای استقرار در ویندوز سرور / پاورشل (Windows Server)
```powershell
.\deploy.ps1
```

پس از اتمام ساخت و اجرای کانتینرها:
- **رابط کاربری داشبورد فارسی:** `http://localhost/` (یا IP سرور شما بر روی پورت 80/443 از طریق Nginx Reverse Proxy)
- **مستندات API بک‌اند:** `http://localhost/docs`
- **ورکرهای پس‌زمینه:** `celery_worker` و `celery_beat` به‌طور خودکار فعال شده و اتوماسیون‌های n8n و زمان‌بندی‌ها را مدیریت می‌کنند.
