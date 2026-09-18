"use client";

import { useEffect, useMemo, useState } from "react";
import {
  PlusOutlined,
  EditOutlined,
  UserOutlined,
  SearchOutlined,
  TeamOutlined,
} from "@ant-design/icons";
import {
  Button,
  Input,
  Tag,
  Tabs,
  Space,
  Avatar,
  Flex,
  Typography,
} from "antd";
const { Text } = Typography;
import type { ColumnsType } from "antd/es/table";
import AITable from "@/components/AITable";
import { fetchPlatformUsers, fetchPlatformRoles } from "@/services/userService";
import type { PlatformUser, PlatformRole } from "@/types/user";
import EditUserRoleModal from "./EditUserRoleModal";
import {
  getAvatarColor,
  getInitials,
  getRoleTagColor,
} from "@/utils/users/userManagementHelper";
import "../assets/css/userManagement.css";
import { App } from "antd";

export default function UserManagementPage() {
  const { message } = App.useApp();

  const [users, setUsers] = useState<PlatformUser[]>([]);
  const [roles, setRoles] = useState<PlatformRole[]>([]);
  const [loading, setLoading] = useState(true);
  const [isError, setIsError] = useState(false);
  const [editingUser, setEditingUser] = useState<PlatformUser | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      setIsError(false);
      try {
        const [fetchedUsers, fetchedRoles] = await Promise.all([
          fetchPlatformUsers(),
          fetchPlatformRoles(),
        ]);
        setUsers(fetchedUsers);
        setRoles(fetchedRoles);
      } catch {
        setIsError(true);
        message.error({
          key: "um-load-error",
          content: "Failed to load Users & Roles data. Please try again.",
        });
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  function handleUserUpdated(updatedUser: PlatformUser) {
    setUsers((prev) =>
      prev.map((u) => (u.id === updatedUser.id ? updatedUser : u)),
    );
    message.success("User Role updated successfully.");
  }

  const filteredUsers = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return users;
    return users.filter(
      (u) =>
        (u.name ?? "").toLowerCase().includes(q) ||
        (u.email ?? "").toLowerCase().includes(q) ||
        (u.role ?? "").toLowerCase().includes(q),
    );
  }, [users, searchQuery]);

  const userColumns: ColumnsType<PlatformUser> = useMemo(
    () => [
      {
        title: "User",
        key: "user",
        width: 190,
        render: (_: unknown, record: PlatformUser) => (
          <Space size={12}>
            <Avatar
              style={{
                backgroundColor: getAvatarColor(record.name),
                fontWeight: 700,
                fontSize: 13,
                flexShrink: 0,
              }}
              size={36}
            >
              {getInitials(record.name)}
            </Avatar>
            <Text strong style={{ fontSize: 14 }}>
              {record.name ?? "Unnamed"}
            </Text>
          </Space>
        ),
      },
      {
        title: "Email",
        dataIndex: "email",
        key: "email",
        width: 230,
        render: (email?: string | null) => (
          <Text strong type="secondary" style={{ fontSize: 13 }}>
            {email ?? ""}
          </Text>
        ),
      },
      {
        title: "Role",
        dataIndex: "role",
        key: "role",
        width: 150,
        render: (role?: string | null) => (
          <Tag
            color={getRoleTagColor(role)}
            style={{ fontWeight: 600, borderRadius: 20, padding: "2px 12px" }}
          >
            {role || "Unassigned"}
          </Tag>
        ),
      },
      {
        title: "Actions",
        key: "actions",
        width: 120,
        render: (_: unknown, record: PlatformUser) => (
          <Button
            id={`edit-user-${record.id}`}
            size="small"
            icon={<EditOutlined />}
            onClick={() => setEditingUser(record)}
            aria-label={`Edit role for ${record.name ?? "user"}`}
          >
            Edit
          </Button>
        ),
      },
    ],
    [],
  );

  const roleColumns: ColumnsType<PlatformRole> = useMemo(
    () => [
      {
        title: "Role Name",
        dataIndex: "name",
        key: "name",
        width: 200,
        render: (name: string) => (
          <Tag
            color={getRoleTagColor(name)}
            style={{ fontWeight: 600, borderRadius: 20, padding: "2px 12px" }}
          >
            {name}
          </Tag>
        ),
      },
      {
        title: "Description",
        dataIndex: "description",
        key: "description",
        render: (description: string | undefined) =>
          description ? (
            <span style={{ color: "#374151", fontSize: 13 }}>
              {description}
            </span>
          ) : (
            <span style={{ color: "#9ca3af", fontSize: 13 }}>—</span>
          ),
      },
    ],
    [],
  );

  const tabItems = [
    {
      key: "users",
      label: (
        <Space size={6}>
          <UserOutlined />
          Users
          <Tag
            style={{
              borderRadius: 20,
              fontWeight: 600,
              marginLeft: 2,
              fontSize: 11,
            }}
          >
            {users.length}
          </Tag>
        </Space>
      ),
      children: (
        <div className="um-section">
          <Flex
            justify="space-between"
            align="center"
            wrap="wrap"
            gap={12}
            style={{ padding: "14px 16px 12px" }}
          >
            <Input
              id="user-search-input"
              placeholder="Search by name, email or role…"
              prefix={<SearchOutlined style={{ color: "#9ca3af" }} />}
              allowClear
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ width: 300 }}
              aria-label="Search users"
            />

            <Flex align="center" gap={12}>
              <span
                style={{
                  fontSize: 13,
                  color: "#6b7280",
                  fontWeight: 500,
                  whiteSpace: "nowrap",
                }}
              >
                {filteredUsers.length}
                {filteredUsers.length !== users.length
                  ? ` of ${users.length}`
                  : ""}{" "}
                user{users.length !== 1 ? "s" : ""}
              </span>

              <Button
                type="primary"
                icon={<PlusOutlined />}
                id="add-user-btn"
                style={{
                  background: "#1f3333",
                  borderColor: "#1f3333",
                  fontWeight: 600,
                }}
                aria-label="Add new user"
              >
                Add User
              </Button>
            </Flex>
          </Flex>

          {loading ? (
            <div className="um-loading">
              <div className="um-loading__spinner" />
              <span className="um-loading__text">Loading users…</span>
            </div>
          ) : isError ? (
            <div className="um-empty">
              <div className="um-empty__icon">
                <UserOutlined style={{ fontSize: 48, color: "#9ca3af" }} />
              </div>
              <p className="um-empty__title">Failed to load users</p>
              <p className="um-empty__text">
                Unable to fetch users from backend.
              </p>
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="um-empty">
              <div className="um-empty__icon">
                <UserOutlined style={{ fontSize: 48, color: "#9ca3af" }} />
              </div>
              <p className="um-empty__title">
                {searchQuery.trim()
                  ? `No users found matching "${searchQuery.trim()}"`
                  : "No users found"}
              </p>
              <p className="um-empty__text">
                {searchQuery.trim()
                  ? "Try searching with a different term."
                  : "Platform users will appear here once added."}
              </p>
            </div>
          ) : (
            <AITable<PlatformUser>
              rowKey="id"
              columns={userColumns}
              datasource={filteredUsers}
              pageSize={8}
              showPagination={true}
            />
          )}
        </div>
      ),
    },
    {
      key: "roles",
      label: (
        <Space size={6}>
          <TeamOutlined />
          Roles
          <Tag
            style={{
              borderRadius: 20,
              fontWeight: 600,
              marginLeft: 2,
              fontSize: 11,
            }}
          >
            {roles.length}
          </Tag>
        </Space>
      ),
      children: (
        <div className="um-section">
          {loading ? (
            <div className="um-loading">
              <div className="um-loading__spinner" />
              <span className="um-loading__text">Loading roles…</span>
            </div>
          ) : isError ? (
            <div className="um-empty">
              <div className="um-empty__icon">
                <TeamOutlined style={{ fontSize: 48, color: "#9ca3af" }} />
              </div>
              <p className="um-empty__title">Failed to load roles</p>
              <p className="um-empty__text">
                Unable to fetch roles from backend.
              </p>
            </div>
          ) : roles.length === 0 ? (
            <div className="um-empty">
              <div className="um-empty__icon">
                <TeamOutlined style={{ fontSize: 48, color: "#9ca3af" }} />
              </div>
              <p className="um-empty__title">No roles found</p>
              <p className="um-empty__text">
                Platform roles will appear here once configured.
              </p>
            </div>
          ) : (
            <AITable<PlatformRole>
              rowKey="id"
              columns={roleColumns}
              datasource={roles}
              pageSize={10}
              showPagination={roles.length > 10}
            />
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="um-page">
      <Tabs
        defaultActiveKey="users"
        items={tabItems}
        className="um-antd-tabs"
        destroyOnHidden={false}
      />

      {editingUser && (
        <EditUserRoleModal
          user={editingUser}
          roles={roles}
          onClose={() => setEditingUser(null)}
          onUpdated={(updatedUser) => {
            handleUserUpdated(updatedUser);
            setEditingUser(null);
          }}
        />
      )}
    </div>
  );
}
