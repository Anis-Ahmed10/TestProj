"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { fetchAuthSession } from "aws-amplify/auth";
import {
  Authenticator,
  ThemeProvider,
  useAuthenticator,
} from "@aws-amplify/ui-react";
import FlaskSVG from "../assets/FlaskSVG";
import "../assets/css/login.css";

const theme = {
  name: "infuse-theme",
  tokens: {
    colors: {
      brand: {
        primary: {
          "10": { value: "#f0f9f7" },
          "20": { value: "#d4eeea" },
          "40": { value: "#a0d4cc" },
          "60": { value: "#1f5c54" },
          "80": { value: "#174d46" },
          "90": { value: "#0f3830" },
          "100": { value: "#071f1b" },
        },
      },
    },
  },
} as const;

const formFields = {
  signUp: {
    name: {
      label: "Full Name",
      placeholder: "Enter your full name",
      isRequired: true,
      order: 1,
    },
  },
};

function AuthenticatedRedirect() {
  const { authStatus } = useAuthenticator();
  const router = useRouter();
  useEffect(() => {
    if (authStatus === "authenticated") router.replace("/test-generator");
  }, [authStatus, router]);
  return null;
}

export default function LoginPage() {
  const router = useRouter();
  useEffect(() => {
    fetchAuthSession()
      .then((s) => {
        if (s.tokens?.idToken) router.replace("/test-generator");
      })
      .catch(() => {});
  }, [router]);

  return (
    <div className="login-bg">
      <ThemeProvider theme={theme}>
        <div className="login-card">
          <div className="login-card__brand">
            <div className="login-card__icon">
              <FlaskSVG />
            </div>
            <h2 className="login-card__title">Infuse AI Platform</h2>
            <p className="login-card__subtitle">
              AI-Augmented Testing Delivery
            </p>
          </div>
          <Authenticator loginMechanisms={["email"]} formFields={formFields}>
            {() => <AuthenticatedRedirect />}
          </Authenticator>
          <p className="login-card__footer">
            Infuse Consulting © 2026 · v0.6.0
          </p>
        </div>
      </ThemeProvider>
    </div>
  );
}
