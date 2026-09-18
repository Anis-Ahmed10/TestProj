"use client";

import React from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { Dropdown, type MenuProps } from "antd";
import {
  DashboardOutlined,
  FolderOpenOutlined,
  TeamOutlined,
  ExperimentOutlined,
  SettingOutlined,
  BranchesOutlined,
  RiseOutlined,
  AppstoreOutlined,
  UsergroupAddOutlined,
  ClockCircleOutlined,
  FileTextOutlined,
  CreditCardOutlined,
  DownOutlined,
  SearchOutlined,
  BarChartOutlined,
  UserOutlined,
} from "@ant-design/icons";

import { navSections } from "@/constants/sidebar";
import { usePermissions } from "@/hooks/usePermissions";
import "../assets/css/sidebar.css";

const iconMap: Record<string, React.ElementType> = {
  LayoutDashboard: DashboardOutlined,
  FolderOpen: FolderOpenOutlined,
  Users: TeamOutlined,
  FlaskConical: ExperimentOutlined,
  Settings2: SettingOutlined,
  GitBranch: BranchesOutlined,
  TrendingUp: RiseOutlined,
  Kanban: AppstoreOutlined,
  UsersRound: UsergroupAddOutlined,
  Clock: ClockCircleOutlined,
  FileText: FileTextOutlined,
  CreditCard: CreditCardOutlined,
  Activity: BarChartOutlined,
  Search: SearchOutlined,
};

export default function Sidebar() {
  const pathname = usePathname();
  const { user, role, hasPermission, isLoaded } = usePermissions();

  const userMenuItems: MenuProps["items"] = [
    {
      key: "signed-in-as",
      type: "group",
      label: user?.email ?? "Signed in",
    },
    {
      key: "profile",
      icon: <UserOutlined />,
      label: <Link href="/profile">Profile</Link>,
    },
  ];

  const visibleSections = navSections
    .map((section) => {
      const sectionHiddenForRole = Boolean(
        section.hiddenForRoles &&
          isLoaded &&
          role &&
          section.hiddenForRoles.includes(role),
      );
      const items = section.items.filter((item) => {
        if (item.permission) {
          return isLoaded && hasPermission(item.permission);
        }
        return !sectionHiddenForRole;
      });
      return { ...section, items };
    })
    .filter((section) => section.items.length > 0);

  const initials = user?.name
    ? user.name
        .split(/\s+/)
        .map((part) => part[0])
        .slice(0, 2)
        .join("")
        .toUpperCase()
    : "–";

  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <div className="sidebar__brand-inner">
          <div className="sidebar__logo">AI</div>
          <div>
            <p className="sidebar__brand-name">Infuse Platform</p>
            <p className="sidebar__brand-sub">AI Testing Delivery</p>
          </div>
        </div>
      </div>

      <nav className="sidebar__nav">
        {visibleSections.map((section) => (
          <div key={section.section}>
            <p className="sidebar__section-label">{section.section}</p>
            <ul className="sidebar__items">
              {section.items.map((item) => {
                const Icon = iconMap[item.icon] || DashboardOutlined;
                const isActive =
                  item.href !== "#" && pathname.startsWith(item.href);
                return (
                  <li key={item.label}>
                    <Link
                      href={item.href}
                      className={`sidebar__item-link${
                        isActive ? " sidebar__item-link--active" : ""
                      }`}
                    >
                      <span className="sidebar__item-icon">
                        <Icon />
                      </span>
                      <span className="sidebar__item-label">{item.label}</span>
                      {item.badge !== undefined && (
                        <span className="sidebar__badge">{item.badge}</span>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="sidebar__footer">
        <Dropdown
          menu={{ items: userMenuItems }}
          trigger={["click"]}
          placement="topRight"
        >
          <button type="button" className="sidebar__user-btn">
            <div className="sidebar__avatar">{initials}</div>
            <div className="sidebar__user-info">
              <p className="sidebar__user-name">{user?.name ?? "Signed in"}</p>
              <p className="sidebar__user-role">{user?.role ?? ""}</p>
            </div>
            <DownOutlined className="sidebar__chevron" />
          </button>
        </Dropdown>
      </div>
    </aside>
  );
}
