import { createSignal, Show, onMount } from "solid-js";
import { isLoaded, isSignedIn, initClerk } from "./auth/clerk";
import LandingPage from "./pages/LandingPage";
import Dashboard from "./pages/Dashboard";

export default function App() {
  const [ready, setReady] = createSignal(false);

  onMount(async () => {
    await initClerk();
    setReady(true);
  });

  return (
    <Show when={ready()} fallback={<LoadingScreen />}>
      <Show when={isSignedIn()} fallback={<LandingPage />}>
        <Dashboard />
      </Show>
    </Show>
  );
}

function LoadingScreen() {
  return (
    <div style={{
      "min-height": "100vh",
      display: "flex",
      "align-items": "center",
      "justify-content": "center",
      background: "#09090b",
      color: "#a1a1aa",
      "font-family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    }}>
      <div style={{ "text-align": "center" }}>
        <div style={{ "font-size": "24px", "font-weight": 700, color: "#fafafa", "margin-bottom": "8px" }}>
          FDE<span style={{ color: "#6366f1" }}>.</span>
        </div>
        <p>Loading...</p>
      </div>
    </div>
  );
}
