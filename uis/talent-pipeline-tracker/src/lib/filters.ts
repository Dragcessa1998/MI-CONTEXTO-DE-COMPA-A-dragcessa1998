import type { RecordFilters, TrackerRecord } from "@/types/tracker";

/** Aplica estado, etapa y búsqueda por nombre/email sin mutar la respuesta. */
export function filterRecords(
  records: readonly TrackerRecord[],
  filters: RecordFilters,
): TrackerRecord[] {
  const search = filters.search?.trim().toLowerCase() ?? "";
  return records.filter((record) =>
    (!filters.status || record.status === filters.status) &&
    (!filters.stage || record.stage === filters.stage) &&
    (!search || `${record.full_name} ${record.email}`.toLowerCase().includes(search)),
  );
}

