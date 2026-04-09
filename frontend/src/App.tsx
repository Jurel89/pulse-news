import { useEffect, useMemo, useState } from "react";

import { LoginPage } from "./features/auth/LoginPage";
import { NewsletterEditorPage } from "./features/newsletters/NewsletterEditorPage";
import { NewsletterListPage } from "./features/newsletters/NewsletterListPage";
import type { Newsletter, NewsletterInput } from "./features/newsletters/newsletter-types";
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

type ActiveView = "dashboard" | "newsletters" | "account";

export default function App() {
  const [session, setSession] = useState<SessionState>(initialSessionState);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<ActiveView>("dashboard");
  const [newsletters, setNewsletters] = useState<Newsletter[]>([]);
  const [editingNewsletter, setEditingNewsletter] = useState<Newsletter | null>(null);
  const [showEditor, setShowEditor] = useState(false);

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

  useEffect(() => {
    if (!session.authenticated) {
      setNewsletters([]);
      return;
    }
    void loadNewsletters();
  }, [session.authenticated]);

  async function loadNewsletters() {
    try {
      const nextNewsletters = await api.listNewsletters();
      setNewsletters(nextNewsletters);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load newsletters.");
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
      setEditingNewsletter(null);
      setShowEditor(false);
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
      { id: "newsletters" as const, label: "Newsletters" },
      { id: "account" as const, label: "Account" }
    ],
    [],
  );

  async function handleSaveNewsletter(payload: NewsletterInput, newsletterId?: number) {
    await runAuthAction(async () => {
      const savedNewsletter = newsletterId
        ? await api.updateNewsletter(newsletterId, payload)
        : await api.createNewsletter(payload);

      setNewsletters((current) => {
        const existingIndex = current.findIndex((item) => item.id === savedNewsletter.id);
        if (existingIndex === -1) {
          return [savedNewsletter, ...current];
        }

        const next = [...current];
        next[existingIndex] = savedNewsletter;
        return next;
      });
      setNotice(`Newsletter ${newsletterId ? "updated" : "created"} successfully.`);
      setEditingNewsletter(null);
      setShowEditor(false);
      setActiveView("newsletters");
    });
  }

  async function handlePauseNewsletter(newsletterId: number) {
    await runAuthAction(async () => {
      const updatedNewsletter = await api.pauseNewsletter(newsletterId);
      setNewsletters((current) =>
        current.map((item) => (item.id === updatedNewsletter.id ? updatedNewsletter : item)),
      );
    });
  }

  async function handleArchiveNewsletter(newsletterId: number) {
    await runAuthAction(async () => {
      const updatedNewsletter = await api.archiveNewsletter(newsletterId);
      setNewsletters((current) =>
        current.map((item) => (item.id === updatedNewsletter.id ? updatedNewsletter : item)),
      );
    });
  }

  async function handleDeleteNewsletter(newsletterId: number) {
    await runAuthAction(async () => {
      await api.deleteNewsletter(newsletterId);
      setNewsletters((current) => current.filter((item) => item.id !== newsletterId));
    });
  }

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
      ) : activeView === "newsletters" ? (
        showEditor ? (
          <NewsletterEditorPage
            busy={busy}
            initialNewsletter={editingNewsletter}
            onCancel={() => {
              setEditingNewsletter(null);
              setShowEditor(false);
            }}
            onSave={handleSaveNewsletter}
          />
        ) : (
          <NewsletterListPage
            items={newsletters}
            onArchive={handleArchiveNewsletter}
            onCreate={() => {
              setEditingNewsletter(null);
              setShowEditor(true);
            }}
            onDelete={handleDeleteNewsletter}
            onEdit={(newsletter) => {
              setEditingNewsletter(newsletter);
              setShowEditor(true);
            }}
            onPause={handlePauseNewsletter}
          />
        )
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
                  <strong>Plan 03 active</strong>
                </div>
                <div>
                  <span className="status-label">Next</span>
                  <strong>{newsletters.length} newsletters tracked</strong>
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
