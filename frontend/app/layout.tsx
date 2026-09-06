import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NIA Research Assistant",
  description: "Standalone text and voice assistant for authorized research datasets.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
