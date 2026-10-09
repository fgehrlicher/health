import { defineConfig } from "vite"
import { devtools } from "@tanstack/devtools-vite"
import { tanstackStart } from "@tanstack/react-start/plugin/vite"
import viteReact from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

const config = defineConfig({
  resolve: { tsconfigPaths: true },
  // Devtools forward console output between browser and server, which
  // floods end-to-end test logs; tests set E2E=1.
  plugins: [
    ...(process.env.E2E ? [] : [devtools()]),
    tailwindcss(),
    tanstackStart(),
    viteReact(),
  ],
  // The production preview server (on the home server) rejects host names it
  // does not know. These are the names the home network uses for it.
  preview: { allowedHosts: ["health.fritz.box", "health"] },
})

export default config
