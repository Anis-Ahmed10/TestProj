import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import { CurrentUser } from "@/types/auth";

export type AuthStatus = "idle" | "loading" | "loaded" | "error";

interface AuthState {
  user: CurrentUser | null;
  status: AuthStatus;
}

const initialState: AuthState = {
  user: null,
  status: "idle",
};

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    authLoading(state) {
      state.status = "loading";
    },
    authLoaded(state, action: PayloadAction<CurrentUser>) {
      state.user = action.payload;
      state.status = "loaded";
    },
    authFailed(state) {
      state.user = null;
      state.status = "error";
    },
    clearAuth(state) {
      state.user = null;
      state.status = "idle";
    },
  },
});

export const { authLoading, authLoaded, authFailed, clearAuth } =
  authSlice.actions;

export default authSlice.reducer;
