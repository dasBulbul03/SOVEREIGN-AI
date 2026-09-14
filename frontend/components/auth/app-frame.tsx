"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";

import { ControlPlane } from "@/components/control-plane/control-plane";
import { getCurrentUser } from "@/lib/auth";

const publicRoutes = new Set(["/signin", "/signup"]);

export function AppFrame({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isPublic = publicRoutes.has(pathname);
  const user = useQuery({ queryKey: ["auth", "me"], queryFn: getCurrentUser, retry: false });

  useEffect(() => {
    if (!isPublic && !user.isPending && user.data === null) {
      router.replace(`/signin?next=${encodeURIComponent(pathname)}`);
    }
  }, [isPublic, pathname, router, user.data, user.isPending]);

  if (isPublic) return children;
  if (user.isPending || user.data === null) {
    return <div className="auth-loading"><ShieldCheck size={28} /><span>Verifying local session…</span></div>;
  }
  if (user.isError) {
    return <div className="auth-loading error-copy">Authentication service is unavailable.</div>;
  }
  return <ControlPlane>{children}</ControlPlane>;
}
