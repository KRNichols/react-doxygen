import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import { CopyProvider } from "./copy.jsx";
import "./index.css";

/**
 * What: Mount the React tree (router + configurable copy + pages).
 * Why: The SPA needs a single entry that can fail-soft if /api/copy is down.
 * Who: Vite / index.html module script.
 * Where: #root in frontend/index.html; served on :5173 in dev.
 * How: createRoot + StrictMode + BrowserRouter + CopyProvider + App.
 */
function bootstrap() {
  createRoot(document.getElementById("root")).render(
    <React.StrictMode>
      <BrowserRouter>
        <CopyProvider>
          <App />
        </CopyProvider>
      </BrowserRouter>
    </React.StrictMode>
  );
}

bootstrap();
