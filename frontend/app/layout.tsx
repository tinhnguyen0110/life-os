import type { Metadata, Viewport } from "next";
import "@/lib/tokens.css";
import { ShellLayout } from "@/components/ShellLayout";
import { NO_FLASH_SCRIPT } from "@/lib/no-flash-script";

export const metadata: Metadata = {
  title: "Life OS",
  description: "Trung tâm điều hành cuộc sống số — dự án · tài chính · automation.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0f0a07",
};

// NO_FLASH_SCRIPT imported from lib/no-flash-script.ts — exported there so
// the parity unit test can import it alongside lib/tweaks.ts to assert the
// inlined hex values never drift from the TS source.

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning: browser extensions inject class/style onto <html>
    // before hydration (harmless), which would otherwise log a mismatch warning.
    <html lang="vi" suppressHydrationWarning>
      <head>
        {/* No-flash: apply saved appearance before first paint. */}
        <script dangerouslySetInnerHTML={{ __html: NO_FLASH_SCRIPT }} />
      </head>
      <body suppressHydrationWarning>
        <ShellLayout>{children}</ShellLayout>
      </body>
    </html>
  );
}
