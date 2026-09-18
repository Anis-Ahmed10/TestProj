import React, { useEffect, useRef, useState } from "react";
import type { ColumnType } from "antd/es/table";
import { Button, Table, Space, App } from "antd";
import {
  PlusOutlined,
  LoadingOutlined,
  FileOutlined,
  DeleteOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  FileExcelOutlined,
} from "@ant-design/icons";
import {
  uploadDocument,
  fetchDocuments,
  deleteDocument,
} from "@/services/documentService";
import { ACCEPTED_FILE_TYPES, MAX_SIZE_MB, PERMISSIONS } from "@/constants";
import { useAppDispatch, useAppSelector } from "@/store/store";
import { usePermissions } from "@/hooks/usePermissions";
import {
  addDocumentForPath,
  removeDocumentForPath,
  updateDocumentForPath,
  setDocumentsForPath,
  DocumentItem,
} from "@/store/slices/documentSlice";

function getFileIcon(fileName: string) {
  const ext = fileName.split(".").pop()?.toLowerCase() ?? "";
  switch (true) {
    case ext === "pdf":
      return <FilePdfOutlined style={{ color: "#ef4444", fontSize: 16 }} />;
    case ["docx", "doc"].includes(ext):
      return <FileWordOutlined style={{ color: "#2563eb", fontSize: 16 }} />;
    case ["xlsx", "xls"].includes(ext):
      return <FileExcelOutlined style={{ color: "#16a34a", fontSize: 16 }} />;
    default:
      return <FileOutlined style={{ color: "#6b7280", fontSize: 16 }} />;
  }
}

interface DocumentsSectionProps {
  folderPath: string;
  entityId: string;
  heading?: string;
  compactEmpty?: boolean;
  emptyDescription?: string;
}

const EMPTY_DOCUMENTS: DocumentItem[] = [];

function formatBytes(bytes: number, decimals = 2) {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
}

function getFileTypeName(fileName: string): string {
  const ext = fileName.split(".").pop()?.toLowerCase() ?? "";
  switch (ext) {
    case "pdf":
      return "PDF Document (.pdf)";
    case "docx":
      return "Word Document (.docx)";
    case "doc":
      return "Word Document (.doc)";
    case "xlsx":
      return "Excel Spreadsheet (.xlsx)";
    case "xls":
      return "Excel Spreadsheet (.xls)";
    case "csv":
      return "Comma-Separated Values (.csv)";
    case "txt":
      return "Text File (.txt)";
    default:
      return `${ext.toUpperCase()} File`;
  }
}

