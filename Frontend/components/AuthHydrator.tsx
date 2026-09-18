"use client";

import { useEffect, useRef } from "react";
import { fetchCurrentUser } from "@/services/userService";
import { authFailed, authLoaded, authLoading } from "@/store/slices/authSlice";
import { useAppDispatch, useAppSelector } from "@/store/store";

export default function AuthHydrator() {
  const dispatch = useAppDispatch();
  const status = useAppSelector((state) => state.auth.status);
  const hydrationStarted = useRef(false);

  useEffect(() => {
    if (status !== "idle") {
      hydrationStarted.current = false;
      return;
    }
    if (hydrationStarted.current) return;
    hydrationStarted.current = true;
    dispatch(authLoading());

    fetchCurrentUser()
      .then((user) => dispatch(authLoaded(user)))
      .catch(() => dispatch(authFailed()));
  }, [status, dispatch]);

  return null;
}
