import { useEffect, useMemo, useState } from "react";

import { LoginPage } from "./features/auth/LoginPage";
import { AccountPage } from "./features/settings/AccountPage";
import { api } from "./lib/api";
import { asLoadedSession, initialSessionState, type SessionState } from "./lib/session";

const baselineCards = [
  {
    title: "Secure Operator Access",
    detail: "Single-user admin workflow with a protected shell, local bootstrap, and account settings."
  },
  {
    title: "Newsletter Control Plane",
    detail: "Newsletter CRUD lands next, on top of this protected shell."
  },
  {
    title: "Run-first Operations",
    detail: "Later phases will add generation, sends, schedules, and audit history on the same execution model."
  }
];

type ActiveView = "dashboard" | "account";

export default function App() {
  const [session, setSession] = useState<SessionState>(initialSessionState);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<ActiveView>("dashboard");

  useEffect(() => {
    void refreshSession();
  }, []);

  async function refreshSession() {
    try {
      const nextSession = await api.getSession();
      setSession(asLoadedSession(nextSession));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to reach the backend.");
      setSession({ ...initialSessionState, loading: false });
    }
  }

  async function runAuthAction(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Request failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleAuthSubmit(email: string, password: string) {
    await runAuthAction(async () => {
      const nextSession = session.initialized
        ? await api.login(email, password)
        : await api.bootstrap(email, password);
      setSession(asLoadedSession(nextSession));
      setActiveView("dashboard");
    });
  }

  async function handleLogout() {
    await runAuthAction(async () => {
      await api.logout();
      const nextSession = await api.getSession();
      setSession(asLoadedSession(nextSession));
      setActiveView("dashboard");
    });
  }

  async function handleChangePassword(currentPassword: string, newPassword: string) {
    await runAuthAction(async () => {
      const result = await api.changePassword(currentPassword, newPassword);
      setNotice(result.message);
    });
  }

  const navItems = useMemo(
    () => [
      { id: "dashboard" as const, label: "Dashboard" },
      { id: "account" as const, label: "Account" }
    ],
    [],
  );

  if (session.loading) {
    return (
      <div className="app-shell">
        <main className="hero">
          <section className="hero-copy">
            <p className="eyebrow">Pulse News</p>
            <h1>Loading the operator shell.</h1>
            <p className="lede">Checking whether the backend is ready and whether an operator session exists.</p>
          </section>
        </main>
      </div>
    );
  }

  if (!session.authenticated) {
    return (
      <div className="app-shell auth-layout">
        <LoginPage
          busy={busy}
          error={error}
          initialized={session.initialized}
          onSubmit={handleAuthSubmit}
        />
      </div>
    );
  }

  const currentUser = session.user;
  if (!currentUser) {
    return null;
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Pulse News</p>
          <h1 className="app-title">Foundation and Secure Control Plane</h1>
        </div>

        <nav className="nav-pills" aria-label="Primary">
          {navItems.map((item) => (
            <button
              className={item.id === activeView ? "nav-pill active" : "nav-pill"}
              key={item.id}
              onClick={() => setActiveView(item.id)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </nav>
      </header>

      {activeView === "account" ? (
        <AccountPage
          busy={busy}
          currentUser={currentUser}
          error={error}
          notice={notice}
          onChangePassword={handleChangePassword}
          onLogout={handleLogout}
        />
      ) : (
        <>
          <main className="hero">
            <section className="hero-copy">
              <h2 className="section-title">Authenticated operator shell is active.</h2>
              <p className="lede">
                The app now protects the admin surface with a real operator account. The next
                plan adds the actual newsletter CRUD workspace on top of this shell.
              </p>
            </section>

            <section className="status-panel" aria-label="Current status">
              <div className="status-metric">
                <span className="status-label">Signed in as</span>
                <strong>{currentUser.email}</strong>
              </div>
              <div className="status-grid">
                <div>
                  <span className="status-label">Shell</span>
                  <strong>Protected</strong>
                </div>
                <div>
                  <span className="status-label">Bootstrap</span>
                  <strong>{session.initialized ? "Locked" : "Open"}</strong>
                </div>
                <div>
                  <span className="status-label">Phase 1</span>
                  <strong>Plan 02 complete</strong>
                </div>
                <div>
                  <span className="status-label">Next</span>
                  <strong>Newsletter CRUD</strong>
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
        </>
      )}
    </div>
  );
}
