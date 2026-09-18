import type { Metadata } from "next";
import "./globals.css";
import "@aws-amplify/ui-react/styles.css";
import ReduxProvider from "@/store/ReduxProvider";
import AmplifyProvider from "@/components/AmplifyProvider";

export const metadata: Metadata = {
  title: "Infuse AI Testing Platform",
  description:
    "AI-powered platform for generating test cases, identifying automation candidates, and analyzing regressions.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body className="min-h-full flex flex-col">
        <AmplifyProvider>
          <ReduxProvider>{children}</ReduxProvider>
        </AmplifyProvider>
      </body>
    </html>
  );
}
