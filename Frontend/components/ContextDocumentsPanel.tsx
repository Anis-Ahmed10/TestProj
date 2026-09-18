"use client";

import React, { useEffect, useRef, useState } from "react";
import { Checkbox, Empty, Modal, Spin, App } from "antd";
import {
  DeleteOutlined,
  FileTextOutlined,
  FolderOpenOutlined,
  LoadingOutlined,
} from "@ant-design/icons";
import { BackendProject } from "@/types/project";
import { ContextDocumentRequest } from "@/types/testGenerator";
import {
  uploadDocument,
  fetchDocuments,
  type FetchedDocument,
} from "@/services/documentService";
import { ACCEPTED_FILE_TYPES, MAX_SIZE_MB } from "@/constants";
import "@/assets/css/contextDocumentsPanel.css";

export function getFileExtension(fileName: string): string {
  const match = fileName.match(/\.[^/.]+$/);
  return match ? match[0].toLowerCase() : "";
}

type DocLevel = "client" | "programme" | "project";

export interface BrowsableDoc extends FetchedDocument {
  level: DocLevel;
}

export function BrowseDocumentsModal({
  open,
  onClose,
  selectedProject,
  existingDocumentIds,
  onAdd,
}: {
  open: boolean;
  onClose: () => void;
  selectedProject: BackendProject | null;
  existingDocumentIds: Set<string>;
  onAdd: (docs: BrowsableDoc[]) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [docsByLevel, setDocsByLevel] = useState<
    Record<DocLevel, BrowsableDoc[]>
  >({ client: [], programme: [], project: [] });
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!open || !selectedProject) return;
    let cancelled = false;
    setLoading(true);
    setCheckedIds(new Set());

    const levels: { level: DocLevel; entityId: string }[] = [
      { level: "client", entityId: selectedProject.client_id },
      { level: "programme", entityId: selectedProject.programme_id },
      { level: "project", entityId: selectedProject.id },
    ];

    Promise.all(
      levels.map(({ level, entityId }) =>
        entityId
          ? fetchDocuments(entityId)
              .then((docs) => ({ level, docs }))
              .catch(() => ({ level, docs: [] as FetchedDocument[] }))
          : Promise.resolve({ level, docs: [] as FetchedDocument[] }),
      ),
    ).then((results) => {
      if (cancelled) return;
      const next: Record<DocLevel, BrowsableDoc[]> = {
        client: [],
        programme: [],
        project: [],
      };
      results.forEach(({ level, docs }) => {
        next[level] = docs.map((d) => ({ ...d, level }));
      });
      setDocsByLevel(next);
      setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [open, selectedProject]);

  const allDocs = [
    ...docsByLevel.client,
    ...docsByLevel.programme,
    ...docsByLevel.project,
  ];

  const toggle = (id: string) => {
    setCheckedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleAdd = () => {
    const selected = allDocs.filter((doc) => checkedIds.has(doc.id));
    onAdd(selected);
    onClose();
  };

  const renderGroup = (title: string, docs: BrowsableDoc[]) => {
    if (docs.length === 0) return null;
    return (
      <div className="cdp-browse-group">
        <div className="cdp-browse-group-title">{title}</div>
        <div className="cdp-browse-group-list">
          {docs.map((doc) => {
            const alreadyAdded = existingDocumentIds.has(doc.id);
            return (
              <label
                key={`${doc.level}-${doc.id}`}
                className={`cdp-browse-doc-row ${
                  alreadyAdded ? "cdp-browse-doc-row--added" : ""
                }`}
              >
                <Checkbox
                  checked={alreadyAdded || checkedIds.has(doc.id)}
                  disabled={alreadyAdded}
                  onChange={() => toggle(doc.id)}
                />
                <FileTextOutlined className="cdp-browse-doc-icon" />
                <span className="cdp-browse-doc-name">
                  {doc.fileName}
                  {alreadyAdded && (
                    <span className="cdp-browse-doc-added-tag">
                      {" "}
                      — already added
                    </span>
                  )}
                </span>
              </label>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <Modal
      title="Add documents from Client / Programme / Project"
      open={open}
      onCancel={onClose}
      onOk={handleAdd}
      okText={`Add ${checkedIds.size > 0 ? `(${checkedIds.size})` : ""}`}
      okButtonProps={{ disabled: checkedIds.size === 0 }}
      width={560}
    >
      {!selectedProject ? (
        <Empty description="Select a project first" />
      ) : loading ? (
        <div className="cdp-browse-loading">
          <Spin />
        </div>
      ) : allDocs.length === 0 ? (
        <Empty description="No documents found for this client, programme, or project" />
      ) : (
        <div className="cdp-browse-doc-list">
          {renderGroup("Client Documents", docsByLevel.client)}
          {renderGroup("Programme Documents", docsByLevel.programme)}
          {renderGroup("Project Documents", docsByLevel.project)}
        </div>
      )}
    </Modal>
  );
}

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

export function useContextDocumentUpload({
  selectedProject,
  contextDocs,
  setContextDocs,
  autoFetch = false,
  folderSuffix,
  onError,
  onNotice,
}: {
  selectedProject: BackendProject | null;
  contextDocs: ContextDocumentRequest[];
  setContextDocs: (docs: ContextDocumentRequest[]) => void;
  autoFetch?: boolean;
  folderSuffix?: string;
  onError?: (msg: string) => void;
  onNotice?: (msg: string, kind?: "success" | "info") => void;
}) {
  const { modal } = App.useApp();
  const [uploadingFileNames, setUploadingFileNames] = useState<Set<string>>(
    new Set(),
  );
  const [fetching, setFetching] = useState(false);
  const contextDocsRef = useRef(contextDocs);
  contextDocsRef.current = contextDocs;

  useEffect(() => {
    if (!autoFetch) return;
    if (!selectedProject) {
      setContextDocs([]);
      return;
    }
    let cancelled = false;
    setFetching(true);
    fetchDocuments(selectedProject.id)
      .then((docs) => {
        if (cancelled) return;
        setContextDocs(
          docs.map((d) => ({
            documentId: d.id,
            title: d.fileName.replace(/\.[^/.]+$/, ""),
            fileName: d.fileName,
          })),
        );
      })
      .catch((err) => {
        if (!cancelled) {
          onError?.(
            err instanceof Error
              ? `Could not load context documents: ${err.message}`
              : "Could not load context documents.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setFetching(false);
      });
    return () => {
      cancelled = true;
    };
  }, [autoFetch, selectedProject?.id]);

  const handleUploadDoc = async (file: File) => {
    if (!selectedProject) {
      onError?.("Please select a project before uploading documents.");
      return;
    }

    const placeholderId = `uploading-${Date.now()}-${file.name}`;
    const placeholderDoc: ContextDocumentRequest = {
      documentId: placeholderId,
      title: file.name.replace(/\.[^/.]+$/, ""),
      fileName: file.name,
    };
    setContextDocs([...contextDocsRef.current, placeholderDoc]);
    setUploadingFileNames((prev) => new Set([...prev, file.name]));

    try {
      const sanitize = (str: string) => str.replace(/ /g, "_");
      const folderParts = [
        selectedProject.client_name,
        selectedProject.programme_name,
        selectedProject.name,
      ];
      if (folderSuffix) folderParts.push(folderSuffix);
      const folderPath = folderParts.map(sanitize).join("/");

      const result = await uploadDocument(file, folderPath, selectedProject.id);

      const withoutPlaceholder = contextDocsRef.current.filter(
        (d) => d.documentId !== placeholderId,
      );

      if (result.isDuplicate) {
        // Already uploaded for this project — drop the optimistic row instead of
        // adding a second entry for the same document.
        setContextDocs(withoutPlaceholder);
        onNotice?.(`"${result.title}" already exists. Upload skipped.`, "info");
      } else {
        setContextDocs(
          withoutPlaceholder.concat({
            documentId: result.documentId ?? placeholderId,
            title: result.title,
            s3Key: result.s3Key,
            fileName: result.fileName,
          }),
        );
        onNotice?.(`"${result.title}" uploaded successfully.`);
      }
    } catch (error) {
      setContextDocs(
        contextDocsRef.current.filter((d) => d.documentId !== placeholderId),
      );
      onError?.(
        error instanceof Error
          ? `Upload failed: ${error.message}`
          : `Failed to upload "${file.name}".`,
      );
    } finally {
      setUploadingFileNames((prev) => {
        const next = new Set(prev);
        next.delete(file.name);
        return next;
      });
    }
  };

  const handleFilesSelected = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const validFiles: File[] = [];
    for (const file of Array.from(files)) {
      const ext = getFileExtension(file.name);
      if (!ACCEPTED_FILE_TYPES.includes(ext)) {
        onError?.(
          `"${file.name}" is not a supported file type. Please upload PDF, DOCX, XLSX, CSV or TXT files.`,
        );
        continue;
      }
      if (file.size > MAX_SIZE_MB * 1024 * 1024) {
        onError?.(
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
                await handleUploadDoc(file);
              }
            } finally {
              isSubmitting = false;
            }
          })();
        },
      });
    }
  };

  const handleRemoveDoc = (index: number) => {
    const doc = contextDocsRef.current[index];
    if (!doc) return;

    const docName = doc.title || doc.fileName;

    modal.confirm({
      title: "Remove Document Context?",
      okText: "Remove Context",
      cancelText: "Cancel",
      okButtonProps: {
        danger: true,
      },
      content: (
        <div className="cdp-confirm-modal-content">
          <p className="cdp-confirm-modal-desc">
            Are you sure you want to remove <strong>{docName}</strong> document
            from the active AI context?
          </p>
          <p className="cdp-confirm-modal-desc">
            <strong>
              This document will not be sent to the LLM for this operation.
            </strong>
          </p>
        </div>
      ),
      onOk() {
        setContextDocs(contextDocsRef.current.filter((_, i) => i !== index));
      },
    });
  };

  const handleAddExistingDocs = (docs: BrowsableDoc[]) => {
    const existingIds = new Set(
      contextDocsRef.current.map((d) => d.documentId),
    );
    const additions = docs
      .filter((d) => !existingIds.has(d.id))
      .map((d) => ({
        documentId: d.id,
        title: d.fileName.replace(/\.[^/.]+$/, ""),
        fileName: d.fileName,
      }));
    if (additions.length > 0) {
      setContextDocs([...contextDocsRef.current, ...additions]);
    }
  };

  return {
    uploadingFileNames,
    fetching,
    handleFilesSelected,
    handleRemoveDoc,
    handleAddExistingDocs,
  };
}

export function ContextDocumentsList({
  docs,
  uploadingFileNames,
  fetching,
  selectedProject,
  onRemove,
  onAddClick,
  onBrowseClick,
  itemClassName = "",
  addRowClassName = "",
  addButtonClassName = "",
  addButtonDisabledClassName = "",
  emptyAddLabel = "Add a document",
  moreAddLabel = "Add another document",
}: {
  docs: ContextDocumentRequest[];
  uploadingFileNames: Set<string>;
  fetching?: boolean;
  selectedProject: BackendProject | null;
  onRemove: (index: number) => void;
  onAddClick: () => void;
  onBrowseClick: () => void;
  itemClassName?: string;
  addRowClassName?: string;
  addButtonClassName?: string;
  addButtonDisabledClassName?: string;
  emptyAddLabel?: string;
  moreAddLabel?: string;
}) {
  return (
    <>
      {fetching ? (
        <div className="cdp-loading-row">
          <Spin size="small" /> Loading project documents…
        </div>
      ) : (
        docs.map((doc, index) => {
          const isUploading = doc.fileName
            ? uploadingFileNames.has(doc.fileName)
            : false;
          return (
            <div className={itemClassName} key={doc.documentId || index}>
              {isUploading ? (
                <LoadingOutlined className="cdp-item-icon--uploading" />
              ) : (
                <FileTextOutlined />
              )}
              <span className="cdp-item-name">
                {doc.title}
                {isUploading && (
                  <span className="cdp-item-uploading-suffix">
                    {" "}
                    - uploading…
                  </span>
                )}
              </span>
              <button
                type="button"
                onClick={() => onRemove(index)}
                disabled={isUploading}
                aria-label={`Remove ${doc.title}`}
                className={
                  isUploading ? "cdp-item-remove--disabled" : "cdp-item-remove"
                }
              >
                <DeleteOutlined />
              </button>
            </div>
          );
        })
      )}

      <div className="cdp-add-row">
        <button
          type="button"
          className={`${addRowClassName} ${addButtonClassName} cdp-add-btn`}
          onClick={onAddClick}
          aria-label={docs.length === 0 ? emptyAddLabel : moreAddLabel}
        >
          <FileTextOutlined />{" "}
          {docs.length === 0 ? emptyAddLabel : moreAddLabel}
        </button>
        <button
          type="button"
          disabled={!selectedProject}
          className={`${addRowClassName} ${
            !selectedProject ? addButtonDisabledClassName : addButtonClassName
          } ${selectedProject ? "cdp-add-btn" : "cdp-add-btn--disabled"}`}
          onClick={onBrowseClick}
          aria-label="Add from Client / Programme / Project"
        >
          <FolderOpenOutlined /> Add from Client / Programme / Project
        </button>
      </div>
    </>
  );
}
