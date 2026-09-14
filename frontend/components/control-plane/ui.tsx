import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: string }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export function Title({ eyebrow, title, copy, action }: { eyebrow: string; title: string; copy: string; action?: ReactNode }) {
  return <div className="page-title"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{copy}</p></div>{action}</div>;
}

export function Head({ n, label, title, action }: { n: string; label?: string; title: string; action?: ReactNode }) {
  return <div className="head"><div><span className="eyebrow">{n}{label ? ` · ${label}` : ""}</span><h2>{title}</h2></div>{action}</div>;
}

export function Metric({ icon: Icon, value, label, note }: { icon: LucideIcon; value: string; label: string; note: string }) {
  return <div className="metric"><Icon size={18} /><b>{value}</b><span>{label}</span><small>{note}</small></div>;
}

export function Flow({ icon: Icon, title, copy, active }: { icon: LucideIcon; title: string; copy: string; active?: boolean }) {
  return <div className={active ? "flow-node active" : "flow-node"}><Icon size={18} /><span><b>{title}</b><small>{copy}</small></span></div>;
}
