import "../globals.css";
import AuthGate from "@/components/AuthGate";
import LayoutWrapper from "@/components/layoutWrapper";

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGate>
      <LayoutWrapper>{children}</LayoutWrapper>
    </AuthGate>
  );
}
