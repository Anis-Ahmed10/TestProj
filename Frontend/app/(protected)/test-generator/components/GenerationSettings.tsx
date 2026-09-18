"use client";
import React from "react";
import { Card, Select } from "antd";
import { SettingOutlined } from "@ant-design/icons";

import {
  CoverageDepth,
  GenerationSettings,
  PriorityAssignment,
  TEST_CASE_FORMATS,
  TestCaseFormat,
} from "@/types/testGenerator";

import CustomSetting from "./CustomSetting";

import { coverageOptions, formatOptions, priorityOptions } from "@/constants";

const { Option } = Select;

type GenerationSettingsProps = {
  settings: GenerationSettings;
  onSettingsChange: (settings: GenerationSettings) => void;
};

type SettingRowProps = {
  label: string;
  options: string[];
  value: string;
  onChange: (v: string) => void;
};

function SettingRow({ label, options, value, onChange }: SettingRowProps) {
  return (
    <div>
      <div
        style={{
          fontSize: 12,
          color: "#6b7280",
          marginBottom: 6,
        }}
      >
        {label}
      </div>

      <Select value={value} onChange={onChange} style={{ width: "100%" }}>
        {options.map((opt) => (
          <Option key={opt} value={opt}>
            {opt}
          </Option>
        ))}
      </Select>
    </div>
  );
}

export default function GenerationSettingsPanel({
  settings,
  onSettingsChange,
}: GenerationSettingsProps) {
  return (
    <>
      <Card
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <SettingOutlined style={{ color: "#6b7280" }} />
            <span style={{ fontSize: 14, fontWeight: 600 }}>
              Generation Settings
            </span>
          </div>
        }
        style={{ borderRadius: 10 }}
      >
        <div
          style={{
            display: "flex",
            gap: 16,
            alignItems: "flex-end",
            flexWrap: "wrap",
          }}
        >
          <div style={{ flex: 1, minWidth: 180 }}>
            <SettingRow
              label="Test Case Format"
              options={formatOptions}
              value={settings.format}
              onChange={(v) => {
                const nextSettings: GenerationSettings = {
                  ...settings,
                  format: v as TestCaseFormat,
                };

                if (
                  v !== TEST_CASE_FORMATS.CUSTOM ||
                  !nextSettings.customFields
                ) {
                  nextSettings.customFields = [];
                }

                onSettingsChange(nextSettings);
              }}
            />
          </div>

          <div style={{ flex: 1, minWidth: 180 }}>
            <SettingRow
              label="Coverage Depth"
              options={coverageOptions}
              value={settings.coverage}
              onChange={(v) =>
                onSettingsChange({
                  ...settings,
                  coverage: v as CoverageDepth,
                })
              }
            />
          </div>

          <div style={{ flex: 1, minWidth: 180 }}>
            <SettingRow
              label="Priority Assignment"
              options={priorityOptions}
              value={settings.priority}
              onChange={(v) =>
                onSettingsChange({
                  ...settings,
                  priority: v as PriorityAssignment,
                })
              }
            />
          </div>
        </div>

        <div
          style={{
            marginTop: 4,
            paddingTop: 10,
            borderTop: "1px solid #e5e7eb",
            fontSize: 12,
            color: "#9ca3af",
          }}
        >
          Settings apply to the next generation run. Change anytime between
          runs.
        </div>
      </Card>

      {settings.format === (TEST_CASE_FORMATS.CUSTOM as TestCaseFormat) && (
        <CustomSetting
          settings={settings}
          onSettingsChange={onSettingsChange}
        />
      )}
    </>
  );
}
