import type { Metadata, Viewport } from "next";
import "@/lib/tokens.css";
import { ShellLayout } from "@/components/ShellLayout";

export const metadata: Metadata = {
  title: "Life OS",
  description: "Trung tâm điều hành cuộc sống số — dự án · tài chính · automation.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0f0a07",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning: browser extensions inject class/style onto <html>
    // before hydration (harmless), which would otherwise log a mismatch warning.
    <html lang="vi" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <ShellLayout>{children}</ShellLayout>
      </body>
    </html>
  );
}
