"use client";

import { ReactNode, useEffect, useRef } from "react";
import { Provider } from "react-redux";
import { App as AntdApp, App } from "antd";
import { store, useAppSelector } from "./store";

interface ReduxProviderProps {
  children: ReactNode;
}

function AutomationSelectionNotificationListener() {
  const { notification } = App.useApp();

  const status = useAppSelector((state) => state.automationSelection.status);
  const error = useAppSelector((state) => state.automationSelection.error);

  const previousStatusRef = useRef(status);

  useEffect(() => {
    if (previousStatusRef.current !== status) {
      if (status === "success") {
        notification.success({
          title: "Analysis complete",
          description:
            "The automation candidate evaluation has been refreshed.",
        });
      }

      if (status === "failed") {
        notification.error({
          title: "Automation analysis failed",
          description:
            error ||
            "The automation analysis service could not complete. Please try again.",
        });
      }

      previousStatusRef.current = status;
    }
  }, [status, error, notification]);

  return null;
}

function TestGenerationNotificationListener() {
  const { notification } = App.useApp();

  const { status, error } = useAppSelector((state) => state.testGeneration);

  const previousStatusRef = useRef(status);

  useEffect(() => {
    if (previousStatusRef.current !== status) {
      if (status === "success") {
        notification.success({
          title: "Test generation completed",
          description:
            "The AI service finished successfully and test data is ready.",
        });
      }

      if (status === "failed") {
        notification.error({
          title: "Test generation failed",
          description:
            error ||
            "The AI service could not generate test cases. Please try again.",
        });
      }

      previousStatusRef.current = status;
    }
  }, [status, error, notification]);

  return null;
}

export default function ReduxProvider({ children }: ReduxProviderProps) {
  return (
    <Provider store={store}>
      <AntdApp
        notification={{
          placement: "top",
          duration: 8,
        }}
      >
        <AutomationSelectionNotificationListener />
        <TestGenerationNotificationListener />
        {children}
      </AntdApp>
    </Provider>
  );
}
