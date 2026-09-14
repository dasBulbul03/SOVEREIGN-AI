"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Building2, LockKeyhole, Mail, ShieldCheck, UserRound } from "lucide-react";

import { authRequest } from "@/lib/auth";

export function AuthScreen({ mode }: { mode: "signin" | "signup" }) {
  const signup = mode === "signup";
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const fields = new FormData(event.currentTarget);
    const payload: Record<string, string> = {
      email: String(fields.get("email") ?? ""),
      password: String(fields.get("password") ?? ""),
    };
    if (signup) {
      payload.full_name = String(fields.get("full_name") ?? "");
      payload.organization_name = String(fields.get("organization_name") ?? "");
    }
    try {
      const user = await authRequest(signup ? "/signup" : "/signin", payload);
      queryClient.setQueryData(["auth", "me"], user);
      const requested = searchParams.get("next");
      router.replace(requested?.startsWith("/") && !requested.startsWith("//") ? requested : "/workbench");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Authentication failed.");
    } finally { setBusy(false); }
  }

  return <main className="auth-page">
    <section className="auth-story">
      <div className="auth-brand"><i><ShieldCheck size={24} /></i><div><b>SOVEREIGN<span> AI</span></b><small>LOCAL AI CONTROL PLANE</small></div></div>
      <div><span className="eyebrow">SECURE LOCAL ACCESS</span><h1>Your confidential intelligence stays inside your boundary.</h1><p>Authenticate against your organization&apos;s local SOVEREIGN AI instance. Credentials, sessions, documents, and model workloads remain under your control.</p></div>
      <ul><li><LockKeyhole size={15} /> Argon2id-protected credentials</li><li><ShieldCheck size={15} /> Revocable local sessions</li><li><Building2 size={15} /> Organization-scoped identity</li></ul>
    </section>
    <section className="auth-panel">
      <div className="auth-form-wrap">
        <span className="eyebrow">{signup ? "CREATE LOCAL TENANT" : "WELCOME BACK"}</span>
        <h2>{signup ? "Create your organization" : "Sign in to SOVEREIGN AI"}</h2>
        <p>{signup ? "Set up the first owner account for your organization." : "Use your locally managed organization account."}</p>
        <form className="auth-form" onSubmit={submit}>
          {signup && <><label><span>Organization name</span><div><Building2 size={16} /><input name="organization_name" autoComplete="organization" minLength={2} maxLength={160} required placeholder="Acme Engineering" /></div></label><label><span>Full name</span><div><UserRound size={16} /><input name="full_name" autoComplete="name" minLength={2} maxLength={160} required placeholder="Alex Morgan" /></div></label></>}
          <label><span>Work email</span><div><Mail size={16} /><input name="email" type="email" autoComplete="email" required placeholder="you@organization.com" /></div></label>
          <label><span>Password</span><div><LockKeyhole size={16} /><input name="password" type="password" autoComplete={signup ? "new-password" : "current-password"} minLength={signup ? 12 : 1} maxLength={128} required placeholder={signup ? "At least 12 characters" : "Enter your password"} /></div></label>
          {error && <div className="auth-error" role="alert">{error}</div>}
          <button className="auth-submit" disabled={busy}>{busy ? "Securing session…" : signup ? "Create organization" : "Sign in"}<ArrowRight size={16} /></button>
        </form>
        {!signup && <><div className="auth-divider"><span>OR</span></div><button className="sso-button" disabled><Building2 size={16} /> Continue with organization SSO <small>COMING SOON</small></button></>}
        <p className="auth-switch">{signup ? "Already have an account?" : "New to SOVEREIGN AI?"} <Link href={signup ? "/signin" : "/signup"}>{signup ? "Sign in" : "Create organization"}</Link></p>
      </div>
    </section>
  </main>;
}
