import PermissionGuard from "@/components/PermissionGuard";
import { PERMISSIONS } from "@/constants";

export default function TestGeneratorLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <PermissionGuard permission={PERMISSIONS.TESTCASE_GENERATE}>
      {children}
    </PermissionGuard>
  );
}
