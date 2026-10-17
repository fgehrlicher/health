import { configDefaults, defineConfig } from "vitest/config"

// Unit tests only. The Playwright specs in e2e/ run with `make check-e2e`; this
// config stands alone so the tests load without the app's Vite plugins.
export default defineConfig({
  resolve: { tsconfigPaths: true },
  test: { exclude: [...configDefaults.exclude, "e2e/**"] },
})
