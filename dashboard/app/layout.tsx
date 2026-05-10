import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { SiteNav } from "@/components/site-nav";
import { ThemeProvider } from "@/components/theme-provider";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const SITE_URL = "https://same-model-same-task.vercel.app";
const SITE_TITLE = "same-model-same-task";
const SITE_DESCRIPTION =
  "Open benchmark of 8 LLM agent frameworks (Python + TypeScript) calling the same Gemini model on the same task with the same 4 tools — only the framework varies.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: SITE_TITLE,
    template: `%s · ${SITE_TITLE}`,
  },
  description: SITE_DESCRIPTION,
  authors: [{ name: "Etienne Brun", url: "https://github.com/tienedev" }],
  openGraph: {
    type: "website",
    url: SITE_URL,
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    siteName: SITE_TITLE,
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col">
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          <SiteNav />
          <div className="flex-1">{children}</div>
          <footer className="mt-16 border-t border-border/60">
            <div className="container mx-auto flex flex-col gap-1 px-4 py-6 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
              <span>
                same-model-same-task — open benchmark of LLM agent frameworks.
              </span>
              <a
                href="https://github.com/tienedev/same-model-same-task"
                className="hover:text-foreground"
              >
                github.com/tienedev/same-model-same-task
              </a>
            </div>
          </footer>
        </ThemeProvider>
      </body>
    </html>
  );
}
