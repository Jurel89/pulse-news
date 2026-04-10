import { FormEvent, useMemo, useState } from "react";

type LoginPageProps = {
  initialized: boolean;
  busy: boolean;
  error: string | null;
  onSubmit: (email: string, password: string, bootstrapSecret?: string) => Promise<void>;
};

export function LoginPage({ initialized, busy, error, onSubmit }: LoginPageProps) {
  const [email, setEmail] = useState("operator@example.com");
  const [password, setPassword] = useState("");
  const [bootstrapSecret, setBootstrapSecret] = useState("");
  const title = useMemo(
    () => (initialized ? "Log in to Pulse News" : "Create the first operator account"),
    [initialized],
  );
  const buttonLabel = initialized ? "Log In" : "Create Operator Account";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit(email, password, initialized ? undefined : bootstrapSecret || undefined);
  }

  return (
    <section className="auth-card">
      <div className="auth-copy">
        <p className="eyebrow">{initialized ? "Operator access" : "First-run setup"}</p>
        <h2>{title}</h2>
        <p>
          {initialized
            ? "Use the single local operator account to access the newsletter console."
            : "Bootstrap the protected admin account once. After this step, the bootstrap route locks automatically."}
        </p>
      </div>

      <form className="auth-form" onSubmit={handleSubmit}>
        <label>
          <span>Email</span>
          <input
            autoComplete="email"
            disabled={busy}
            onChange={(event) => setEmail(event.target.value)}
            type="email"
            value={email}
          />
        </label>

        <label>
          <span>Password</span>
          <input
            autoComplete={initialized ? "current-password" : "new-password"}
            disabled={busy}
            minLength={12}
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
        </label>

        {!initialized ? (
          <label>
            <span>Bootstrap Secret (if required)</span>
            <input
              autoComplete="off"
              disabled={busy}
              onChange={(event) => setBootstrapSecret(event.target.value)}
              placeholder="Leave blank if not configured"
              type="password"
              value={bootstrapSecret}
            />
          </label>
        ) : null}

        {error ? <p className="form-error">{error}</p> : null}

        <button className="primary-button" disabled={busy} type="submit">
          {busy ? "Working..." : buttonLabel}
        </button>
      </form>
    </section>
  );
}
