import PermissionGuard from "@/components/PermissionGuard";
import { PERMISSIONS } from "@/constants";

export const metadata = {
  title: "Regression Impact Analyser | Infuse Platform",
  description:
    "AI-powered regression impact analyser that identifies which test cases are affected by code changes, saving hours of manual triage.",
};

export default function RegressionAnalyzerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <PermissionGuard permission={PERMISSIONS.REGRESSION_READ}>
      {children}
    </PermissionGuard>
  );
}
