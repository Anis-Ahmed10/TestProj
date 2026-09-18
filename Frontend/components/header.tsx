"use client";

import { useState, Suspense } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { signOut } from "aws-amplify/auth";
import { MenuOutlined } from "@ant-design/icons";
import "../assets/css/header.css";
import LogoutSVG from "@/assets/Icons/LogoutSVG";
import { useAppDispatch } from "@/store/store";
import { resetAllState } from "@/store/store";

interface HeaderProps {
  onMenuToggle?: () => void;
}

const pageTitles: Record<string, string> = {
  "/test-generator/": "AI Test Case Generator",
  "/automation-selector/": "Automation Candidate Selector",
  "/clients/": "Clients",
  "/regression-analyser/": "Regression Impact Analyser",
  "/active-projects/": "Active Projects",
  "/test-cases-library/": "Test Cases Library",
  "/story-review/": "Story Review Queue",
  "/user-management/": "User Management",
  "/profile/": "User Profile",
};

function getDynamicTitle(
  pathname: string,
  searchParams: URLSearchParams,
): string {
  if (pageTitles[pathname]) return pageTitles[pathname];

  if (pathname.startsWith("/project-view")) {
    const projectName = searchParams.get("projectName");
    return projectName ? projectName : "Project View";
  }

  if (pathname.startsWith("/clients/project")) {
    const projectName = searchParams.get("projectName");
    const projectId = searchParams.get("projectId");
    return projectName ? projectName : projectId ? projectId : "Project";
  }

  if (pathname.startsWith("/clients/programme")) {
    return searchParams.get("programmeName") ?? "Programme";
  }

  if (pathname.startsWith("/clients/workspace")) {
    const clientName = searchParams.get("clientName");
    return clientName ? clientName : "Client Workspace";
  }

  return "Infuse Platform";
}

function HeaderInner({ onMenuToggle }: HeaderProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const dispatch = useAppDispatch();
  const title = getDynamicTitle(pathname, searchParams);
  const [isSigningOut, setIsSigningOut] = useState(false);

  async function handleSignOut() {
    setIsSigningOut(true);
    try {
      await signOut();
      dispatch(resetAllState());
      router.push("/login");
    } catch {
      setIsSigningOut(false);
    }
  }

  return (
    <header className="header">
      <div className="header__left">
        <button onClick={onMenuToggle} className="header__menu-btn">
          <MenuOutlined style={{ fontSize: "20px" }} />
        </button>
        <h1 className="header__title">{title}</h1>
      </div>
      <div className="header__right">
        <button
          onClick={handleSignOut}
          disabled={isSigningOut}
          className="header__logout-btn"
        >
          <LogoutSVG />
          <span>{isSigningOut ? "Signing out…" : "Sign Out"}</span>
        </button>
      </div>
    </header>
  );
}

export default function Header({ onMenuToggle }: HeaderProps) {
  return (
    <Suspense
      fallback={
        <header className="header">
          <div className="header__left">
            <h1 className="header__title">Infuse Platform</h1>
          </div>
        </header>
      }
    >
      <HeaderInner onMenuToggle={onMenuToggle} />
    </Suspense>
  );
}
