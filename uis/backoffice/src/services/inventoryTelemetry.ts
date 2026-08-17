"use client";

import { track, type TelemetryActorRole, type TelemetryOffice } from "@/services/telemetry";

type ProductCategory = "training_kit" | "certification" | "onboarding_equipment";
type Currency = "EUR" | "USD";

interface InventoryBase {
  office: Exclude<TelemetryOffice, "unknown">;
  product_id: string;
  product_category: ProductCategory;
  programme_id: string;
  quantity: number;
  currency: Currency;
}

export function trackInboundOrderCreated(properties: InventoryBase & {
  order_id: string;
  supplier_id: string;
  unit_cost: number;
}): void {
  track("inbound_order_created", { ...properties });
}

export function trackOutboundOrderCreated(properties: InventoryBase & {
  order_id: string;
  recipient_type: "client" | "candidate" | "consultant" | "support_agent";
}): void {
  track("outbound_order_created", { ...properties });
}

export function trackStockThresholdTriggered(properties: InventoryBase & {
  threshold: number;
  available_quantity: number;
}): void {
  track("stock_threshold_triggered", { ...properties });
}

export function trackDirectStockEditRejected(properties: InventoryBase & {
  attempted_operation: "set" | "increment" | "decrement";
  actor_role: TelemetryActorRole;
  reason_code: string;
}): void {
  track("direct_stock_edit_rejected", { ...properties });
}

export function trackKitCostVarianceDetected(properties: InventoryBase & {
  supplier_id: string;
  previous_unit_cost: number;
  current_unit_cost: number;
  variance_percent: number;
  threshold_percent: number;
}): void {
  track("kit_cost_variance_detected", { ...properties });
}
