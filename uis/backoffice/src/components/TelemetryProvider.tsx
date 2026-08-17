"use client";

import { useCallback, useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { useReportWebVitals } from "next/web-vitals";
import type { NextWebVitalsMetric } from "next/app";

import {
  currentTelemetryActorRole,
  currentTelemetryOffice,
  initializeTelemetry,
  track,
  trackFrontendError,
  type TelemetrySection,
} from "@/services/telemetry";

interface WebVitalsSnapshot {
  TTFB?: number;
  LCP?: number;
  CLS?: number;
  INP?: number;
  sent?: boolean;
}

export function sectionFromPath(pathname: string): TelemetrySection {
  if (pathname === "/") return "dashboard";
  if (pathname.startsWith("/suppliers")) return "suppliers";
  if (pathname.startsWith("/incidents")) return "incidents";
  if (pathname.startsWith("/processes")) return "reports";
  if (pathname.startsWith("/inventory")) return "inventory";
  return "unknown";
}

function deviceClass(): "mobile" | "tablet" | "desktop" | "unknown" {
  if (typeof window === "undefined") return "unknown";
  if (window.innerWidth < 640) return "mobile";
  if (window.innerWidth < 1024) return "tablet";
  return "desktop";
}

function navigationType(): "navigate" | "reload" | "back_forward" | "prerender" {
  const navigation = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
  return navigation?.type ?? "navigate";
}

export default function TelemetryProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const section = sectionFromPath(pathname);
  const previousSection = useRef<TelemetrySection>("login");
  const vitals = useRef<WebVitalsSnapshot>({});

  useEffect(() => initializeTelemetry(), []);

  useEffect(() => {
    vitals.current = {};
    const timeout = window.setTimeout(() => {
      track("section_viewed", {
        section,
        previous_section: previousSection.current,
        office: currentTelemetryOffice(),
        actor_role: currentTelemetryActorRole(),
      });
      previousSection.current = section;
    }, 5_000);
    return () => window.clearTimeout(timeout);
  }, [section]);

  useEffect(() => {
    const onError = (event: ErrorEvent) => {
      trackFrontendError(event.error ?? new Error("WindowError"), false, section);
    };
    const onUnhandledRejection = (event: PromiseRejectionEvent) => {
      trackFrontendError(event.reason, false, section);
    };
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onUnhandledRejection);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onUnhandledRejection);
    };
  }, [section]);

  const reportWebVitals = useCallback((metric: NextWebVitalsMetric) => {
    if (metric.name === "TTFB" || metric.name === "LCP" || metric.name === "CLS" || metric.name === "INP") {
      vitals.current[metric.name] = metric.value;
    }
    const snapshot = vitals.current;
    if (snapshot.sent || snapshot.TTFB === undefined || snapshot.LCP === undefined || snapshot.CLS === undefined) return;
    snapshot.sent = true;
    track("page_load_recorded", {
      section,
      device_class: deviceClass(),
      navigation_type: navigationType(),
      ttfb_ms: Math.max(0, Math.round(snapshot.TTFB)),
      lcp_ms: Math.max(0, Math.round(snapshot.LCP)),
      cls: Math.max(0, snapshot.CLS),
      inp_ms: snapshot.INP === undefined ? null : Math.max(0, Math.round(snapshot.INP)),
      sample_rate: 1,
    });
  }, [section]);

  useReportWebVitals(reportWebVitals);

  return children;
}
