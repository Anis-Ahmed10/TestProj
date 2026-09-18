import { Descriptions, Typography } from "antd";
import type { TestCaseScenario } from "@/types/testGenerator";

const { Text } = Typography;

interface BddTestCaseDetailsProps {
  scenario?: TestCaseScenario;
}

function renderScenarioItems(items?: string[]) {
  if (!items?.length) {
    return <Text type="secondary">None</Text>;
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 2,
        width: "100%",
      }}
    >
      {items.map((item, index) => (
        <Text key={`${item}-${index}`}>{item}</Text>
      ))}
    </div>
  );
}

export default function BddTestCaseDetails({
  scenario,
}: BddTestCaseDetailsProps) {
  const sections = [
    { label: "Given", items: scenario?.given },
    { label: "When", items: scenario?.when },
    { label: "Then", items: scenario?.then },
  ];

  const hasContent = sections.some((section) => section.items?.length);

  if (!hasContent) {
    return <Text type="secondary">No BDD scenario data provided.</Text>;
  }

  return (
    <Descriptions
      column={1}
      size="small"
      bordered={false}
      style={{ marginTop: 6 }}
    >
      {sections.map((section) => (
        <Descriptions.Item
          key={section.label}
          label={<Text strong>{section.label}</Text>}
        >
          {renderScenarioItems(section.items)}
        </Descriptions.Item>
      ))}
    </Descriptions>
  );
}
