import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app/App";

function mount() {
  const el = document.getElementById("root");
  if (!el) throw new Error("Missing #root element");
  createRoot(el).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

// Inside Outlook, wait for Office.js. In a plain browser (development) mount right away.
if (typeof Office !== "undefined" && typeof Office.onReady === "function") {
  void Office.onReady().then(mount);
} else {
  mount();
}
