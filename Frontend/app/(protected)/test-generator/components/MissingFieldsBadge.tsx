import { WarningOutlined } from "@ant-design/icons";

export default function MissingFieldsBadge({ count }: { count: number }) {
  return (
    <span className="tg-missing-badge">
      <WarningOutlined style={{ fontSize: 9 }} />
      {count} {count === 1 ? "field" : "fields"} missing
    </span>
  );
}
