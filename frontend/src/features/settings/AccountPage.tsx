import { FormEvent, useState } from "react";

import type { UserSummary } from "../../lib/api";

type AccountPageProps = {
  busy: boolean;
  currentUser: UserSummary;
  error: string | null;
  notice: string | null;
  onChangePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  onLogout: () => Promise<void>;
};

export function AccountPage({
  busy,
  currentUser,
  error,
  notice,
  onChangePassword,
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

      <form className="auth-form" onSubmit={handleSubmit}>
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
