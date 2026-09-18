"use client";

import { Modal, Table, Tag, Typography, Space, Divider, Alert } from "antd";
import {
  CheckCircleOutlined,
  WarningOutlined,
  CloseCircleOutlined,
} from "@ant-design/icons";
import type { PushToJiraResult, PushedTestCase } from "@/types/jira";

const { Text } = Typography;

interface PushToJiraModalProps {
  open: boolean;
  onClose: () => void;
  result: PushToJiraResult | null;
  loading: boolean;
}

const pushedColumns = [
  {
    title: "TC ID",
    dataIndex: "tc_id",
    key: "tc_id",
    render: (id: string, row: PushedTestCase) => (
      <span>
        {id}
        {row.rename_note && (
          <Tag color="orange" style={{ marginLeft: 6, fontSize: 10 }}>
            renamed from {row.rename_note}
          </Tag>
        )}
      </span>
    ),
  },
  {
    title: "Jira Story ID",
    dataIndex: "jira_key",
    key: "jira_key",
    render: (key: string | null) =>
      key ? <Tag color="blue">{key}</Tag> : <Text type="secondary">—</Text>,
  },
  {
    title: "Status",
    dataIndex: "status",
    key: "status",
    render: (status: string) => {
      if (status === "pushed")
        return (
          <Tag color="green" icon={<CheckCircleOutlined />}>
            Pushed
          </Tag>
        );
      if (status === "duplicate")
        return (
          <Tag color="orange" icon={<WarningOutlined />}>
            Duplicate
          </Tag>
        );
      return (
        <Tag color="red" icon={<CloseCircleOutlined />}>
          Failed
        </Tag>
      );
    },
  },
];

export default function PushToJiraModal({
  open,
  onClose,
  result,
  loading,
}: PushToJiraModalProps) {
  if (!result && !loading) return null;

  return (
    <Modal
      title="Push to Jira — Results"
      open={open}
      onCancel={onClose}
      onOk={onClose}
      okText="Done"
      cancelButtonProps={{ style: { display: "none" } }}
      width={700}
      confirmLoading={loading}
    >
      {loading && (
        <Alert title="Pushing test cases to Jira…" type="info" showIcon />
      )}

      {result && (
        <Space orientation="vertical" style={{ width: "100%" }} size={16}>
          {/* Summary bar */}
          <Space size={20} wrap>
            <Tag color="green" style={{ padding: "4px 10px", fontSize: 13 }}>
              <CheckCircleOutlined /> {result.pushed_count} pushed
            </Tag>
            <Tag color="orange" style={{ padding: "4px 10px", fontSize: 13 }}>
              <WarningOutlined /> {result.duplicate_count} duplicates skipped
            </Tag>
            {result.failed_count > 0 && (
              <Tag color="red" style={{ padding: "4px 10px", fontSize: 13 }}>
                <CloseCircleOutlined /> {result.failed_count} failed
              </Tag>
            )}
            <Tag color="blue" style={{ padding: "4px 10px", fontSize: 13 }}>
              {result.db_saved_count} saved to DB
            </Tag>
          </Space>

          {/* Pushed items */}
          {result.pushed.length > 0 && (
            <>
              <Divider plain>Pushed ({result.pushed.length})</Divider>
              <Table
                dataSource={result.pushed}
                columns={pushedColumns}
                rowKey="tc_id"
                size="small"
                pagination={false}
                scroll={{ y: 240 }}
              />
            </>
          )}

          {/* Duplicates */}
          {result.duplicates.length > 0 && (
            <>
              <Divider plain>
                Skipped as duplicates ({result.duplicates.length})
              </Divider>
              <Space wrap>
                {result.duplicates.map((id: string) => (
                  <Tag key={id} color="orange">
                    {id}
                  </Tag>
                ))}
              </Space>
            </>
          )}

          {/* Failures */}
          {result.failed.length > 0 && (
            <>
              <Divider plain>Failed ({result.failed.length})</Divider>
              {result.failed.map((f: { tc_id: string; error: string }) => (
                <Alert
                  key={f.tc_id}
                  type="error"
                  showIcon
                  title={f.tc_id}
                  description={f.error}
                  style={{ marginBottom: 6 }}
                />
              ))}
            </>
          )}
        </Space>
      )}
    </Modal>
  );
}
