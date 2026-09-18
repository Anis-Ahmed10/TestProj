"use client";

import "@/lib/amplify-config";

export default function AmplifyProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
