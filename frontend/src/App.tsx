const baselineCards = [
  {
    title: "Secure Operator Access",
    detail: "Single-user admin workflow with a protected shell, local bootstrap, and account settings."
  },
  {
    title: "Newsletter Control Plane",
    detail: "Each newsletter will carry its own prompt, template, provider settings, and schedule."
  },
  {
    title: "Run-first Operations",
    detail: "Manual sends, future schedules, and auditability share one execution history rather than separate flows."
  }
];

export default function App() {
  return (
    <div className="app-shell">
      <main className="hero">
        <section className="hero-copy">
          <p className="eyebrow">Pulse News</p>
          <h1>Newsletter operations for one operator, one control plane, one container.</h1>
          <p className="lede">
            This foundation phase establishes the authenticated app shell, database
            baseline, and deployment shape that later phases will turn into a full
            newsletter workflow.
          </p>
        </section>

        <section className="status-panel" aria-label="Phase status">
          <div className="status-metric">
            <span className="status-label">Current phase</span>
            <strong>Foundation and Secure Control Plane</strong>
          </div>
          <div className="status-grid">
            <div>
              <span className="status-label">Backend</span>
              <strong>FastAPI shell</strong>
            </div>
            <div>
              <span className="status-label">Frontend</span>
              <strong>React + Vite shell</strong>
            </div>
            <div>
              <span className="status-label">Persistence</span>
              <strong>SQLite baseline</strong>
            </div>
            <div>
              <span className="status-label">Packaging</span>
              <strong>Single Docker image</strong>
            </div>
          </div>
        </section>
      </main>

      <section className="card-grid" aria-label="Roadmap themes">
        {baselineCards.map((card) => (
          <article className="info-card" key={card.title}>
            <h2>{card.title}</h2>
            <p>{card.detail}</p>
          </article>
        ))}
      </section>
    </div>
  );
}
