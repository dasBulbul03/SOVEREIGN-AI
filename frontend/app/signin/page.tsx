import { Suspense } from "react";

import { AuthScreen } from "@/components/auth/auth-screen";

export default function SigninPage() {
  return <Suspense><AuthScreen mode="signin" /></Suspense>;
}
