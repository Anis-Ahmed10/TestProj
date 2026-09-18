"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Button, Tag, Avatar, Popconfirm, Tooltip, App } from "antd";
import {
  UserAddOutlined,
  DeleteOutlined,
  EditOutlined,
} from "@ant-design/icons";
import {
  fetchProjectTeamMembers,
  removeTeamMember,
  TeamMember,
} from "@/services/teamService";
import AddMemberModal from "@/app/(protected)/project-view/components/AddMemberModal";
import { AVATAR_COLORS } from "@/utils/users/userManagementHelper";
import AITable from "@/components/AITable";
import { usePermissions } from "@/hooks/usePermissions";
import { PERMISSIONS } from "@/constants";

interface TeamTabProps {
  projectId: string;
}

function getAvatarColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++)
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

function getInitials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

export default function TeamTab({ projectId }: TeamTabProps) {
  // 2. Destructure message from App.useApp() hook
  const { message } = App.useApp();
  const { hasPermission } = usePermissions();
  const canManageTeam =
    hasPermission(PERMISSIONS.TEAM_ADD) &&
    hasPermission(PERMISSIONS.TEAM_REMOVE) &&
    hasPermission(PERMISSIONS.TEAM_AVAILABLE_USERS);

  const [members, setMembers] = useState<TeamMember[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);

  const loadTeamMembers = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const data = await fetchProjectTeamMembers(projectId);
      setMembers(data);
    } catch (err) {
      console.error(err);
      message.error("Failed to load project team members");
    } finally {
      setLoading(false);
    }
  }, [projectId, message]);

  useEffect(() => {
    loadTeamMembers();
  }, [loadTeamMembers]);

  const handleDelete = async (userId: string) => {
    setDeletingId(userId);
    try {
      const removedMember = await removeTeamMember(projectId, userId);
      message.success(`${removedMember.name} removed successfully`);
      setMembers((prev) => prev.filter((m) => m.user_id !== userId));
    } catch (err) {
      console.error(err);
      message.error("Failed to remove team member");
    } finally {
      setDeletingId(null);
    }
  };

  const [activePopconfirmId, setActivePopconfirmId] = useState<string | null>(
    null,
  );

  const baseColumns = [
    {
      title: "Member",
      dataIndex: "name",
      key: "name",
      render: (text: string, record: TeamMember) => (
        <div className="flex items-center gap-3">
          <Avatar style={{ backgroundColor: getAvatarColor(text) }}>
            {getInitials(text)}
          </Avatar>
          <div>
            <div className="font-bold text-gray-900">{text}</div>
            <div className="text-xs text-gray-400">{record.email}</div>
          </div>
        </div>
      ),
    },
    {
      title: "Role",
      dataIndex: "role",
      key: "role",
      render: (role: string) => role || "Team Member",
    },
    {
      title: "Hours This Sprint",
      dataIndex: "hours_this_sprint",
      key: "hours_this_sprint",
      align: "center" as const,
      render: (hours: number | null | undefined) => (
        <span className="text-gray-700 font-medium">
          {hours !== null && hours !== undefined ? `${hours} hrs` : "0 hrs"}
        </span>
      ),
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (status: string) => {
        const formattedStatus = status?.toLowerCase();
        let tagColor = "default";
        if (formattedStatus === "active") tagColor = "green";
        if (formattedStatus === "inactive") tagColor = "red";
        return <Tag color={tagColor}>{status || "Active"}</Tag>;
      },
    },
  ];

  const actionColumn = {
    title: "Action",
    key: "action",
    align: "center" as const,
    render: (_: unknown, record: TeamMember) => {
      const userId = record.user_id;
      const isPopconfirmOpen = activePopconfirmId === userId;
      return (
        <div className="flex items-center justify-center gap-1">
          <Tooltip title="Edit member">
            <Button
              type="text"
              icon={
                <EditOutlined className="text-gray-600 hover:text-teal-700" />
              }
              size="small"
            />
          </Tooltip>
          <Popconfirm
            title={
              <span className="text-xs font-semibold text-gray-800">
                Remove Member
              </span>
            }
            description={
              <span className="text-xs text-gray-500">
                Remove from project?
              </span>
            }
            onConfirm={() => {
              setActivePopconfirmId(null);
              handleDelete(userId);
            }}
            onCancel={() => setActivePopconfirmId(null)}
            onOpenChange={(open) => {
              if (open) {
                setActivePopconfirmId(userId);
              } else {
                setActivePopconfirmId(null);
              }
            }}
            okText="Yes, Remove"
            cancelText="Cancel"
            okButtonProps={{ danger: true, loading: deletingId === userId }}
          >
            <Tooltip
              title="Remove from team"
              open={isPopconfirmOpen ? false : undefined}
            >
              <Button
                type="text"
                danger
                icon={<DeleteOutlined />}
                size="small"
                className="hover:bg-red-50"
              />
            </Tooltip>
          </Popconfirm>
        </div>
      );
    },
  };

  const teamColumns = canManageTeam
    ? [...baseColumns, actionColumn]
    : baseColumns;

  return (
    <div className="workspace__body">
      <div className="project-page__detail-card">
        <div className="team-header">
          <span className="project-card__heading">Project Team</span>
          {canManageTeam && (
            <Button
              type="primary"
              icon={<UserAddOutlined />}
              className="project-primary-btn"
              onClick={() => {
                setIsModalOpen(true);
              }}
            >
              Add Member
            </Button>
          )}
        </div>

        <AITable
          columns={teamColumns}
          datasource={members}
          rowKey="id"
          loading={loading}
          pageSize={6}
        />
      </div>

      {canManageTeam && (
        <AddMemberModal
          open={isModalOpen}
          projectId={projectId}
          onClose={() => setIsModalOpen(false)}
          onSuccess={loadTeamMembers}
        />
      )}
    </div>
  );
}
