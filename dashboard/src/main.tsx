import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";
import "./improvement.css";
import { applyTheme, readTheme } from "./theme";

// The theme this browser keeps, before the first render, so a page never
// shows the other one first
applyTheme(readTheme());

const root = document.getElementById("root");
if (!root) throw new Error("index.html has no #root element");

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
