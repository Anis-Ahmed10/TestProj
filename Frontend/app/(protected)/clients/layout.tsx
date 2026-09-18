import PermissionGuard from "@/components/PermissionGuard";
import { PERMISSIONS } from "@/constants";

export default function ClientsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <PermissionGuard permission={PERMISSIONS.CLIENT_READ}>
      {children}
    </PermissionGuard>
  );
}
