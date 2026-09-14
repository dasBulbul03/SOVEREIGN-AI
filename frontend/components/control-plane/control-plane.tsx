"use client";

import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Activity, BookOpen, Building2, ChevronDown, ChevronRight, Cpu, Gauge, LockKeyhole, LogOut, Menu, Moon, Settings, ShieldCheck, Sparkles, Sun, UserRound } from "lucide-react";

import { getJson, type Readiness, type RegisteredModel } from "@/lib/api";
import { getCurrentUser, signOut } from "@/lib/auth";
import type { View } from "./types";
import { Badge } from "./ui";

const nav = [
  { id: "workbench", href: "/workbench", label: "Workbench", icon: Sparkles },
  { id: "overview", href: "/overview", label: "Overview", icon: Gauge },
  { id: "models", href: "/models", label: "Model registry", icon: Cpu },
  { id: "knowledge", href: "/knowledge", label: "Knowledge base", icon: BookOpen },
  { id: "trace", href: "/trace", label: "Execution trace", icon: Activity },
  { id: "security", href: "/security", label: "Sovereignty", icon: ShieldCheck },
] satisfies { id: View; href: string; label: string; icon: typeof Activity }[];

export function ControlPlane({ children }: { children: ReactNode }) {
  const [drawer, setDrawer] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const profile = useRef<HTMLDivElement>(null);
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const user = useQuery({ queryKey: ["auth", "me"], queryFn: getCurrentUser, retry: false });
  const logout = useMutation({
    mutationFn: signOut,
    onSuccess: () => {
      queryClient.setQueryData(["auth", "me"], null);
      router.replace("/signin");
    },
  });
  const readiness = useQuery({ queryKey: ["readiness"], queryFn: () => getJson<Readiness>("/readiness"), refetchInterval: 30_000 });
  const models = useQuery({ queryKey: ["models"], queryFn: () => getJson<RegisteredModel[]>("/models"), refetchInterval: 30_000 });
  const enabledModels = models.data?.filter((model) => model.enabled) ?? [];
  const readyModels = enabledModels.filter((model) => model.latest_health?.status === "ready").length;
  const current = pathname === "/settings" ? { label: "Settings" } : (nav.find((item) => pathname === item.href) ?? nav[0]);

  useEffect(() => {
    const saved = window.localStorage.getItem("sovereignforge-theme");
    const nextTheme = saved === "light" ? "light" : "dark";
    // Hydrate the persisted client-only preference after the server-rendered dark default.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
  }, []);

  useEffect(() => {
    function closeProfile(event: MouseEvent) {
      if (!profile.current?.contains(event.target as Node)) setProfileOpen(false);
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setProfileOpen(false);
    }
    document.addEventListener("mousedown", closeProfile);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeProfile);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, []);

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
    window.localStorage.setItem("sovereignforge-theme", nextTheme);
  }

  return <div className="shell">
    <aside className={drawer ? "sidebar open" : "sidebar"}>
      <div className="brand"><i><ShieldCheck size={21} /></i><div><b>SovereignForge<span>AI</span></b><small>LOCAL AI CONTROL PLANE</small></div></div>
      <nav>{nav.map(({ id, href, label, icon: Icon }) => <Link className={pathname === href ? "active" : ""} onClick={() => setDrawer(false)} href={href} key={id}><Icon size={18} />{label}{id === "security" && <em />}</Link>)}</nav>
      <div className="node">
        <div><i className={`dot ${readiness.data?.status === "ok" ? "" : "amber"}`} /><b>Node SF-01</b><small>{readiness.isPending ? "Checking local services…" : readiness.data?.status === "ok" ? "All systems operational" : "Service attention required"}</small></div>
        <label>Ready models <b>{readyModels} / {enabledModels.length}</b></label>
        <progress value={readyModels} max={Math.max(enabledModels.length, 1)} />
        <label>Execution mode <b>Local API</b></label><progress value="100" max="100" />
      </div>
    </aside>
    <main>
      <header><button className="menu" aria-label="Toggle navigation" onClick={() => setDrawer(!drawer)}><Menu size={19} /></button><div className="crumb">SOVEREIGN AI <ChevronRight size={13} /> <b>{current.label}</b></div><div className="profile-area" ref={profile}><button className="identity" aria-haspopup="menu" aria-expanded={profileOpen} onClick={() => setProfileOpen((open) => !open)}><Badge tone={readiness.data?.status === "ok" ? "green" : "amber"}><LockKeyhole size={12} /> SOVEREIGN MODE</Badge><i>{user.data?.full_name.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase() ?? "SA"}</i><span><b>{user.data?.full_name ?? "Local user"}</b><small>{user.data?.organization.name ?? "Organization"}</small></span><ChevronDown className={profileOpen ? "rotated" : ""} size={14} /></button>{profileOpen && <div className="profile-panel" role="menu"><div className="profile-summary"><i>{user.data?.full_name.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase() ?? "SA"}</i><span><b>{user.data?.full_name}</b><small>{user.data?.email}</small></span></div><div className="profile-context"><span><Building2 size={14} /><small>ORGANIZATION</small></span><b>{user.data?.organization.name}</b><em>{user.data?.role}</em></div><div className="profile-menu"><button role="menuitem" onClick={() => { setProfileOpen(false); router.push("/settings?tab=profile"); }}><UserRound size={15} /><span><b>Profile</b><small>Personal information</small></span><ChevronRight size={13} /></button><button role="menuitem" onClick={() => { setProfileOpen(false); router.push("/settings?tab=workspace"); }}><Settings size={15} /><span><b>Settings</b><small>Workspace preferences</small></span><ChevronRight size={13} /></button><button role="menuitem" onClick={() => { setProfileOpen(false); router.push("/settings?tab=security"); }}><ShieldCheck size={15} /><span><b>Security & sessions</b><small>Manage trusted devices</small></span><ChevronRight size={13} /></button></div><div className="theme-row"><span>{theme === "dark" ? <Moon size={15} /> : <Sun size={15} />}<b>Dark mode</b></span><button className={theme === "dark" ? "theme-switch active" : "theme-switch"} role="switch" aria-checked={theme === "dark"} aria-label="Toggle dark mode" onClick={toggleTheme}><i /></button></div><button className="profile-signout" role="menuitem" disabled={logout.isPending} onClick={() => logout.mutate()}><LogOut size={15} />{logout.isPending ? "Signing out…" : "Sign out"}</button></div>}</div></header>
      <div className="page">{children}</div>
    </main>
    {drawer && <button className="overlay" aria-label="Close navigation" onClick={() => setDrawer(false)} />}
  </div>;
}
