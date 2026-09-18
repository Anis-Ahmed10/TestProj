import PermissionGuard from "@/components/PermissionGuard";
import { PERMISSIONS } from "@/constants";

export default function ActiveProjectsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <PermissionGuard permission={PERMISSIONS.PROJECT_READ}>
      {children}
    </PermissionGuard>
  );
}
