"use client";

import React, { useEffect, useState } from "react";
import { Empty } from "antd";
import PencilIcon from "../../assets/icons/PencilIcon";
import CheckCircleIcon from "../../assets/icons/CheckCircleIcon";
import RobotIcon from "../../assets/icons/RobotIcon";
import {
  fetchProjectTestCaseSummary,
  ProjectTestCaseSummary,
} from "@/services/projectService";

const STAT_CARDS = [
  {
    key: "test-cases",
    label: "TOTAL TEST CASES",
    iconBg: "bg-[#e8f4f0]",
    icon: <PencilIcon />,
  },
  {
    key: "pass-rate",
    label: "PASS RATE",
    iconBg: "bg-green-100",
    icon: <CheckCircleIcon />,
  },
  {
    key: "ai-generated",
    label: "AI GENERATED",
    iconBg: "bg-amber-100",
    icon: <RobotIcon />,
  },
];

interface OverviewTabProps {
  projectId: string;
}

export default function OverviewTab({ projectId }: OverviewTabProps) {
  const [summary, setSummary] = useState<ProjectTestCaseSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!projectId) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetchProjectTestCaseSummary(projectId)
      .then((data) => {
        if (!cancelled) setSummary(data);
      })
      .catch(() => {
        if (!cancelled) setSummary(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const cardValue = (key: string): { value: string; sub: string } => {
    if (loading) return { value: "—", sub: "Loading…" };
    if (!summary) return { value: "—", sub: "No data yet" };
    if (key === "test-cases") {
      return {
        value: String(summary.total),
        sub:
          summary.total > 0
            ? `${summary.pending} pending review`
            : "No test cases yet",
      };
    }
    if (key === "pass-rate") {
      return {
        value: summary.total > 0 ? `${summary.pass_rate}%` : "—",
        sub: summary.total > 0 ? `${summary.approved} approved` : "No data yet",
      };
    }
    return { value: "—", sub: "Not tracked yet" };
  };

  return (
    <div className="workspace__body">
      <div className="grid grid-cols-3 gap-4 mb-4">
        {STAT_CARDS.map((card) => {
          const { value, sub } = cardValue(card.key);
          return (
            <div key={card.key} className="project-stat-card">
              <div className={`project-stat-card__icon ${card.iconBg}`}>
                {card.icon}
              </div>
              <div>
                <div className="project-stat-card__label">{card.label}</div>
                <div className="project-stat-card__value">{value}</div>
                <div className="project-stat-card__sub">{sub}</div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="project-page__detail-card">
        <div className="project-card__header">
          <span className="project-card__heading">Recent Activity</span>
        </div>
        {summary && summary.total > 0 ? (
          <ul className="project-recent-activity-list">
            <li className="project-recent-activity-item">
              <PencilIcon />
              <span>
                <strong>{summary.total}</strong> test case
                {summary.total === 1 ? "" : "s"} on this project
                {summary.pending > 0 && (
                  <> — {summary.pending} awaiting review</>
                )}
              </span>
            </li>
          </ul>
        ) : (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="No activity yet"
            className="!py-8"
          />
        )}
      </div>
    </div>
  );
}
