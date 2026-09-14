"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { Overview } from "@/components/control-plane/overview-models";
import { getJson, type Readiness, type RegisteredModel } from "@/lib/api";

export default function OverviewPage() {
  const router = useRouter();
  const readiness = useQuery({ queryKey: ["readiness"], queryFn: () => getJson<Readiness>("/readiness") });
  const models = useQuery({ queryKey: ["models"], queryFn: () => getJson<RegisteredModel[]>("/models") });
  return <Overview go={() => router.push("/workbench")} readiness={readiness.data} models={models.data ?? []} />;
}
