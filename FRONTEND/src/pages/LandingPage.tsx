import { getClerk } from "../auth/clerk";

export default function LandingPage() {
  function handleGetStarted() {
    const clerk = getClerk();
    if (clerk) {
      clerk.openSignIn({});
    } else {
      // Dev mode — just navigate to app
      window.location.hash = "#/app";
    }
  }

  function handleSignIn() {
    const clerk = getClerk();
    if (clerk) {
      clerk.openSignIn({});
    } else {
      window.location.hash = "#/app";
    }
  }

  return (
    <div style={{ "min-height": "100vh", background: "#09090b", color: "#fafafa", "font-family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" }}>
      {/* Header */}
      <header style={{ display: "flex", "justify-content": "space-between", "align-items": "center", padding: "20px 40px", "max-width": "1200px", margin: "0 auto" }}>
        <div style={{ "font-size": "20px", "font-weight": 700, color: "#fafafa" }}>
          FDE<span style={{ color: "#6366f1" }}>.</span>
        </div>
        <nav style={{ display: "flex", gap: "32px", "align-items": "center" }}>
          <a href="#features" style={{ color: "#a1a1aa", "text-decoration": "none", "font-size": "14px" }}>Features</a>
          <a href="#how-it-works" style={{ color: "#a1a1aa", "text-decoration": "none", "font-size": "14px" }}>How it Works</a>
          <a href="#pricing" style={{ color: "#a1a1aa", "text-decoration": "none", "font-size": "14px" }}>Pricing</a>
          <button
            onClick={handleSignIn}
            style={{ background: "transparent", border: "1px solid #27272a", color: "#fafafa", padding: "8px 16px", "border-radius": "6px", cursor: "pointer", "font-size": "14px" }}
          >
            Sign In
          </button>
        </nav>
      </header>

      {/* Hero */}
      <section style={{ "text-align": "center", padding: "120px 40px 80px", "max-width": "900px", margin: "0 auto" }}>
        <div style={{ display: "inline-block", background: "#1e1b4b", color: "#a5b4fc", padding: "4px 12px", "border-radius": "20px", "font-size": "12px", "font-weight": 500, "margin-bottom": "24px" }}>
          AI-Powered Engineering Platform
        </div>
        <h1 style={{ "font-size": "clamp(36px, 5vw, 64px)", "font-weight": 800, "line-height": 1.1, margin: "0 0 24px", background: "linear-gradient(135deg, #fafafa 0%, #a1a1aa 100%)", "-webkit-background-clip": "text", "-webkit-text-fill-color": "transparent" }}>
          Describe your idea.<br />We build it.
        </h1>
        <p style={{ "font-size": "18px", color: "#a1a1aa", "max-width": "600px", margin: "0 auto 40px", "line-height": 1.6 }}>
          FDE is a Forward Deployed Engineer that plans your architecture, generates production-ready code, and deploys LLMs to cloud infrastructure — all from a single conversation.
        </p>
        <div style={{ display: "flex", gap: "16px", "justify-content": "center" }}>
          <button
            onClick={handleGetStarted}
            style={{ background: "#6366f1", color: "white", border: "none", padding: "12px 28px", "border-radius": "8px", "font-size": "16px", "font-weight": 600, cursor: "pointer" }}
          >
            Get Started Free
          </button>
          <a
            href="#how-it-works"
            style={{ background: "transparent", color: "#fafafa", border: "1px solid #27272a", padding: "12px 28px", "border-radius": "8px", "font-size": "16px", "font-weight": 600, "text-decoration": "none", display: "inline-block" }}
          >
            See How it Works
          </a>
        </div>
      </section>

      {/* Features */}
      <section id="features" style={{ padding: "80px 40px", "max-width": "1100px", margin: "0 auto" }}>
        <h2 style={{ "text-align": "center", "font-size": "32px", "font-weight": 700, "margin-bottom": "48px" }}>Everything you need to ship</h2>
        <div style={{ display: "grid", "grid-template-columns": "repeat(auto-fit, minmax(300px, 1fr))", gap: "24px" }}>
          <FeatureCard
            title="AI Architecture Planning"
            description="Describe your problem. Our AI planner asks the right questions, proposes architecture, and recommends the best approach — RAG, agents, workflows, or classic apps."
            icon="&#9881;"
          />
          <FeatureCard
            title="Code Generation"
            description="Once approved, a 4-agent pipeline builds your application: planner, builder, reviewer, and fixer. Complete with tests, docs, and deployment config."
            icon="&#128187;"
          />
          <FeatureCard
            title="LLM Deployment"
            description="Deploy any open-source LLM to RunPod, Modal, or Azure with GPU optimization. Real-time pricing search and automated provisioning."
            icon="&#128640;"
          />
          <FeatureCard
            title="Sandbox Isolation"
            description="Every task runs in its own Daytona sandbox — an ephemeral container with dedicated CPU, memory, and network. Zero cross-contamination."
            icon="&#128737;"
          />
          <FeatureCard
            title="Multi-Provider Support"
            description="RunPod serverless, Modal, Azure VMs, AKS, ACA, NVIDIA NIM — the agent picks the optimal deployment based on your budget and latency needs."
            icon="&#9729;"
          />
          <FeatureCard
            title="Real-Time Progress"
            description="Watch your project being built or deployed in real-time via WebSocket streaming. Every step is visible, from planning to verification."
            icon="&#9889;"
          />
        </div>
      </section>

      {/* How it Works */}
      <section id="how-it-works" style={{ padding: "80px 40px", background: "#0f0f11" }}>
        <div style={{ "max-width": "800px", margin: "0 auto" }}>
          <h2 style={{ "text-align": "center", "font-size": "32px", "font-weight": 700, "margin-bottom": "48px" }}>How it works</h2>
          <div style={{ display: "flex", "flex-direction": "column", gap: "32px" }}>
            <Step number={1} title="Describe your idea" description="Start a session and tell us what you want to build in plain language." />
            <Step number={2} title="Answer clarifying questions" description="The AI asks 3-5 targeted questions to nail down requirements and constraints." />
            <Step number={3} title="Review the proposal" description="Get a full architecture proposal with stack, components, risks, alternatives, and cost." />
            <Step number={4} title="Approve and build" description="Hit approve. The system routes to code generation or LLM deployment, runs autonomously, and verifies the result." />
          </div>
        </div>
      </section>

      {/* CTA */}
      <section style={{ padding: "80px 40px", "text-align": "center" }}>
        <h2 style={{ "font-size": "28px", "font-weight": 700, "margin-bottom": "16px" }}>Ready to ship faster?</h2>
        <p style={{ color: "#a1a1aa", "margin-bottom": "32px" }}>Start building in under a minute. No credit card required.</p>
        <button
          onClick={handleGetStarted}
          style={{ background: "#6366f1", color: "white", border: "none", padding: "14px 32px", "border-radius": "8px", "font-size": "16px", "font-weight": 600, cursor: "pointer" }}
        >
          Get Started Free
        </button>
      </section>

      {/* Footer */}
      <footer style={{ padding: "40px", "border-top": "1px solid #1f1f23", "text-align": "center", color: "#52525b", "font-size": "13px" }}>
        FDE Platform &middot; Built with AI, verified by humans.
      </footer>
    </div>
  );
}

