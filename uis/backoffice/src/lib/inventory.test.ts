import { outboundWarning, parseInventoryError } from "./inventory";

describe("parseInventoryError", () => {
  it("preserves the backend stock message so the user can correct the request", () => {
    expect(parseInventoryError({ detail: "Insufficient stock for asset 'Laptop'. Available: 2, requested: 3." }, 400))
      .toContain("Available: 2");
  });

  it("formats FastAPI field errors and uses safe fallbacks", () => {
    expect(parseInventoryError({ detail: [{ loc: ["body", "quantity"], msg: "Input should be greater than 0" }] }, 422))
      .toBe("quantity: Input should be greater than 0");
    expect(parseInventoryError({ trace: "postgres://secret" }, 500)).not.toContain("secret");
  });
});

describe("outboundWarning", () => {
  it("warns only when the requested quantity exceeds current stock", () => {
    expect(outboundWarning(6, 5)).toContain("Stock insuficiente");
    expect(outboundWarning(5, 5)).toBe("");
  });
});
