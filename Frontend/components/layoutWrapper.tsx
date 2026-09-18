"use client";

import React, { Suspense, useState } from "react";
import AuthHydrator from "@/components/AuthHydrator";
import Sidebar from "@/components/sidebar";
import Header from "@/components/header";

interface LayoutWrapperProps {
  children: React.ReactNode;
}

export default function LayoutWrapper({ children }: LayoutWrapperProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen bg-[#0f1117] overflow-hidden">
      <AuthHydrator />
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-30 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <div
        className={`fixed md:relative z-40 h-screen transition-transform duration-200 ease-in-out ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        <Sidebar />
      </div>
      <div className="flex-1 flex flex-col overflow-hidden">
        <Suspense
          fallback={
            <header className="header">
              <div className="header__left">
                <h1 className="header__title">Infuse Platform</h1>
              </div>
            </header>
          }
        >
          <Header onMenuToggle={() => setSidebarOpen(!sidebarOpen)} />
        </Suspense>
        <main className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-white/6 scrollbar-track-transparent bg-gray-50 h-full">
          {children}
        </main>
      </div>
    </div>
  );
}
