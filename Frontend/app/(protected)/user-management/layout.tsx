import PermissionGuard from "@/components/PermissionGuard";
import { PERMISSIONS } from "@/constants";

export default function UserManagementLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <PermissionGuard permission={PERMISSIONS.USER_MANAGE}>
      {children}
    </PermissionGuard>
  );
}
