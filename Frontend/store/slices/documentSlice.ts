import { createSlice, PayloadAction } from "@reduxjs/toolkit";

export interface DocumentItem {
  id: string;
  name: string;
  fileName?: string;
  isUploading?: boolean;
}

interface DocumentState {
  documentsByPath: Record<string, DocumentItem[]>;
}

const initialState: DocumentState = {
  documentsByPath: {},
};

const documentSlice = createSlice({
  name: "documents",
  initialState,
  reducers: {
    setDocumentsForPath(
      state,
      action: PayloadAction<{ folderPath: string; documents: DocumentItem[] }>,
    ) {
      state.documentsByPath[action.payload.folderPath] =
        action.payload.documents;
    },
    addDocumentForPath(
      state,
      action: PayloadAction<{ folderPath: string; document: DocumentItem }>,
    ) {
      const existing = state.documentsByPath[action.payload.folderPath] ?? [];
      state.documentsByPath[action.payload.folderPath] = [
        ...existing,
        action.payload.document,
      ];
    },
    updateDocumentForPath(
      state,
      action: PayloadAction<{
        folderPath: string;
        id: string;
        update: Partial<DocumentItem>;
      }>,
    ) {
      const docs = state.documentsByPath[action.payload.folderPath];
      if (!docs) return;
      state.documentsByPath[action.payload.folderPath] = docs.map((doc) =>
        doc.id === action.payload.id
          ? { ...doc, ...action.payload.update }
          : doc,
      );
    },
    removeDocumentForPath(
      state,
      action: PayloadAction<{ folderPath: string; id: string }>,
    ) {
      const docs = state.documentsByPath[action.payload.folderPath];
      if (!docs) return;
      state.documentsByPath[action.payload.folderPath] = docs.filter(
        (doc) => doc.id !== action.payload.id,
      );
    },
  },
});

export const {
  setDocumentsForPath,
  addDocumentForPath,
  updateDocumentForPath,
  removeDocumentForPath,
} = documentSlice.actions;

export default documentSlice.reducer;
