import PermissionGuard from "@/components/PermissionGuard";
import { PERMISSIONS } from "@/constants";

export default function TestCasesLibraryLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <PermissionGuard permission={PERMISSIONS.TESTCASE_LIBRARY_READ}>
      {children}
    </PermissionGuard>
  );
}
