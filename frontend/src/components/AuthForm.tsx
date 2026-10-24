"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import { Button, ErrorBanner, Field, inputClass } from "./ui";

/** Only allow same-site relative redirects after login. */
export function safeNext(next: string | null): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return "/dashboard";
  return next;
}

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") {
        await api("/auth/login", { method: "POST", body: { email: form.get("email"), password: form.get("password") } });
      } else {
        await api("/auth/register", {
          method: "POST",
          body: {
            email: form.get("email"),
            password: form.get("password"),
            full_name: form.get("full_name"),
            organization_name: form.get("organization_name"),
          },
        });
      }
      router.replace(safeNext(params.get("next")));
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-lg font-bold text-white">A</div>
          <h1 className="text-xl font-semibold text-ink">{mode === "login" ? "Sign in to AgentGuard" : "Create your workspace"}</h1>
          <p className="mt-1 text-sm text-ink-2">Test AI agents for reliability, security and policy compliance.</p>
        </div>
        <form onSubmit={onSubmit} className="space-y-4 rounded-xl border border-border bg-surface p-6">
          <ErrorBanner message={error} />
          {mode === "register" && (
            <>
              <Field label="Full name" htmlFor="full_name">
                <input id="full_name" name="full_name" required maxLength={200} className={inputClass} autoComplete="name" />
              </Field>
              <Field label="Organization" htmlFor="organization_name">
                <input id="organization_name" name="organization_name" required maxLength={200} className={inputClass} autoComplete="organization" />
              </Field>
            </>
          )}
          <Field label="Email" htmlFor="email">
            <input id="email" name="email" type="email" required className={inputClass} autoComplete="email" />
          </Field>
          <Field label="Password" htmlFor="password" hint={mode === "register" ? "At least 10 characters." : undefined}>
            <input
              id="password"
              name="password"
              type="password"
              required
              minLength={mode === "register" ? 10 : 1}
              className={inputClass}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
          </Field>
          <Button type="submit" disabled={busy} className="w-full">
            {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </Button>
        </form>
        <p className="mt-4 text-center text-sm text-ink-2">
          {mode === "login" ? (
            <>
              New to AgentGuard? <Link className="font-medium text-accent hover:underline" href="/register">Create an account</Link>
            </>
          ) : (
            <>
              Already have an account? <Link className="font-medium text-accent hover:underline" href="/login">Sign in</Link>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
