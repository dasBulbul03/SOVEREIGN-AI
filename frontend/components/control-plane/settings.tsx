"use client";

import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Check, Laptop, Save, ShieldCheck, UserRound } from "lucide-react";

import { getCurrentUser, type AuthUser } from "@/lib/auth";
import { request, type UserSession, type Workspace } from "./types";
import { Badge, Title } from "./ui";

type SettingsTab = "profile" | "workspace" | "security";

export function AccountSettings({ initialTab }: { initialTab: SettingsTab }) {
  const router = useRouter();
  const client = useQueryClient();
  const [tab, setTab] = useState<SettingsTab>(initialTab);
  const [saved, setSaved] = useState("");
  const [defaultWorkspace, setDefaultWorkspace] = useState("");
  const user = useQuery({ queryKey: ["auth", "me"], queryFn: getCurrentUser });
  const workspaces = useQuery({ queryKey: ["workspaces"], queryFn: () => request<Workspace[]>("/workspaces") });
  const sessions = useQuery({ queryKey: ["auth", "sessions"], queryFn: () => request<UserSession[]>("/auth/sessions") });
  const updateProfile = useMutation({
    mutationFn: (fullName: string) => request<AuthUser>("/auth/me", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ full_name: fullName }) }),
    onSuccess: (updated) => { client.setQueryData(["auth", "me"], updated); setSaved("Profile saved."); },
  });
  const revoke = useMutation({
    mutationFn: (id: string) => request<void>(`/auth/sessions/${id}`, { method: "DELETE" }),
    onSuccess: async (_, id) => {
      const wasCurrent = sessions.data?.find((item) => item.id === id)?.current;
      if (wasCurrent) router.replace("/signin");
      else await client.invalidateQueries({ queryKey: ["auth", "sessions"] });
    },
  });

  useEffect(() => {
    // Hydrate this browser-only preference after the server render.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDefaultWorkspace(window.localStorage.getItem("sovereign-default-workspace") ?? "");
  }, []);

  useEffect(() => {
    // Keep the visible tab aligned when profile-menu navigation changes only the query string.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTab(initialTab);
  }, [initialTab]);

  function chooseTab(next: SettingsTab) {
    setTab(next); setSaved(""); router.replace(`/settings?tab=${next}`, { scroll: false });
  }

  function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    updateProfile.mutate(String(new FormData(event.currentTarget).get("full_name") ?? "").trim());
  }

  function saveWorkspace() {
    if (!defaultWorkspace) return;
    window.localStorage.setItem("sovereign-default-workspace", defaultWorkspace);
    setSaved("Default workspace saved for this browser.");
  }

  return <>
    <Title eyebrow="ACCOUNT CONTROL" title="Profile & settings" copy="Manage your local identity, workspace preference, and authenticated sessions." />
    <div className="settings-layout">
      <aside className="settings-tabs"><button className={tab === "profile" ? "active" : ""} onClick={() => chooseTab("profile")}><UserRound size={16} /> Profile</button><button className={tab === "workspace" ? "active" : ""} onClick={() => chooseTab("workspace")}><Laptop size={16} /> Workspace</button><button className={tab === "security" ? "active" : ""} onClick={() => chooseTab("security")}><ShieldCheck size={16} /> Security & sessions</button></aside>
      <section className="panel settings-panel">
        {saved && <div className="success-strip"><Check size={14} /> {saved}</div>}
        {tab === "profile" && <><span className="eyebrow">PERSONAL INFORMATION</span><h2>Your profile</h2><p>Your name is shown in the control plane and retained with your local account.</p>{user.data && <form className="settings-form" onSubmit={saveProfile}><label><span>Full name</span><input name="full_name" defaultValue={user.data.full_name} required minLength={2} /></label><label><span>Email</span><input value={user.data.email} disabled /></label><label><span>Role</span><input value={user.data.role} disabled /></label><button className="primary" disabled={updateProfile.isPending}><Save size={14} /> {updateProfile.isPending ? "Saving…" : "Save profile"}</button>{updateProfile.error instanceof Error && <div className="api-error">{updateProfile.error.message}</div>}</form>}</>}
        {tab === "workspace" && <><span className="eyebrow">LOCAL PREFERENCE</span><h2>Default workspace</h2><p>This browser preference determines which workspace opens first in Workbench and Knowledge.</p><div className="settings-form"><label><span>Workspace</span><select value={defaultWorkspace} onChange={(event) => setDefaultWorkspace(event.target.value)}><option value="" disabled>Select a workspace</option>{workspaces.data?.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label><button className="primary" onClick={saveWorkspace} disabled={!defaultWorkspace}><Save size={14} /> Save preference</button></div></>}
        {tab === "security" && <><span className="eyebrow">AUTHENTICATED DEVICES</span><h2>Security & sessions</h2><p>Revoke any local session you do not recognize. Revoking the current session signs this browser out.</p><div className="session-list">{sessions.data?.map((item) => <div key={item.id}><i><Laptop size={17} /></i><span><b>{item.current ? "This browser" : "Authenticated session"}</b><small>Last used {new Date(item.last_used_at).toLocaleString()} · expires {new Date(item.expires_at).toLocaleString()}</small></span>{item.current && <Badge tone="green">CURRENT</Badge>}<button className="secondary" disabled={revoke.isPending} onClick={() => { if (window.confirm(`Revoke ${item.current ? "the current" : "this"} session?`)) revoke.mutate(item.id); }}>Revoke</button></div>)}</div>{sessions.error instanceof Error && <div className="api-error">{sessions.error.message}</div>}</>}
      </section>
    </div>
  </>;
}
