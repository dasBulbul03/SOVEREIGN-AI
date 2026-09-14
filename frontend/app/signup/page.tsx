import { Suspense } from "react";

import { AuthScreen } from "@/components/auth/auth-screen";

export default function SignupPage() {
  return <Suspense><AuthScreen mode="signup" /></Suspense>;
}
