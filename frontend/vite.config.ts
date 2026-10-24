import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Outlook only loads task panes over HTTPS. Certificates are created once with:
//   npx office-addin-dev-certs install
function devHttps() {
  const dir = path.join(os.homedir(), ".office-addin-dev-certs");
  const key = path.join(dir, "localhost.key");
  const cert = path.join(dir, "localhost.crt");
  const ca = path.join(dir, "ca.crt");
  if (fs.existsSync(key) && fs.existsSync(cert)) {
    return {
      key: fs.readFileSync(key),
      cert: fs.readFileSync(cert),
      ca: fs.existsSync(ca) ? fs.readFileSync(ca) : undefined,
    };
  }
  return undefined;
}

export default defineConfig({
  plugins: [react()],
  server: { port: 3000, https: devHttps() },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    css: false,
  },
});
