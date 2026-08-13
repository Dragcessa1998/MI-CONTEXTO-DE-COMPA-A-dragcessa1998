import { authenticatedHeaders, clearExpiredSession } from "@/lib/auth";

export const INVENTORY_API_URL =
  process.env.NEXT_PUBLIC_INVENTORY_API_URL ??
  process.env.NEXT_PUBLIC_PLATFORM_API_URL ??
  process.env.NEXT_PUBLIC_AUTH_API_URL ??
  process.env.NEXT_PUBLIC_SUPPLIERS_API_URL ??
  "http://localhost:8000";

export const OFFICES = ["Valencia", "Miami"] as const;
export type Office = (typeof OFFICES)[number];

export const ASSET_CATEGORIES = ["hardware", "peripherals", "office_supplies", "training_materials"] as const;
export type AssetCategory = (typeof ASSET_CATEGORIES)[number];
export const CATEGORY_LABELS: Record<AssetCategory, string> = {
  hardware: "Hardware",
  peripherals: "Periféricos",
  office_supplies: "Suministros de oficina",
  training_materials: "Material de formación",
};

export type ExitType = "allocation" | "consumption";
export const EXIT_TYPE_LABELS: Record<ExitType, string> = {
  allocation: "Asignación",
  consumption: "Consumo",
};

export interface AssetSummary {
  id: number;
  name: string;
  sku: string;
  category: AssetCategory;
  office: Office;
}

export interface Asset extends AssetSummary {
  current_stock: number;
}

export interface AssetInput {
  name: string;
  sku: string;
  category: AssetCategory;
  office: Office;
}

export interface InboundInput {
  asset_id: number;
  quantity: number;
  supplier: string;
  office: Office;
}

export interface OutboundInput {
  asset_id: number;
  quantity: number;
  exit_type: ExitType;
  assigned_to: string | null;
  office: Office;
}

interface RecordedOrder {
  id: number;
  asset_id: number;
  quantity: number;
  office: Office;
  created_at: string;
  user_uuid: string;
  asset: AssetSummary;
}

export interface InboundOrder extends RecordedOrder {
  supplier: string;
}

export interface OutboundOrder extends RecordedOrder {
  exit_type: ExitType;
  assigned_to: string | null;
}

export interface InventoryOrder {
  id: number;
  order_type: "inbound" | "outbound";
  asset_id: number;
  quantity: number;
  office: Office;
  created_at: string;
  user_uuid: string;
  asset: AssetSummary;
  supplier: string | null;
  exit_type: ExitType | null;
  assigned_to: string | null;
}

export class InventoryApiError extends Error {
  constructor(message: string, public readonly status?: number) {
    super(message);
    this.name = "InventoryApiError";
  }
}

export function parseInventoryError(body: unknown, status: number): string {
  if (body && typeof body === "object") {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const messages = detail.map((item) => {
        const issue = item as { loc?: unknown[]; msg?: unknown };
        const field = Array.isArray(issue.loc) ? String(issue.loc.at(-1) ?? "datos") : "datos";
        const message = typeof issue.msg === "string" ? issue.msg.replace(/^Value error, /, "") : "valor no válido";
        return `${field}: ${message}`;
      });
      if (messages.length) return messages.join(" · ");
    }
  }
  if (status === 401) return "Tu sesión ha expirado. Inicia sesión de nuevo.";
  if (status === 404) return "No encontramos el registro solicitado.";
  if (status === 409) return "Ya existe un activo con ese SKU.";
  if (status === 422) return "Revisa los datos del formulario.";
  return "No pudimos completar la operación. Inténtalo de nuevo.";
}

export function outboundWarning(quantity: number, available: number): string {
  return quantity > available
    ? `Stock insuficiente: hay ${available} unidades y solicitas ${quantity}.`
    : "";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${INVENTORY_API_URL}${path}`, {
      ...init,
      cache: "no-store",
      headers: authenticatedHeaders(init.headers),
    });
  } catch {
    throw new InventoryApiError("No se pudo conectar con el servicio de inventario.");
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401) clearExpiredSession();
    throw new InventoryApiError(parseInventoryError(body, response.status), response.status);
  }
  return body as T;
}

export const inventoryApi = {
  listProducts: () => request<Asset[]>("/inventory/products"),
  createProduct: (payload: AssetInput) =>
    request<Asset>("/inventory/products", { method: "POST", body: JSON.stringify(payload) }),
  getProduct: (id: number) => request<Asset>(`/inventory/products/${id}`),
  createInbound: (payload: InboundInput) =>
    request<InboundOrder>("/inventory/orders/inbound", { method: "POST", body: JSON.stringify(payload) }),
  createOutbound: (payload: OutboundInput) =>
    request<OutboundOrder>("/inventory/orders/outbound", { method: "POST", body: JSON.stringify(payload) }),
  listOrders: () => request<InventoryOrder[]>("/inventory/orders"),
};
