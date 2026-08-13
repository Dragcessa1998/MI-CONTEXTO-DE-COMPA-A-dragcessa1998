import { extractError, safeHttpMessage } from "./api";
import { extractFastApiError } from "./suppliers";

describe("extractError", () => {
  it("returns the public structured message and string details", () => {
    expect(
      extractError({
        error: {
          message: "Revisa el candidato.",
          details: ["email inválido", 500, "salario fuera de rango"],
        },
      }),
    ).toBe("Revisa el candidato. · email inválido · salario fuera de rango");
  });

  it("returns null for malformed or private error bodies", () => {
    expect(extractError(null)).toBeNull();
    expect(extractError({ trace: "database-password" })).toBeNull();
  });
});

describe("safeHttpMessage", () => {
  it("maps a known authentication failure to a safe actionable message", () => {
    expect(safeHttpMessage(401)).toBe("Tu sesión no es válida. Inicia sesión de nuevo.");
  });

  it("uses the generic safe fallback for unknown and server statuses", () => {
    expect(safeHttpMessage(418)).toBe(
      "El servicio no pudo completar la operación. Reintenta en unos instantes.",
    );
    expect(safeHttpMessage(503)).not.toContain("trace");
  });
});

describe("extractFastApiError", () => {
  it("formats validation details and translates required fields", () => {
    expect(
      extractFastApiError({
        detail: [
          { loc: ["body", "email"], msg: "Field required" },
          { loc: ["body", "monthly_rate"], msg: "Input should be a valid number" },
        ],
      }),
    ).toBe("email: Este campo es obligatorio · monthly_rate: Debe ser un número válido");
  });

  it("returns null instead of exposing an unknown response shape", () => {
    expect(extractFastApiError({ internal: "postgres://secret" })).toBeNull();
    expect(extractFastApiError("not-json")).toBeNull();
  });
});
