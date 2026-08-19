import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@/index.css";
import App from "@/App";

// Suppress benign "ResizeObserver loop ..." browser noise so it never triggers
// the CRA dev error overlay. This warning is harmless (fired by Radix/Recharts
// when they re-measure layout) and does not indicate a real bug.
const RESIZE_OBSERVER_MSG = /ResizeObserver loop (limit exceeded|completed with undelivered notifications)/;
window.addEventListener(
  "error",
  (e) => {
    if (e?.message && RESIZE_OBSERVER_MSG.test(e.message)) {
      e.stopImmediatePropagation();
      e.preventDefault();
      const overlay = document.getElementById("webpack-dev-server-client-overlay");
      if (overlay) overlay.style.display = "none";
    }
  },
  true,
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  },
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
