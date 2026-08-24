import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    globals: false,
    include: ["tests/**/*.test.ts"],
    setupFiles: ["tests/setup/vitestSetup.ts"],
    testTimeout: 15000,
    hookTimeout: 15000
  }
});
