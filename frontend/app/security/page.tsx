"use client";

import { useQuery } from "@tanstack/react-query";

import { Security } from "@/components/control-plane/trace-security";
import { getJson, type Readiness } from "@/lib/api";

export default function SecurityPage() {
  const readiness = useQuery({ queryKey: ["readiness"], queryFn: () => getJson<Readiness>("/readiness") });
  return <Security readiness={readiness.data} />;
}