export default function DocumentsSection({
  folderPath,
  entityId,
  heading = "Documents",
  compactEmpty = false,
  emptyDescription = "Upload documents — SOWs, specs, reports, and more.",
}: DocumentsSectionProps) {
  const { message, modal } = App.useApp();
  const dispatch = useAppDispatch();
  const { hasPermission } = usePermissions();
  const canDelete = hasPermission(PERMISSIONS.DOCUMENT_DELETE);
  const documents = useAppSelector(
    (state) => state.documents.documentsByPath[folderPath] ?? EMPTY_DOCUMENTS,
  );
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!entityId) return;
    let cancelled = false;
    setLoading(true);
    fetchDocuments(entityId)
      .then((docs) => {
        if (cancelled) return;
        dispatch(
          setDocumentsForPath({
            folderPath,
            documents: docs.map((d) => ({
              id: d.id,
              name: d.fileName.replace(/\.[^/.]+$/, ""),
              fileName: d.fileName,
            })),
          }),
        );
      })
      .catch((error) => {
        if (!cancelled) {
          console.error("Failed to load documents:", error);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [entityId, folderPath]);

  function handleAddClick() {
    fileInputRef.current?.click();
  }

  async function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const validFiles: File[] = [];
    for (const file of Array.from(files)) {
      const ext = file.name.match(/\.[^/.]+$/)?.[0]?.toLowerCase() ?? "";
      if (!ACCEPTED_FILE_TYPES.includes(ext)) {
        message.error(
          `"${file.name}" is not a supported file type. Please upload PDF, DOCX, XLSX, CSV or TXT files.`,
        );
        continue;
      }

      if (file.size > MAX_SIZE_MB * 1024 * 1024) {
        message.error(
          `"${file.name}" exceeds ${MAX_SIZE_MB}MB. Please upload a smaller file.`,
        );
        continue;
      }

      validFiles.push(file);
    }

    if (validFiles.length > 0) {
      let isSubmitting = false;
      modal.confirm({
        title: "Confirm Document Upload",
        width: 500,
        okText: "Upload/Confirm",
        cancelText: "Cancel",
        okButtonProps: {
          style: { backgroundColor: "#1f3333", borderColor: "#1f3333" },
        },
        content: (
          <div className="cdp-confirm-modal-content">
            <p className="cdp-confirm-modal-desc">
              {validFiles.length > 1
                ? "Are you sure you want to upload these files? They will be sanitized before upload."
                : "Are you sure you want to upload this file? It will be sanitized before upload."}
            </p>
            <div className="cdp-confirm-table-wrapper">
              <table className="cdp-confirm-table">
                <thead>
                  <tr>
                    <th style={{ width: "60%" }}>File Name</th>
                    <th>Type</th>
                    <th className="align-right">Size</th>
                  </tr>
                </thead>
                <tbody>
                  {validFiles.map((file, idx) => (
                    <tr key={idx}>
                      <td className="file-name">{file.name}</td>
                      <td className="file-type">
                        {getFileTypeName(file.name).split(" (")[0]}
                      </td>
                      <td className="file-size">{formatBytes(file.size)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ),
        onOk() {
          if (isSubmitting) return;
          isSubmitting = true;
          return (async () => {
            try {
              for (const file of validFiles) {
                await uploadFile(file);
              }
            } finally {
              isSubmitting = false;
            }
          })();
        },
      });
    }

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  async function uploadFile(file: File) {
    const placeholderId = `uploading-${Date.now()}-${file.name}`;

    dispatch(
      addDocumentForPath({
        folderPath,
        document: {
          id: placeholderId,
          name: file.name.replace(/\.[^/.]+$/, ""),
          fileName: file.name,
          isUploading: true,
        },
      }),
    );

    try {
      const result = await uploadDocument(file, folderPath, entityId);
      if (result.isDuplicate) {
        dispatch(removeDocumentForPath({ folderPath, id: placeholderId }));
        message.info(`"${result.title}" already exists. Upload skipped.`);
      } else {
        message.success(`"${result.title}" uploaded successfully.`);

        dispatch(
          updateDocumentForPath({
            folderPath,
            id: placeholderId,
            update: {
              id: result.documentId ?? placeholderId,
              name: result.title,
              fileName: result.fileName,
              isUploading: false,
            },
          }),
        );
      }
    } catch (error) {
      dispatch(removeDocumentForPath({ folderPath, id: placeholderId }));
      message.error(
        error instanceof Error
          ? `Upload failed: ${error.message}`
          : `Failed to upload "${file.name}".`,
      );
    }
  }

  function handleRemove(record: DocumentItem) {
    modal.confirm({
      title: "Delete Document?",
      okText: "Delete/Confirm",
      cancelText: "Cancel",
      okButtonProps: {
        danger: true,
      },
      content: (
        <div className="cdp-confirm-modal-content">
          <p className="cdp-confirm-modal-desc">
            Are you sure you want to delete this document from the library?
          </p>
          <div className="cdp-confirm-table-wrapper">
            <table className="cdp-confirm-table">
              <thead>
                <tr>
                  <th style={{ width: "70%" }}>File Name</th>
                  <th>Type</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="file-name">
                    {record.fileName || record.name}
                  </td>
                  <td className="file-type">
                    {
                      getFileTypeName(record.fileName || record.name).split(
                        " (",
                      )[0]
                    }
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div className="cdp-confirm-warn-box">
            This action is permanent and cannot be undone.
          </div>
        </div>
      ),
      async onOk() {
        try {
          await deleteDocument(record.id, entityId);
          dispatch(removeDocumentForPath({ folderPath, id: record.id }));
          message.success(`"${record.name}" deleted successfully.`);
        } catch (error) {
          message.error(
            error instanceof Error
              ? `Deletion failed: ${error.message}`
              : `Failed to delete "${record.name}".`,
          );
        }
      },
    });
  }

  const columns: ColumnType<DocumentItem>[] = [
    {
      title: "NAME",
      dataIndex: "fileName",
      key: "name",
      render: (fileName: string, record: DocumentItem) => (
        <Space size={8} align="start">
          {record.isUploading ? (
            <LoadingOutlined style={{ fontSize: 16 }} />
          ) : (
            getFileIcon(fileName ?? "")
          )}
          <div>
            <div className="doc-name">{record.name}</div>
          </div>
        </Space>
      ),
    },
    {
      title: "",
      key: "actions",
      width: 48,
      render: (_: unknown, record: DocumentItem) => (
        <Button
          type="text"
          icon={<DeleteOutlined className="doc-delete-icon" />}
          size="small"
          disabled={(record.isUploading ?? false) || !canDelete}
          onClick={() => handleRemove(record)}
          title={
            canDelete
              ? "Remove document"
              : "You do not have permission to delete documents"
          }
        />
      ),
    },
  ];

  return (
    <div className="docs-section">
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPTED_FILE_TYPES.join(",")}
        multiple
        style={{ display: "none" }}
        onChange={handleFileSelected}
      />

      <div className="workspace__section-header">
        <h2 className="workspace__section-title">
          {heading}
          {documents.length > 0 && (
            <span className="workspace__section-count">{documents.length}</span>
          )}
        </h2>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          className="doc-add-btn"
          onClick={handleAddClick}
        >
          Add Document
        </Button>
      </div>

      {documents.length === 0 ? (
        loading ? (
          <div className="doc-empty-compact">Loading documents…</div>
        ) : compactEmpty ? (
          <div className="doc-empty-compact">No documents yet</div>
        ) : (
          <div className="doc-empty">
            <FileOutlined className="doc-empty-icon" />
            <p className="doc-empty-title">No documents yet</p>
            <p className="doc-empty-description">{emptyDescription}</p>
          </div>
        )
      ) : (
        <Table<DocumentItem>
          className="project-tabs-table"
          columns={columns}
          dataSource={documents}
          rowKey="id"
          pagination={false}
          size="small"
        />
      )}
    </div>
  );
}
