import {
  combineReducers,
  configureStore,
  createAction,
} from "@reduxjs/toolkit";
import { TypedUseSelectorHook, useDispatch, useSelector } from "react-redux";
import authReducer from "./slices/authSlice";
import automationSelectionReducer from "./slices/automationSelectionSlice";
import documentReducer from "./slices/documentSlice";
import regressionAnalyserReducer from "./slices/regressionAnalyserSlice";
import testGenerationReducer from "./slices/testGenerationSlice";

export const resetAllState = createAction("store/resetAll");

const combinedReducer = combineReducers({
  auth: authReducer,
  testGeneration: testGenerationReducer,
  automationSelection: automationSelectionReducer,
  documents: documentReducer,
  regressionAnalyser: regressionAnalyserReducer,
});

type CombinedState = ReturnType<typeof combinedReducer>;

function rootReducer(
  state: CombinedState | undefined,
  action: { type: string },
) {
  if (resetAllState.match(action)) {
    return combinedReducer(undefined, action);
  }
  return combinedReducer(state, action);
}

export const store = configureStore({ reducer: rootReducer });

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;

export const useAppDispatch: () => AppDispatch = useDispatch;
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;
