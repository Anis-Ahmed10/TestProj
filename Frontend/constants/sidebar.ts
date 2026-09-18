import { PERMISSIONS, type Permission } from "@/constants";

interface NavItem {
  label: string;
  icon: string;
  href: string;
  badge?: number;
  permission?: Permission;
}

interface NavSection {
  section: string;
  items: NavItem[];
  hiddenForRoles?: string[];
}

const navSections: NavSection[] = [
  {
    section: "MAIN",
    items: [
      // { label: "Portfolio Dashboard", icon: "LayoutDashboard", href: "#" },
      {
        label: "Active Projects",
        icon: "FolderOpen",
        href: "/active-projects",
        permission: PERMISSIONS.PROJECT_READ,
      },
      {
        label: "Clients",
        icon: "Users",
        href: "/clients",
        permission: PERMISSIONS.CLIENT_READ,
      },
    ],
  },
  {
    section: "AI TOOLS",
    items: [
      {
        label: "Test Generator",
        icon: "FlaskConical",
        href: "/test-generator",
        permission: PERMISSIONS.TESTCASE_GENERATE,
      },
      {
        label: "Test Cases Library",
        icon: "FileText",
        href: "/test-cases-library",
        permission: PERMISSIONS.TESTCASE_LIBRARY_READ,
      },
      {
        label: "Story Review",
        icon: "FileText",
        href: "/story-review",
        permission: PERMISSIONS.STORY_GET_PENDING_APPROVALS,
      },
      {
        label: "Automation Selector",
        icon: "Settings2",
        href: "/automation-selector",
        permission: PERMISSIONS.AUTOMATION_ANALYZE,
      },
      {
        label: "Regression Analyser",
        icon: "GitBranch",
        href: "/regression-analyser",
        permission: PERMISSIONS.REGRESSION_READ,
      },
      // { label: "AI Metrics & ROI", icon: "TrendingUp", href: "#" },
    ],
  },
  {
    section: "DELIVERY",
    items: [
      {
        label: "Project View",
        icon: "Kanban",
        href: "/project-view",
        permission: PERMISSIONS.PROJECT_READ,
      },
      // { label: "Team & Resources", icon: "UsersRound", href: "#" },
      // { label: "Time Logging", icon: "Clock", href: "#" },
      // { label: "SOW Manager", icon: "FileText", href: "#" },
    ],
  },
  {
    section: "OPERATIONS",
    hiddenForRoles: ["Test Engineer"],
    items: [
      // { label: "Billing", icon: "CreditCard", href: "#" },
      // { label: "Monitoring", icon: "Activity", href: "#" },
      {
        label: "User Management",
        icon: "Users",
        href: "/user-management",
        permission: PERMISSIONS.USER_MANAGE,
      },
    ],
  },
];

export { navSections };
export type { NavItem, NavSection };
