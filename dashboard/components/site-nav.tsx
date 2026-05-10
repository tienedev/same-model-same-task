"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";

const links = [
  { href: "/", label: "Leaderboard", match: (p: string) => p === "/" },
  {
    href: "/methodology",
    label: "Methodology",
    match: (p: string) => p.startsWith("/methodology"),
  },
];

export function SiteNav() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-30 border-b border-border/60 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <nav className="container mx-auto flex h-14 items-center gap-6 px-4 text-sm">
        <Link
          href="/"
          className="font-semibold tracking-tight"
        >
          <span className="text-base">same-model-same-task</span>
        </Link>
        <div className="flex items-center gap-5">
          {links.map((link) => {
            const active = link.match(pathname);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "transition-colors hover:text-foreground",
                  active ? "text-foreground" : "text-muted-foreground",
                )}
              >
                {link.label}
              </Link>
            );
          })}
        </div>
        <div className="ml-auto flex items-center gap-3">
          <a
            href="https://github.com/tienedev/same-model-same-task"
            className="text-muted-foreground transition-colors hover:text-foreground"
          >
            GitHub
          </a>
          <ThemeToggle />
        </div>
      </nav>
    </header>
  );
}
