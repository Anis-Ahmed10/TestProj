import { createAsyncThunk, createSlice, PayloadAction } from "@reduxjs/toolkit";
import { analyzeImpact } from "@/services/impactAnalyzer";
import type {
  ImpactAnalysisResult,
  RegressionStrategy,
  ChangeType,
  SuiteSource,
} from "@/types/impactAnalyzer";
import type { RootState } from "@/store/store";

export interface AnalyzeRegressionParams {
  projectId: string;
  storyKeys: string[];
  changeType: Exclude<ChangeType, null>;
  regressionStrategy: RegressionStrategy;
  suiteSource: SuiteSource;
  impactPrompt?: string;
  contextDocuments?: string[];
  userId?: string;
}

type RegressionAnalyserStatus = "idle" | "inProgress" | "success" | "failed";

export interface RegressionAnalyserInputState {
  projectId: string | null;
  stories: string[];
  changeType: ChangeType;
  changeTypeDetail: string;
  strategy: RegressionStrategy;
  suiteSource: SuiteSource;
  changeDescription: string;
  impactPrompt: string;
}

interface RegressionAnalyserState {
  inputState: RegressionAnalyserInputState;
  status: RegressionAnalyserStatus;
  error: string | null;
  result: ImpactAnalysisResult | null;
  lastUpdated: string | null;
  requestId: string | null;
}

const initialInputState: RegressionAnalyserInputState = {
  projectId: null,
  stories: [],
  changeType: null,
  changeTypeDetail: "",
  strategy: "selective",
  suiteSource: "internal",
  changeDescription: "",
  impactPrompt: "",
};

const initialState: RegressionAnalyserState = {
  inputState: initialInputState,
  status: "idle",
  error: null,
  result: null,
  lastUpdated: null,
  requestId: null,
};

export const analyzeRegressionAsync = createAsyncThunk<
  ImpactAnalysisResult,
  AnalyzeRegressionParams,
  { rejectValue: string }
>(
  "regressionAnalyser/analyzeImpact",
  async (params, { rejectWithValue, signal }) => {
    try {
      return await analyzeImpact({ ...params, signal });
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") throw error;
      return rejectWithValue(
        error instanceof Error
          ? error.message
          : "Failed to analyse regression impact.",
      );
    }
  },
);

const IMPACT_PROMPT_HARD_LIMIT = 10_000;

export type RunRegressionAnalysisRejection =
  | { code: "MISSING_PROJECT" }
  | { code: "MISSING_CHANGE_TYPE" }
  | { code: "MISSING_STORIES" };

export const runRegressionAnalysis = createAsyncThunk<
  void,
  void,
  { state: RootState; rejectValue: RunRegressionAnalysisRejection }
>(
  "regressionAnalyser/run",
  async (_, { getState, dispatch, rejectWithValue }) => {
    const state = getState();
    const {
      projectId,
      stories,
      changeType,
      changeTypeDetail,
      strategy,
      suiteSource,
      changeDescription,
      impactPrompt,
    } = state.regressionAnalyser.inputState;

    if (!projectId) {
      return rejectWithValue({ code: "MISSING_PROJECT" });
    }
    if (!changeType) {
      return rejectWithValue({ code: "MISSING_CHANGE_TYPE" });
    }
    if (stories.length === 0) {
      return rejectWithValue({ code: "MISSING_STORIES" });
    }

    const combinedPrompt = [changeDescription, changeTypeDetail, impactPrompt]
      .filter(Boolean)
      .join("\n\n")
      .slice(0, IMPACT_PROMPT_HARD_LIMIT);

    dispatch(regressionAnalyserSlice.actions.clearRegressionAnalyserResult());

    await dispatch(
      analyzeRegressionAsync({
        projectId,
        storyKeys: stories,
        changeType,
        regressionStrategy: strategy,
        suiteSource,
        impactPrompt: combinedPrompt,
        userId: state.auth.user?.id ?? undefined,
      }),
    ).unwrap();
  },
);

const regressionAnalyserSlice = createSlice({
  name: "regressionAnalyser",
  initialState,
  reducers: {
    setProjectId(state, action: PayloadAction<string | null>) {
      const nextProjectId = action.payload;
      if (nextProjectId === state.inputState.projectId) {
        return;
      }
      state.inputState = { ...initialInputState, projectId: nextProjectId };
      state.status = "idle";
      state.error = null;
      state.result = null;
      state.lastUpdated = null;
      state.requestId = null;
    },
    setStories(state, action: PayloadAction<string[]>) {
      state.inputState.stories = action.payload;
    },
    selectChangeType(state, action: PayloadAction<ChangeType>) {
      state.inputState.changeType = action.payload;
      if (action.payload) {
        state.inputState.suiteSource =
          action.payload === "defect" ? "jira" : "internal";
      }
    },
    setChangeTypeDetail(state, action: PayloadAction<string>) {
      state.inputState.changeTypeDetail = action.payload;
    },
    setStrategy(state, action: PayloadAction<RegressionStrategy>) {
      state.inputState.strategy = action.payload;
    },
    setSuiteSource(state, action: PayloadAction<SuiteSource>) {
      state.inputState.suiteSource = action.payload;
    },
    setChangeDescription(state, action: PayloadAction<string>) {
      state.inputState.changeDescription = action.payload;
    },
    setImpactPrompt(state, action: PayloadAction<string>) {
      state.inputState.impactPrompt = action.payload;
    },
    clearRegressionAnalyserResult(state) {
      state.status = "idle";
      state.error = null;
      state.result = null;
      state.lastUpdated = null;
      state.requestId = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(analyzeRegressionAsync.pending, (state, action) => {
        state.requestId = action.meta.requestId;
        state.status = "inProgress";
        state.error = null;
      })
      .addCase(analyzeRegressionAsync.fulfilled, (state, action) => {
        if (action.meta.requestId !== state.requestId) return;
        state.status = "success";
        state.result = action.payload;
        state.error = null;
        state.lastUpdated = new Date().toISOString();
      })
      .addCase(analyzeRegressionAsync.rejected, (state, action) => {
        if (action.meta.requestId !== state.requestId) return;
        if (action.meta.aborted) {
          state.status = "idle";
          return;
        }
        state.status = "failed";
        state.error =
          action.payload ||
          action.error.message ||
          "Failed to analyse regression impact.";
        state.lastUpdated = new Date().toISOString();
      });
  },
});

export const {
  setProjectId,
  setStories,
  selectChangeType,
  setChangeTypeDetail,
  setStrategy,
  setSuiteSource,
  setChangeDescription,
  setImpactPrompt,
  clearRegressionAnalyserResult,
} = regressionAnalyserSlice.actions;
export default regressionAnalyserSlice.reducer;
