import { FormEvent, useState } from "react";

import type { UserSummary } from "../../lib/api";

type OperationMode = "live" | "simulated";

type AccountPageProps = {
  busy: boolean;
  currentUser: UserSummary;
  error: string | null;
  notice: string | null;
  aiGenerationMode: OperationMode;
  emailDeliveryMode: OperationMode;
  onChangePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  onChangeOperationModes: (modes: {
    ai_generation_mode?: OperationMode;
    email_delivery_mode?: OperationMode;
  }) => Promise<void>;
  onLogout: () => Promise<void>;
};

export function AccountPage({
  busy,
  currentUser,
  error,
  notice,
  aiGenerationMode,
  emailDeliveryMode,
  onChangePassword,
  onChangeOperationModes,
  onLogout
}: AccountPageProps) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onChangePassword(currentPassword, newPassword);
    setCurrentPassword("");
    setNewPassword("");
  }

  function describeMode(mode: OperationMode, domain: "ai" | "email") {
    if (domain === "ai") {
      return mode === "live"
        ? "Live mode uses configured AI providers to generate real drafts."
        : "Simulated mode generates local fallback drafts without requiring live AI keys.";
    }

    return mode === "live"
      ? "Live mode sends real emails when delivery credentials are configured."
      : "Simulated mode keeps delivery in preview-only flows without sending real emails.";
  }

  return (
    <section className="settings-card">
      <header className="settings-header">
        <div>
          <p className="eyebrow">Account</p>
          <h2>{currentUser.email}</h2>
        </div>
        <button className="secondary-button" disabled={busy} onClick={() => void onLogout()} type="button">
          Log Out
        </button>
      </header>

      <div className="form-section">
        <h3 className="form-section-title">Operation Mode</h3>
        <label>
          <span>AI generation mode</span>
          <div className="checkbox-row" style={{ margin: "var(--sp-2) 0 var(--sp-3)" }}>
            <span
              className={aiGenerationMode === "live" ? "status-badge status-active" : "status-badge status-paused"}
              style={{ textTransform: "uppercase" }}
            >
              {aiGenerationMode === "simulated" ? "simulation" : aiGenerationMode}
            </span>
            <span className="help-text" style={{ color: "var(--color-text-secondary)", fontSize: "var(--font-sm)" }}>
              {describeMode(aiGenerationMode, "ai")}
            </span>
          </div>
          <select
            disabled={busy}
            onChange={(event) =>
              void onChangeOperationModes({
                ai_generation_mode: event.target.value as OperationMode,
              })
            }
            value={aiGenerationMode}
          >
            <option value="live">Live</option>
            <option value="simulated">Simulation</option>
          </select>
        </label>

        <label>
          <span>Email delivery mode</span>
          <div className="checkbox-row" style={{ margin: "var(--sp-2) 0 var(--sp-3)" }}>
            <span
              className={emailDeliveryMode === "live" ? "status-badge status-active" : "status-badge status-paused"}
              style={{ textTransform: "uppercase" }}
            >
              {emailDeliveryMode === "simulated" ? "simulation" : emailDeliveryMode}
            </span>
            <span className="help-text" style={{ color: "var(--color-text-secondary)", fontSize: "var(--font-sm)" }}>
              {describeMode(emailDeliveryMode, "email")}
            </span>
          </div>
          <select
            disabled={busy}
            onChange={(event) =>
              void onChangeOperationModes({
                email_delivery_mode: event.target.value as OperationMode,
              })
            }
            value={emailDeliveryMode}
          >
            <option value="live">Live</option>
            <option value="simulated">Simulation</option>
          </select>
        </label>
      </div>

      <hr className="form-divider" />

      <form className="auth-form" onSubmit={handleSubmit}>
        <h3 className="form-section-title">Security</h3>
        <label>
          <span>Current password</span>
          <input
            autoComplete="current-password"
            disabled={busy}
            onChange={(event) => setCurrentPassword(event.target.value)}
            required
            type="password"
            value={currentPassword}
          />
        </label>

        <label>
          <span>New password</span>
          <input
            autoComplete="new-password"
            disabled={busy}
            minLength={12}
            onChange={(event) => setNewPassword(event.target.value)}
            required
            type="password"
            value={newPassword}
          />
        </label>

        {error ? <p className="form-error">{error}</p> : null}
        {notice ? <p className="form-notice">{notice}</p> : null}

        <button className="primary-button" disabled={busy} type="submit">
          {busy ? "Updating..." : "Change Password"}
        </button>
      </form>
    </section>
  );
}
