/** @type {import('jest').Config} */
module.exports = {
  preset: "ts-jest",
  testEnvironment: "node",
  testMatch: ["<rootDir>/src/**/*.test.ts"],
  collectCoverageFrom: ["src/lib/api.ts", "src/lib/suppliers.ts", "src/lib/inventory.ts"],
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/src/$1",
    "^@logic/(.*)$": "<rootDir>/../../src/$1",
  },
};