function FeatureCard(props: { title: string; description: string; icon: string }) {
  return (
    <div style={{ background: "#18181b", border: "1px solid #27272a", "border-radius": "12px", padding: "24px" }}>
      <div style={{ "font-size": "28px", "margin-bottom": "12px" }}>{props.icon}</div>
      <h3 style={{ "font-size": "16px", "font-weight": 600, "margin-bottom": "8px", color: "#fafafa" }}>{props.title}</h3>
      <p style={{ color: "#a1a1aa", "font-size": "14px", "line-height": 1.5, margin: 0 }}>{props.description}</p>
    </div>
  );
}

function Step(props: { number: number; title: string; description: string }) {
  return (
    <div style={{ display: "flex", gap: "16px", "align-items": "flex-start" }}>
      <div style={{ width: "32px", height: "32px", "border-radius": "50%", background: "#6366f1", color: "white", display: "flex", "align-items": "center", "justify-content": "center", "font-weight": 700, "font-size": "14px", "flex-shrink": 0 }}>
        {props.number}
      </div>
      <div>
        <h4 style={{ margin: "0 0 4px", "font-size": "16px", "font-weight": 600 }}>{props.title}</h4>
        <p style={{ margin: 0, color: "#a1a1aa", "font-size": "14px" }}>{props.description}</p>
      </div>
    </div>
  );
}
