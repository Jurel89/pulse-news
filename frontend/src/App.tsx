import { useEffect, useMemo, useState } from "react";

import { RunDashboardPage } from "./features/dashboard/RunDashboardPage";
import { LoginPage } from "./features/auth/LoginPage";
import { NewsletterEditorPage } from "./features/newsletters/NewsletterEditorPage";
import { NewsletterListPage } from "./features/newsletters/NewsletterListPage";
import { NewsletterPreviewPage } from "./features/newsletters/NewsletterPreviewPage";
import type { NewsletterSummary, NewsletterDetail, NewsletterInput } from "./features/newsletters/newsletter-types";
import { AccountPage } from "./features/settings/AccountPage";
import { EmailTemplatesPage, EmailTemplateEditor } from "./features/templates/EmailTemplatesPage";
import { ProvidersPage, ProviderEditor } from "./features/providers/ProvidersPage";
import { ApiKeysPage, ApiKeyEditor } from "./features/api-keys/ApiKeysPage";
import type { EmailTemplateSummary, EmailTemplateDetail, EmailTemplateInput } from "./features/templates/template-types";
import type { ProviderSummary, ProviderDetail, ProviderInput } from "./features/providers/provider-types";
import type { ApiKeySummary, ApiKeyDetail, ApiKeyInput } from "./features/api-keys/api-key-types";
import { api } from "./lib/api";
import { asLoadedSession, initialSessionState, type SessionState } from "./lib/session";

type ActiveView = "dashboard" | "newsletters" | "templates" | "providers" | "apikeys" | "account";

