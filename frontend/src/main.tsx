import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { AppProvider } from "./state";
import "./styles.css";

/** Last line of defence: a rendering failure must never show a blank page. */
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // Keep the detail in the console for debugging, and show a readable panel.
    console.error("FIRETRACK interface error", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 48, maxWidth: 780, margin: "0 auto", fontFamily: "system-ui" }}>
          <div style={{ color: "#f97316", letterSpacing: "0.18em", fontSize: 11, textTransform: "uppercase" }}>
            FIRETRACK
          </div>
          <h1 style={{ color: "#e8eef7", fontSize: 24, margin: "8px 0" }}>The interface hit an error</h1>
          <p style={{ color: "#9fb0c7", lineHeight: 1.6 }}>
            The server is probably still running. Reload the page; if the problem persists, this build
            of the interface has a bug.
          </p>
          <pre
            style={{
              background: "#0c1626", color: "#fca5a5", padding: 14, borderRadius: 8,
              fontSize: 12, overflow: "auto", border: "1px solid #1b2b44",
            }}
          >
            {this.state.error.message}
          </pre>
          <button
            type="button"
            onClick={() => window.location.reload()}
            style={{
              marginTop: 14, padding: "8px 14px", borderRadius: 8, border: "1px solid #f97316",
              background: "#f97316", color: "#1a0d02", fontWeight: 600, cursor: "pointer",
            }}
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ErrorBoundary>
      <AppProvider>
        <App />
      </AppProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);
