import PermissionGuard from "@/components/PermissionGuard";
import { PERMISSIONS } from "@/constants";

export default function StoryReviewLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <PermissionGuard permission={PERMISSIONS.STORY_GET_PENDING_APPROVALS}>
      {children}
    </PermissionGuard>
  );
}
