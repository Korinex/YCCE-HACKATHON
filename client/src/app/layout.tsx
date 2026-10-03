import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "Privacy Shield", description: "PS-06 Personal Data Privacy Shield" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
