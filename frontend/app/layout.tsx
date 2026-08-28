import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/context/auth-context";
import { Toaster } from "react-hot-toast";

export const metadata: Metadata = {
  title: "AI SEO OS — سیستم مدیریت هوشمند سئو",
  description: "مرکز فرماندهی هوشمند سئو برای مدیریت، تحلیل، و اتوماسیون وب‌سایت‌ها",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fa" dir="rtl" className="dark">
      <head>
        <link
          href="https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css"
          rel="stylesheet"
          type="text/css"
        />
      </head>
      <body className="font-vazir min-h-screen bg-background text-foreground antialiased selection:bg-primary/30">
        <AuthProvider>{children}</AuthProvider>
        <Toaster position="bottom-right" toastOptions={{ style: { background: '#18181b', color: '#fff', border: '1px solid rgba(255,255,255,0.1)' } }} />
      </body>
    </html>
  );
}
