"use client";

import React from "react";
import {
  Alert,
  Button,
  Form,
  Input,
  message,
  Modal,
  Select,
  Table,
  Tag,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import type { TextAreaRef } from "antd/es/input/TextArea";
import type { GenerationSettings } from "@/types/testGenerator";
import {
  CustomStdField,
  CustomColumn,
  MANDATORY_TITLE,
  allStandardFieldOptions,
  StandardFieldSelectOption,
  CustomTableRow,
} from "@/types/testGenerator";
import { useRef } from "react";

const MANDATORY_FIELDS: CustomStdField[] = [MANDATORY_TITLE.value];

const STANDARD_FIELD_MAP = Object.fromEntries(
  allStandardFieldOptions.map((o) => [o.value, o]),
) as Record<CustomStdField, (typeof allStandardFieldOptions)[number]>;

const STANDARD_FIELD_LABEL_MAP = Object.fromEntries(
  allStandardFieldOptions.map((o) => [o.label, o]),
) as Record<string, (typeof allStandardFieldOptions)[number]>;

export type CustomSettingProps = {
  settings: GenerationSettings;
  onSettingsChange: (settings: GenerationSettings) => void;
};

function buildCustomFieldsPayload(
  standardFields: CustomStdField[],
  customColumns: CustomColumn[],
) {
  return [
    ...standardFields.map((field) => {
      const option = STANDARD_FIELD_MAP[field];
      return {
        name: option?.label ?? field,
        description: option?.description ?? "",
      };
    }),
    ...customColumns.map((column) => ({
      name: column.name,
      description: column.description,
    })),
  ];
}

export default function CustomSetting({
  settings,
  onSettingsChange,
}: CustomSettingProps) {
  // Derive standard-field keys from settings.customFields (no local state needed).
  const standardFields = React.useMemo<CustomStdField[]>(() => {
    const fields = settings.customFields ?? [];
    const fromSettings = fields
      .map((field) => {
        if (field.name === MANDATORY_TITLE.label) return MANDATORY_TITLE.value;
        return STANDARD_FIELD_LABEL_MAP[field.name]?.value ?? undefined;
      })
      .filter((v): v is CustomStdField => Boolean(v));
    return Array.from(
      new Set<CustomStdField>([...MANDATORY_FIELDS, ...fromSettings]),
    );
  }, [settings.customFields]);

  // Derive custom (non-standard) columns from settings.customFields.
  const customColumns = React.useMemo<CustomColumn[]>(() => {
    const fields = settings.customFields ?? [];
    return fields
      .filter((field) => {
        const isTitle = field.name === MANDATORY_TITLE.label;
        const isStandard = Boolean(STANDARD_FIELD_LABEL_MAP[field.name]);
        return !isTitle && !isStandard;
      })
      .map((field) => ({
        id: `custom_${field.name}`,
        name: field.name,
        description: field.description,
      }));
  }, [settings.customFields]);

  const MAX_FIELDS = 10;

  const [isAddModalOpen, setIsAddModalOpen] = React.useState(false);
  const [modalForm] = Form.useForm();
  const [formError, setFormError] = React.useState<string | null>(null);

  const totalSelectedCountForLimit =
    standardFields.length + customColumns.length;

  function resetAddModal() {
    setFormError(null);
    modalForm.resetFields();
  }

  function showAddModal() {
    resetAddModal();
    setIsAddModalOpen(true);
  }

  function closeAddModal() {
    setIsAddModalOpen(false);
  }

  const settingsRef = React.useRef(settings);
  React.useLayoutEffect(() => {
    settingsRef.current = settings;
  });

  const updateSettingsFields = React.useCallback(
    (
      nextStandardFields: CustomStdField[],
      nextCustomColumns: CustomColumn[],
    ) => {
      onSettingsChange({
        ...settingsRef.current,
        customFields: buildCustomFieldsPayload(
          nextStandardFields,
          nextCustomColumns,
        ),
      });
    },
    [onSettingsChange],
  );

  function handleAddCustomColumn(values: {
    name?: string;
    description?: string;
  }) {
    const name = (values.name ?? "").trim();
    const description = (values.description ?? "").trim();

    if (!name) return;

    const normalizedName = normalizeColumnName(name);

    const standardLabels = new Set(
      allStandardFieldOptions.map((option) =>
        normalizeColumnName(option.label),
      ),
    );

    if (standardLabels.has(normalizedName)) {
      setFormError(
        `"${name}" is a standard field. Select it from the dropdown above instead.`,
      );
      return;
    }

    const existingLower = new Map<string, string>([
      ...standardFields.map((f) => {
        const opt = STANDARD_FIELD_MAP[f];
        const label = opt?.label ?? f;
        return [normalizeColumnName(label), label] as const;
      }),
      ...customColumns.map(
        (c) => [normalizeColumnName(c.name), c.name] as const,
      ),
    ]);

    const conflictingName = existingLower.get(normalizedName);
    if (conflictingName) {
      setFormError(`Column name already exists: ${conflictingName}`);
      return;
    }

    if (customColumns.length + standardFields.length >= MAX_FIELDS) {
      setFormError(`Maximum of ${MAX_FIELDS} fields allowed.`);
      return;
    }

    const next: CustomColumn = {
      id: `custom_${normalizedName}`,
      name,
      description,
    };

    const nextCustomColumns = [...customColumns, next];
    updateSettingsFields(standardFields, nextCustomColumns);
    setIsAddModalOpen(false);
  }

  const normalizeColumnName = (name: string): string =>
    name.trim().replace(/\s+/g, " ").toLowerCase();

  const columns: ColumnsType<CustomTableRow> = React.useMemo(
    () => [
      {
        title: "Name",
        dataIndex: "name",
        key: "name",
      },
      {
        title: "Description",
        dataIndex: "description",
        key: "description",
      },
      {
        title: "",
        key: "actions",
        width: 60,
        align: "center",
        render: (_: unknown, record: { id: string; isCustom?: boolean }) => {
          if (!record.isCustom) return null;
          return (
            <Button
              type="text"
              danger
              icon={<DeleteOutlined />}
              onClick={() => {
                const nextCustomColumns = customColumns.filter(
                  (c) => c.id !== record.id,
                );
                updateSettingsFields(standardFields, nextCustomColumns);
              }}
            />
          );
        },
      },
    ],
    [customColumns, standardFields, updateSettingsFields],
  );

  const dataSource = React.useMemo<CustomTableRow[]>(() => {
    const fields = settings.customFields ?? [];

    // Check if mandatory Title is already in settings.customFields
    const hasTitle = fields.some((f) => f.name === MANDATORY_TITLE.label);

    const mandatoryRows: CustomTableRow[] = [];
    if (!hasTitle) {
      mandatoryRows.push({
        id: `std_${MANDATORY_TITLE.value}`,
        name: MANDATORY_TITLE.label,
        description: MANDATORY_TITLE.description,
        isCustom: false,
      });
    }

    const mappedFields = fields.map((f) => {
      const isTitle = f.name === MANDATORY_TITLE.label;
      const stdEntry = STANDARD_FIELD_LABEL_MAP[f.name];
      const isStandard = isTitle || Boolean(stdEntry);
      return {
        id: isStandard
          ? `std_${stdEntry?.value ?? MANDATORY_TITLE.value}`
          : `custom_${f.name}`,
        name: f.name,
        description: f.description,
        isCustom: !isStandard,
      };
    });

    return [...mandatoryRows, ...mappedFields];
  }, [settings.customFields]);

  const descriptionRef = React.useRef<TextAreaRef | null>(null);
  return (
    <>
      <div
        style={{
          borderRadius: 10,
          background: "#fff",
          border: "1px solid #f0f0f0",
          padding: 12,
        }}
      >
        <div
          style={{
            fontSize: 14,
            fontWeight: 600,
            marginBottom: 8,
            color: "#000",
          }}
        >
          Custom Test Case Configuration
        </div>

        <div
          style={{
            fontSize: 12,
            color: "#6b7280",
            marginBottom: 6,
            fontWeight: 600,
          }}
        >
          Standard Fields
        </div>

        <>
          <div style={{ height: 12 }} />

          <Select
            mode="multiple"
            style={{ width: "100%" }}
            placeholder="Select optional standard fields"
            value={standardFields}
            onChange={(values) => {
              const selected = values as CustomStdField[];

              const mandatorySet = new Set<CustomStdField>(MANDATORY_FIELDS);
              const mandatorySelected = MANDATORY_FIELDS;

              const maxSelected = Math.max(
                0,
                MAX_FIELDS - customColumns.length,
              );
              if (selected.length > maxSelected) {
                message.warning(`Maximum of ${MAX_FIELDS} fields allowed.`);
              }
              const capped = selected.slice(0, maxSelected) as CustomStdField[];

              const nextNonMandatory = capped.filter(
                (v) => !mandatorySet.has(v),
              );

              const nextStandardFields = [
                ...mandatorySelected,
                ...nextNonMandatory,
              ];
              updateSettingsFields(nextStandardFields, customColumns);
            }}
            optionLabelProp="label"
            maxTagCount="responsive"
            options={allStandardFieldOptions.map((opt) => {
              const isMandatory = MANDATORY_FIELDS.includes(
                opt.value as CustomStdField,
              );

              const remaining =
                MAX_FIELDS - (standardFields.length + customColumns.length);

              const isSelected = standardFields.includes(
                opt.value as CustomStdField,
              );

              const disabled = isMandatory || (remaining <= 0 && !isSelected);

              return {
                value: opt.value as CustomStdField,
                label: opt.label,
                description: opt.description,
                disabled,
              } satisfies StandardFieldSelectOption;
            })}
            optionRender={(option) => {
              const op = option.data as unknown as StandardFieldSelectOption;

              return (
                <div style={{ display: "flex", flexDirection: "column" }}>
                  <span>{op?.label}</span>
                  <span style={{ fontSize: 12, color: "#6b7280" }}>
                    {op?.description}
                  </span>
                </div>
              );
            }}
          />

          <div style={{ marginTop: 8, fontSize: 12, color: "#9ca3af" }}>
            Selected standard fields (and their description) appear in the table
            below.
          </div>

          <div style={{ height: 16 }} />

          <div
            style={{
              fontSize: 12,
              color: "#6b7280",
              marginBottom: 8,
              fontWeight: 600,
            }}
          >
            Custom Columns
          </div>

          <Table
            size="small"
            rowKey={(r: CustomTableRow) => r.id}
            columns={columns}
            dataSource={dataSource}
            pagination={false}
          />

          <div style={{ marginBottom: 10, marginTop: 12 }}>
            <Button
              icon={<PlusOutlined />}
              onClick={showAddModal}
              disabled={totalSelectedCountForLimit >= MAX_FIELDS}
            >
              Add Custom Column
            </Button>

            <div style={{ marginTop: 8 }}>
              <Tag
                color={
                  totalSelectedCountForLimit >= MAX_FIELDS
                    ? "warning"
                    : "default"
                }
                style={{ border: 0 }}
              >
                {totalSelectedCountForLimit}/{MAX_FIELDS} fields selected
              </Tag>
            </div>
          </div>
        </>
      </div>

      <Modal
        title="Add Custom Column"
        open={isAddModalOpen}
        onCancel={closeAddModal}
        okText="Add"
        cancelText="Cancel"
        onOk={() => {
          modalForm
            .validateFields()
            .then((values) => {
              void handleAddCustomColumn(
                values as { name?: string; description?: string },
              );
            })
            .catch((err: unknown) => {
              const isAntValidationError =
                typeof err === "object" &&
                err !== null &&
                "errorFields" in err &&
                Array.isArray((err as Record<string, unknown>).errorFields);
              if (!isAntValidationError) {
                console.error(
                  "Unexpected error in modal form submission:",
                  err,
                );
              }
            });
        }}
      >
        <Form
          form={modalForm}
          layout="vertical"
          onFinish={handleAddCustomColumn}
        >
          {formError && (
            <div style={{ marginTop: 8 }}>
              <Alert type="error" showIcon title={formError} />
            </div>
          )}
          <Form.Item
            label="Column Name"
            name="name"
            rules={[{ required: true, message: "Column name is required" }]}
          >
            <Input.TextArea
              placeholder="e.g., Risk Category"
              maxLength={40}
              showCount={true}
              rows={1}
              autoSize={false}
              style={{ resize: "none" }}
              onChange={() => setFormError(null)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  descriptionRef.current?.focus();
                }
              }}
            />
          </Form.Item>

          <Form.Item
            label="Description"
            name="description"
            rules={[{ required: true, message: "Description is required" }]}
          >
            <Input.TextArea
              ref={descriptionRef}
              placeholder="e.g., Risk classification..."
              maxLength={200}
              showCount={true}
              autoSize={{ minRows: 3, maxRows: 5 }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  modalForm.submit();
                }
              }}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
