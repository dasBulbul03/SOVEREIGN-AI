import { AccountSettings } from "@/components/control-plane/settings";

export default async function SettingsPage({ searchParams }: { searchParams: Promise<{ tab?: string }> }) {
  const { tab } = await searchParams;
  const initialTab = tab === "workspace" || tab === "security" ? tab : "profile";
  return <AccountSettings initialTab={initialTab} />;
}
