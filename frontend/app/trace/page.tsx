import { Trace } from "@/components/control-plane/trace-security";

export default async function TracePage({ searchParams }: { searchParams: Promise<{ task?: string }> }) {
  const { task } = await searchParams;
  return <Trace requestedTaskId={task} />;
}
