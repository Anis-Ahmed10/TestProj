import { createAsyncThunk, createSlice, PayloadAction } from "@reduxjs/toolkit";
import { analyzeAutomationCandidates } from "@/services/automationSelector";
import type {
  AutomationSelectorState,
  CategoryConfig,
  CategoryKey,
  ClassificationThresholds,
} from "@/types/automationCandidate";
import { buildCategoryState } from "@/utils/automationSelector/automationSelectorHelpers";

type AnalysisPayload = {
  categories: Record<CategoryKey, CategoryConfig>;
  categoryOrder: CategoryKey[];
};

const createInitialState = (
  projectId: string | null = null,
): AutomationSelectorState => ({
  status: "idle",
  projectId,
  categories: {},
  categoryOrder: [],
  activeCategory: "",
  selectedFilter: "all",
  searchQuery: "",
  levelFilter: "",
  settingsPanelOpen: false,
  settingsActiveTab: "",
  thresholds: { automate: 0.65, review: 0.4 },
  projectContext: "",
  lastRunTimestamp: null,
  rerunning: false,
  error: null,
  hasRun: false,
});

export const runAutomationAnalysisAsync = createAsyncThunk<
  AnalysisPayload,
  string,
  { rejectValue: string }
>(
  "automationSelection/runAnalysis",
  async (projectId, { rejectWithValue, signal }) => {
    try {
      const response = await analyzeAutomationCandidates(projectId, signal);
      const categories = response.data?.categories ?? [];

      if (!categories.length) {
        return rejectWithValue(
          "The automation analysis returned no categories for this project.",
        );
      }

      return buildCategoryState(categories);
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") throw error;
      return rejectWithValue(
        error instanceof Error
          ? error.message
          : "Failed to analyse automation candidates.",
      );
    }
  },
);

const automationSelectionSlice = createSlice({
  name: "automationSelection",
  initialState: createInitialState(),
  reducers: {
    setProjectId(state, action: PayloadAction<string | null>) {
      return createInitialState(action.payload);
    },
    setActiveCategory(state, action: PayloadAction<CategoryKey>) {
      state.activeCategory = action.payload;
      state.selectedFilter = "all";
      state.searchQuery = "";
      state.levelFilter = "";
    },
    setSelectedFilter(
      state,
      action: PayloadAction<"all" | "automate" | "review" | "manual">,
    ) {
      state.selectedFilter = action.payload;
    },
    setSearchQuery(state, action: PayloadAction<string>) {
      state.searchQuery = action.payload;
    },
    setLevelFilter(state, action: PayloadAction<string>) {
      state.levelFilter = action.payload;
    },
    toggleTestCaseChecked(state, action: PayloadAction<string>) {
      const cat = state.categories[state.activeCategory];
      if (!cat) return;
      const tc = cat.testCases.find((t) => t.id === action.payload);
      if (tc && tc.classification !== "KEEP_MANUAL") {
        tc.checked = !tc.checked;
      }
    },
    setAllChecked(
      state,
      action: PayloadAction<{ checked: boolean; visibleIds: string[] }>,
    ) {
      const cat = state.categories[state.activeCategory];
      if (!cat) return;
      const visibleSet = new Set(action.payload.visibleIds);
      cat.testCases.forEach((tc) => {
        if (visibleSet.has(tc.id) && tc.classification !== "KEEP_MANUAL") {
          tc.checked = action.payload.checked;
        }
      });
    },
    openSettingsPanel(state) {
      state.settingsPanelOpen = true;
      state.settingsActiveTab = state.activeCategory;
    },
    closeSettingsPanel(state) {
      state.settingsPanelOpen = false;
    },
    setSettingsActiveTab(state, action: PayloadAction<CategoryKey>) {
      state.settingsActiveTab = action.payload;
    },
    updateThresholds(state, action: PayloadAction<ClassificationThresholds>) {
      state.thresholds = action.payload;
    },
    updateProjectContext(state, action: PayloadAction<string>) {
      state.projectContext = action.payload;
    },
    updateCategoryPrompt(
      state,
      action: PayloadAction<{
        key: CategoryKey;
        field: "basePrompt" | "impactPrompt";
        value: string;
      }>,
    ) {
      const cat = state.categories[action.payload.key];
      if (cat) {
        cat[action.payload.field] = action.payload.value;
      }
    },
    addCategory(state, action: PayloadAction<{ key: string; name: string }>) {
      const newCat: CategoryConfig = {
        key: action.payload.key,
        title: action.payload.name,
        icon: "AppstoreOutlined",
        iconColor: "#6B7280",
        iconBgClass: "as-ci-custom",
        meta: "0 TCs · Not yet analysed",
        basePrompt: `You are an expert test automation engineer. Evaluate each test case for suitability as a ${action.payload.name} test automation candidate.

Return a JSON object matching the exact schema provided.`,
        impactPrompt: "",
        factors: [],
        status: "scored",
        failureReason: null,
        counts: { all: 0, automate: 0, review: 0, manual: 0 },
        testCases: [],
      };
      state.categories[action.payload.key] = newCat;
      state.categoryOrder.push(action.payload.key);
    },
    clearAutomationSelectorState() {
      return createInitialState();
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(runAutomationAnalysisAsync.pending, (state) => {
        state.status = "inProgress";
        state.rerunning = true;
        state.error = null;
      })
      .addCase(runAutomationAnalysisAsync.fulfilled, (state, action) => {
        if (action.meta.arg !== state.projectId) return;
        state.status = "success";
        state.rerunning = false;
        state.hasRun = true;
        state.error = null;
        const custom = state.categoryOrder.filter(
          (key) => !(key in action.payload.categories),
        );
        const edited = Object.fromEntries(
          Object.entries(action.payload.categories).map(([key, cat]) => [
            key,
            state.categories[key]
              ? {
                  ...cat,
                  basePrompt: state.categories[key].basePrompt,
                  impactPrompt: state.categories[key].impactPrompt,
                }
              : cat,
          ]),
        );
        state.categories = {
          ...edited,
          ...Object.fromEntries(
            custom.map((key) => [key, state.categories[key]]),
          ),
        };
        state.categoryOrder = [...action.payload.categoryOrder, ...custom];
        state.activeCategory = action.payload.categoryOrder[0] ?? "";
        state.selectedFilter = "all";
        state.searchQuery = "";
        state.levelFilter = "";
        state.lastRunTimestamp = new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });
      })
      .addCase(runAutomationAnalysisAsync.rejected, (state, action) => {
        if (action.meta.arg !== state.projectId) return;
        state.rerunning = false;
        if (action.error?.name === "AbortError") {
          state.status = "idle";
          state.error = null;
          return;
        }
        state.status = "failed";
        state.error =
          action.payload ||
          action.error.message ||
          "Failed to analyse automation candidates.";
      });
  },
});

export const {
  setProjectId,
  setActiveCategory,
  setSelectedFilter,
  setSearchQuery,
  setLevelFilter,
  toggleTestCaseChecked,
  setAllChecked,
  openSettingsPanel,
  closeSettingsPanel,
  setSettingsActiveTab,
  updateThresholds,
  updateProjectContext,
  updateCategoryPrompt,
  addCategory,
  clearAutomationSelectorState,
} = automationSelectionSlice.actions;

export default automationSelectionSlice.reducer;
