import { useEffect, useMemo, useState } from "react";

import { RunDashboardPage } from "./features/dashboard/RunDashboardPage";
import { LoginPage } from "./features/auth/LoginPage";
import { NewsletterEditorPage } from "./features/newsletters/NewsletterEditorPage";
import { NewsletterListPage } from "./features/newsletters/NewsletterListPage";
import { NewsletterPreviewPage } from "./features/newsletters/NewsletterPreviewPage";
import type { NewsletterSummary, NewsletterDetail, NewsletterInput } from "./features/newsletters/newsletter-types";
import { AccountPage } from "./features/settings/AccountPage";
import { api } from "./lib/api";
import { asLoadedSession, initialSessionState, type SessionState } from "./lib/session";

type ActiveView = "dashboard" | "newsletters" | "account";

export default function App() {
  const [session, setSession] = useState<SessionState>(initialSessionState);
  const [busy, setBusy] = useState(false);
  const [newslettersLoading, setNewslettersLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<ActiveView>("dashboard");
  const [newsletters, setNewsletters] = useState<NewsletterSummary[]>([]);
  const [editingNewsletter, setEditingNewsletter] = useState<NewsletterDetail | null>(null);
  const [previewingNewsletter, setPreviewingNewsletter] = useState<NewsletterSummary | null>(null);
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
    setNewslettersLoading(true);
    try {
      const nextNewsletters = await api.listNewsletters();
      setNewsletters(nextNewsletters);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load newsletters.");
    } finally {
      setNewslettersLoading(false);
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

  async function handleAuthSubmit(email: string, password: string, bootstrapSecret?: string) {
    await runAuthAction(async () => {
      const nextSession = session.initialized
        ? await api.login(email, password)
        : await api.bootstrap(email, password, bootstrapSecret);
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
      setPreviewingNewsletter(null);
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
      void savedNewsletter;
      await loadNewsletters();
      setNotice(`Newsletter ${newsletterId ? "updated" : "created"} successfully.`);
      setEditingNewsletter(null);
      setPreviewingNewsletter(null);
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

  async function handleScheduleResume(newsletterId: number) {
    await runAuthAction(async () => {
      const updatedNewsletter = await api.resumeNewsletterSchedule(newsletterId);
      setNewsletters((current) =>
        current.map((item) => (item.id === updatedNewsletter.id ? updatedNewsletter : item)),
      );
    });
  }

  async function handleSchedulePause(newsletterId: number) {
    await runAuthAction(async () => {
      const updatedNewsletter = await api.pauseNewsletterSchedule(newsletterId);
      setNewsletters((current) =>
        current.map((item) => (item.id === updatedNewsletter.id ? updatedNewsletter : item)),
      );
    });
  }

  async function handleGenerateNewsletter(newsletterId: number) {
    await runAuthAction(async () => {
      const result = await api.generateNewsletter(newsletterId);
      await loadNewsletters();
      setEditingNewsletter(result.newsletter);
      setNotice(result.message);
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
          <h1 className="app-title">Newsletter Operations</h1>
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
        previewingNewsletter ? (
          <NewsletterPreviewPage
            newsletter={previewingNewsletter}
            onBack={() => setPreviewingNewsletter(null)}
          />
        ) : showEditor ? (
          <NewsletterEditorPage
            busy={busy}
            initialNewsletter={editingNewsletter}
            onCancel={() => {
              setEditingNewsletter(null);
              setShowEditor(false);
            }}
            onGenerate={editingNewsletter ? () => handleGenerateNewsletter(editingNewsletter.id) : undefined}
            onSave={handleSaveNewsletter}
          />
        ) : (
          <NewsletterListPage
            items={newsletters}
            loading={newslettersLoading}
            error={error}
            onArchive={handleArchiveNewsletter}
            onCreate={() => {
              setEditingNewsletter(null);
              setShowEditor(true);
            }}
            onDelete={handleDeleteNewsletter}
            onEdit={async (newsletter) => {
              try {
                const detail = await api.getNewsletter(newsletter.id);
                setEditingNewsletter(detail);
                setShowEditor(true);
              } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to load newsletter details.");
              }
            }}
            onPreview={(newsletter) => {
              setPreviewingNewsletter(newsletter);
              setShowEditor(false);
            }}
            onPause={handlePauseNewsletter}
            onSchedulePause={handleSchedulePause}
            onScheduleResume={handleScheduleResume}
          />
        )
      ) : (
        <RunDashboardPage newsletters={newsletters} />
      )}
    </div>
  );
}
