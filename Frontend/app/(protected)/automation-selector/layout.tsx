import PermissionGuard from "@/components/PermissionGuard";
import { PERMISSIONS } from "@/constants";

export default function AutomationSelectorLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <PermissionGuard permission={PERMISSIONS.AUTOMATION_ANALYZE}>
      {children}
    </PermissionGuard>
  );
}
