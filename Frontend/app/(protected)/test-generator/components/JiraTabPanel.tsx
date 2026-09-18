import { Button, Select } from "antd";
import {
  CloudDownloadOutlined,
  ReloadOutlined,
  CheckCircleFilled,
} from "@ant-design/icons";

interface JiraTabPanelProps {
  active: boolean;
  hasJiraImported: boolean;
  isFileUploaded: boolean;
  isJiraImport: boolean;
  selectedProject: boolean;
  jiraLoading: boolean;
  refreshLoading: boolean;
  statusOptions: string[];
  selectedStatuses: string[];
  statusesLoading: boolean;
  onStatusChange: (values: string[]) => void;
  onImport: () => void;
  onRefresh: () => void;
}

export default function JiraTabPanel({
  active,
  hasJiraImported,
  isFileUploaded,
  isJiraImport,
  jiraLoading,
  refreshLoading,
  selectedProject,
  statusOptions,
  selectedStatuses,
  statusesLoading,
  onStatusChange,
  onImport,
  onRefresh,
}: JiraTabPanelProps) {
  return (
    <div className="usi-panel">
      <p className="usi-panel-hint">
        Pull user stories from the Jira project linked to the selected workspace
        above. Optionally filter by status to import only stories in those
        states; leave it empty to import all.
      </p>
      {active && (
        <div className="usi-status-filter">
          <label
            className="usi-status-filter-label"
            htmlFor="jira-status-filter"
          >
            Filter by status
          </label>
          <Select
            id="jira-status-filter"
            mode="multiple"
            allowClear
            style={{ width: "100%" }}
            placeholder="All statuses"
            value={selectedStatuses}
            onChange={onStatusChange}
            loading={statusesLoading}
            disabled={selectedProject}
            options={statusOptions.map((s) => ({ value: s, label: s }))}
            optionFilterProp="label"
            getPopupContainer={(trigger) =>
              trigger.parentElement ?? document.body
            }
          />
        </div>
      )}
      <div className="usi-action-row">
        <Button
          type="primary"
          icon={<CloudDownloadOutlined />}
          onClick={onImport}
          loading={jiraLoading}
          disabled={hasJiraImported || isFileUploaded || selectedProject}
          size="large"
        >
          Import Stories from Jira
        </Button>

        {isJiraImport && (
          <Button
            icon={<ReloadOutlined />}
            onClick={onRefresh}
            loading={refreshLoading}
            size="large"
          >
            Refresh from Jira
          </Button>
        )}
      </div>

      {hasJiraImported && (
        <div className="usi-success-strip">
          <CheckCircleFilled style={{ color: "#16a34a", fontSize: 15 }} />
          Stories imported successfully. Use Refresh to sync changes.
        </div>
      )}
    </div>
  );
}
