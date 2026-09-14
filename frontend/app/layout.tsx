import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppFrame } from "@/components/auth/app-frame";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "SOVEREIGN AI · Local AI Control Plane",
  description: "Sovereign on-premise agentic AI workbench for confidential industrial work.",
  icons: { icon: "/icon.svg", shortcut: "/icon.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return <html lang="en" data-theme="dark"><head><script dangerouslySetInnerHTML={{ __html: "try{document.documentElement.dataset.theme=localStorage.getItem('sovereignforge-theme')==='light'?'light':'dark'}catch(e){}" }} /></head><body><Providers><AppFrame>{children}</AppFrame></Providers></body></html>;
}
