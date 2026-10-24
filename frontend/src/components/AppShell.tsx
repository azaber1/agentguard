"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { User } from "@/lib/types";
import { cx, Loading } from "./ui";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/agents", label: "Agents" },
  { href: "/scenarios", label: "Scenarios" },
  { href: "/runs", label: "Test runs" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: user } = useApi<User>("/auth/me");

  async function logout() {
    try {
      await api("/auth/logout", { method: "POST" });
    } finally {
      router.replace("/login");
      router.refresh();
    }
  }

  return (
    <div className="min-h-screen md:flex">
      <aside className="border-b border-border bg-surface md:sticky md:top-0 md:flex md:h-screen md:w-60 md:flex-col md:border-b-0 md:border-r">
        <div className="flex items-center gap-2 px-4 py-4 md:px-5 md:py-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-sm font-bold text-white">A</div>
          <span className="font-semibold text-ink">AgentGuard</span>
        </div>
        <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:pb-0">
          {NAV.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cx(
                  "whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium",
                  active ? "bg-surface-2 text-ink" : "text-ink-2 hover:bg-surface-2 hover:text-ink",
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="hidden border-t border-border p-4 md:mt-auto md:block">
          {user ? (
            <>
              <div className="truncate text-sm font-medium text-ink">{user.full_name}</div>
              <div className="truncate text-xs text-ink-3">{user.organization.name}</div>
            </>
          ) : (
            <div className="h-8" />
          )}
          <button onClick={logout} className="mt-3 text-xs font-medium text-ink-2 hover:text-ink">
            Sign out
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-4 py-6 md:px-8 md:py-8">
        <div className="mx-auto max-w-6xl">
          {user ? children : <Loading />}
          <button onClick={logout} className="mt-10 text-xs font-medium text-ink-2 hover:text-ink md:hidden">
            Sign out
          </button>
        </div>
      </main>
    </div>
  );
}
