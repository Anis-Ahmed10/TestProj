"use client";

import { ClockCircleOutlined } from "@ant-design/icons";
import "@/assets/css/cooldownNotice.css";

interface CooldownNoticeProps {
  actionLabel: string;
  formattedTime: string;
  className?: string;
}

export default function CooldownNotice({
  actionLabel,
  formattedTime,
  className,
}: CooldownNoticeProps) {
  return (
    <span
      className={`ai-cooldown-notice${className ? ` ${className}` : ""}`}
      role="status"
      aria-live="polite"
    >
      <ClockCircleOutlined />
      <span>
        You can run {actionLabel} again in <strong>{formattedTime}</strong>.
      </span>
    </span>
  );
}