export default function App() {
  const [session, setSession] = useState<SessionState>(initialSessionState);
  const [busy, setBusy] = useState(false);
  const [newslettersLoading, setNewslettersLoading] = useState(false);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [providersLoading, setProvidersLoading] = useState(false);
  const [apiKeysLoading, setApiKeysLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<ActiveView>("dashboard");
  const [newsletters, setNewsletters] = useState<NewsletterSummary[]>([]);
  const [templates, setTemplates] = useState<EmailTemplateSummary[]>([]);
  const [providers, setProviders] = useState<ProviderSummary[]>([]);
  const [apiKeys, setApiKeys] = useState<ApiKeySummary[]>([]);
  const [editingNewsletter, setEditingNewsletter] = useState<NewsletterDetail | null>(null);
  const [previewingNewsletter, setPreviewingNewsletter] = useState<NewsletterSummary | null>(null);
  const [showEditor, setShowEditor] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<EmailTemplateDetail | null>(null);
  const [showTemplateEditor, setShowTemplateEditor] = useState(false);
  const [editingProvider, setEditingProvider] = useState<ProviderDetail | null>(null);
  const [showProviderEditor, setShowProviderEditor] = useState(false);
  const [editingApiKey, setEditingApiKey] = useState<ApiKeyDetail | null>(null);
  const [showApiKeyEditor, setShowApiKeyEditor] = useState(false);

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

  async function loadTemplates() {
    setTemplatesLoading(true);
    try {
      const nextTemplates = await api.emailTemplates.list();
      setTemplates(nextTemplates);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load templates.");
    } finally {
      setTemplatesLoading(false);
    }
  }

  async function loadProviders() {
    setProvidersLoading(true);
    try {
      const nextProviders = await api.providers.list();
      setProviders(nextProviders);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load providers.");
    } finally {
      setProvidersLoading(false);
    }
  }

  async function loadApiKeys() {
    setApiKeysLoading(true);
    try {
      const nextApiKeys = await api.apiKeys.list();
      setApiKeys(nextApiKeys);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load API keys.");
    } finally {
      setApiKeysLoading(false);
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
      resetAllEditors();
      setActiveView("dashboard");
    });
  }

  function resetAllEditors() {
    setEditingNewsletter(null);
    setPreviewingNewsletter(null);
    setShowEditor(false);
    setEditingTemplate(null);
    setShowTemplateEditor(false);
    setEditingProvider(null);
    setShowProviderEditor(false);
    setEditingApiKey(null);
    setShowApiKeyEditor(false);
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
      { id: "templates" as const, label: "Templates" },
      { id: "providers" as const, label: "Providers" },
      { id: "apikeys" as const, label: "API Keys" },
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

  async function handleSaveTemplate(payload: EmailTemplateInput, templateId?: number) {
    await runAuthAction(async () => {
      if (templateId) {
        await api.emailTemplates.update(templateId, payload);
      } else {
        await api.emailTemplates.create(payload);
      }
      await loadTemplates();
      setNotice(`Template ${templateId ? "updated" : "created"} successfully.`);
      setEditingTemplate(null);
      setShowTemplateEditor(false);
      setActiveView("templates");
    });
  }

  async function handleDeleteTemplate(templateId: number) {
    await runAuthAction(async () => {
      await api.emailTemplates.delete(templateId);
      await loadTemplates();
    });
  }

  async function handleSetDefaultTemplate(templateId: number) {
    await runAuthAction(async () => {
      await api.emailTemplates.setDefault(templateId);
      await loadTemplates();
      setNotice("Default template updated.");
    });
  }

  async function handleSaveProvider(payload: ProviderInput, providerId?: number) {
    await runAuthAction(async () => {
      if (providerId) {
        await api.providers.update(providerId, payload);
      } else {
        await api.providers.create(payload);
      }
      await loadProviders();
      setNotice(`Provider ${providerId ? "updated" : "created"} successfully.`);
      setEditingProvider(null);
      setShowProviderEditor(false);
      setActiveView("providers");
    });
  }

  async function handleDeleteProvider(providerId: number) {
    await runAuthAction(async () => {
      await api.providers.delete(providerId);
      await loadProviders();
    });
  }

  async function handleToggleProvider(providerId: number, enabled: boolean) {
    await runAuthAction(async () => {
      const provider = providers.find(p => p.id === providerId);
      if (!provider) return;
        await api.providers.update(providerId, {
          name: provider.name,
          provider_type: provider.provider_type,
          is_enabled: enabled,
          description: provider.description ?? "",
          default_model: provider.default_model ?? ""
        });
      await loadProviders();
    });
  }

  async function handleSaveApiKey(payload: ApiKeyInput, apiKeyId?: number) {
    await runAuthAction(async () => {
      if (apiKeyId) {
        await api.apiKeys.update(apiKeyId, payload);
      } else {
        await api.apiKeys.create(payload);
      }
      await loadApiKeys();
      setNotice(`API key ${apiKeyId ? "updated" : "created"} successfully.`);
      setEditingApiKey(null);
      setShowApiKeyEditor(false);
      setActiveView("apikeys");
    });
  }

  async function handleDeleteApiKey(apiKeyId: number) {
    await runAuthAction(async () => {
      await api.apiKeys.delete(apiKeyId);
      await loadApiKeys();
    });
  }

  async function handleToggleApiKey(apiKeyId: number, active: boolean) {
    await runAuthAction(async () => {
      const apiKey = apiKeys.find(k => k.id === apiKeyId);
      if (!apiKey) return;
      await api.apiKeys.update(apiKeyId, {
        name: apiKey.name,
        provider_type: apiKey.provider_type,
        key_value: null as unknown as string,
        is_active: active
      });
      await loadApiKeys();
    });
  }

  function handleNavClick(view: ActiveView) {
    if (view !== activeView) {
      setError(null);
      setNotice(null);
      resetAllEditors();
    }
    setActiveView(view);
    if (view === "templates" && templates.length === 0) {
      void loadTemplates();
    } else if (view === "providers" && providers.length === 0) {
      void loadProviders();
    } else if (view === "apikeys" && apiKeys.length === 0) {
      void loadApiKeys();
    }
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

  const currentUser = session.user!;
  if (!currentUser) {
    return null;
  }

  function renderContent() {
    switch (activeView) {
      case "account":
        return (
          <AccountPage
            busy={busy}
            currentUser={currentUser}
            error={error}
            notice={notice}
            onChangePassword={handleChangePassword}
            onLogout={handleLogout}
          />
        );

      case "templates":
        if (showTemplateEditor) {
          return (
            <EmailTemplateEditor
              initialTemplate={editingTemplate}
              onCancel={() => {
                setEditingTemplate(null);
                setShowTemplateEditor(false);
              }}
              onSave={handleSaveTemplate}
            />
          );
        }
        return (
          <EmailTemplatesPage
            templates={templates}
            loading={templatesLoading}
            error={error}
            onDismissError={() => setError(null)}
            onCreate={() => {
              setEditingTemplate(null);
              setShowTemplateEditor(true);
            }}
            onEdit={async (template) => {
              try {
                const detail = await api.emailTemplates.get(template.id);
                setEditingTemplate(detail);
                setShowTemplateEditor(true);
              } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to load template details.");
              }
            }}
            onDelete={handleDeleteTemplate}
            onSetDefault={handleSetDefaultTemplate}
            onRefresh={loadTemplates}
          />
        );

      case "providers":
        if (showProviderEditor) {
          return (
            <ProviderEditor
              initialProvider={editingProvider}
              error={error}
              onDismissError={() => setError(null)}
              onCancel={() => {
                setEditingProvider(null);
                setShowProviderEditor(false);
              }}
              onSave={handleSaveProvider}
            />
          );
        }
        return (
          <ProvidersPage
            providers={providers}
            loading={providersLoading}
            error={error}
            onDismissError={() => setError(null)}
            onCreate={() => {
              setEditingProvider(null);
              setShowProviderEditor(true);
            }}
            onEdit={async (provider) => {
              try {
                const detail = await api.providers.get(provider.id);
                setEditingProvider(detail);
                setShowProviderEditor(true);
              } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to load provider details.");
              }
            }}
            onDelete={handleDeleteProvider}
            onToggleEnabled={handleToggleProvider}
          />
        );

      case "apikeys":
        if (showApiKeyEditor) {
          return (
            <ApiKeyEditor
              initialApiKey={editingApiKey}
              onCancel={() => {
                setEditingApiKey(null);
                setShowApiKeyEditor(false);
              }}
              onSave={handleSaveApiKey}
            />
          );
        }
        return (
          <ApiKeysPage
            apiKeys={apiKeys}
            loading={apiKeysLoading}
            error={error}
            onDismissError={() => setError(null)}
            onCreate={() => {
              setEditingApiKey(null);
              setShowApiKeyEditor(true);
            }}
            onEdit={async (apiKey) => {
              try {
                const detail = await api.apiKeys.get(apiKey.id);
                setEditingApiKey(detail);
                setShowApiKeyEditor(true);
              } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to load API key details.");
              }
            }}
            onDelete={handleDeleteApiKey}
            onToggleActive={handleToggleApiKey}
          />
        );

      case "newsletters":
        if (previewingNewsletter) {
          return (
            <NewsletterPreviewPage
              newsletter={previewingNewsletter}
              onBack={() => setPreviewingNewsletter(null)}
            />
          );
        }
        if (showEditor) {
          return (
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
          );
        }
        return (
          <NewsletterListPage
            items={newsletters}
            loading={newslettersLoading}
            error={error}
            onDismissError={() => setError(null)}
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
        );

      default:
        return <RunDashboardPage newsletters={newsletters} />;
    }
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
              onClick={() => handleNavClick(item.id)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </nav>
      </header>

      {renderContent()}
    </div>
  );
}
