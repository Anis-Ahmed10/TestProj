"use client";

import React, { useEffect, useState } from "react";
import { Modal, Input, Checkbox, Avatar, Spin, Empty, App } from "antd"; // 1. Import App from "antd"
import { SearchOutlined } from "@ant-design/icons";
import {
  fetchAvailableUsers,
  addTeamMembers,
  AvailableUser,
} from "@/services/teamService";
import { getInitials } from "@/utils/users/userManagementHelper";

interface AddMemberModalProps {
  open: boolean;
  projectId: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function AddMemberModal({
  open,
  projectId,
  onClose,
  onSuccess,
}: AddMemberModalProps) {
  // 2. Destructure message from App.useApp() instead of direct import
  const { message } = App.useApp();

  const [users, setUsers] = useState<AvailableUser[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open && projectId) {
      loadAvailableUsers();
    } else {
      setSelectedIds([]);
      setSearch("");
    }
  }, [open, projectId]);

  const loadAvailableUsers = async () => {
    setLoading(true);
    try {
      const data = await fetchAvailableUsers(projectId);
      setUsers(data);
    } catch (err) {
      console.error(err);
      message.error("Failed to load available users.");
    } finally {
      setLoading(false);
    }
  };

  const handleToggleUser = (userId: string) => {
    setSelectedIds((prev) =>
      prev.includes(userId)
        ? prev.filter((id) => id !== userId)
        : [...prev, userId],
    );
  };

  const handleToggleAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds((prev) => [
        ...new Set([...prev, ...filteredUsers.map((u) => u.id)]),
      ]);
    } else {
      setSelectedIds((prev) =>
        prev.filter((id) => !filteredUsers.some((u) => u.id === id)),
      );
    }
  };

  const handleSubmit = async () => {
    if (selectedIds.length === 0) {
      message.warning("Please select at least one user to add.");
      return;
    }

    setSubmitting(true);
    try {
      await addTeamMembers(projectId, selectedIds);
      message.success("Team members added successfully!");
      onSuccess();
      onClose();
    } catch (err) {
      console.error(err);
      message.error("Failed to add members to team.");
    } finally {
      setSubmitting(false);
    }
  };

  const filteredUsers = users.filter(
    (u) =>
      u.name.toLowerCase().includes(search.toLowerCase()) ||
      u.email.toLowerCase().includes(search.toLowerCase()),
  );

  const isAllSelected =
    filteredUsers.length > 0 &&
    filteredUsers.every((u) => selectedIds.includes(u.id));

  return (
    <Modal
      title={
        <span className="text-base font-semibold text-gray-900">
          Add Team Members
        </span>
      }
      open={open}
      onCancel={onClose}
      onOk={handleSubmit}
      okText={`Add Selected (${selectedIds.length})`}
      confirmLoading={submitting}
      okButtonProps={{
        disabled: selectedIds.length === 0,
        style: { backgroundColor: "#0f4d50", borderColor: "#0f4d50" },
      }}
      destroyOnHidden
      width={500}
    >
      <div className="py-2">
        {/* Search Input */}
        <Input
          prefix={<SearchOutlined className="text-gray-400" />}
          placeholder="Search by name or email..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="mb-4"
        />

        {loading ? (
          <div className="py-8 text-center">
            <Spin size="medium" />
          </div>
        ) : filteredUsers.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="No available users found"
          />
        ) : (
          <div>
            {/* Select All Row */}
            <div className="flex items-center justify-between pb-2 mb-2 border-b border-gray-100 px-2">
              <Checkbox
                checked={isAllSelected}
                onChange={(e) => handleToggleAll(e.target.checked)}
              >
                <span className="text-xs font-semibold text-gray-500 uppercase">
                  Select All ({filteredUsers.length})
                </span>
              </Checkbox>
            </div>

            {/* Users List */}
            <div className="max-h-64 overflow-y-auto space-y-1 pr-1">
              {filteredUsers.map((user) => {
                const isChecked = selectedIds.includes(user.id);
                return (
                  <div
                    key={user.id}
                    onClick={() => handleToggleUser(user.id)}
                    className={`flex items-center justify-between p-2 rounded-lg cursor-pointer transition-colors ${
                      isChecked ? "bg-teal-50/50" : "hover:bg-gray-50"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <Checkbox
                        checked={isChecked}
                        onChange={() => handleToggleUser(user.id)}
                        onClick={(e) => e.stopPropagation()}
                      />
                      <Avatar size={32} style={{ backgroundColor: "#0f4d50" }}>
                        {getInitials(user.name)}
                      </Avatar>
                      <div>
                        <div className="text-sm font-medium text-gray-800">
                          {user.name}
                        </div>
                        <div className="text-xs text-gray-400">
                          {user.email}
                        </div>
                      </div>
                    </div>
                    {user.role && (
                      <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                        {user.role}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
