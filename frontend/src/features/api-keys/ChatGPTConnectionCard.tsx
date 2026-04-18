import { useState } from "react";
import type { ApiKeySummary } from "./api-key-types";
import { api } from "../../lib/api";

type Props = {
  apiKey: ApiKeySummary;
  onDisconnected: () => void;
  onRefreshed: () => void;
};

function formatExpiry(expiresAt: string | null, expiresInSeconds: number | null): string {
  if (expiresInSeconds != null) {
    if (expiresInSeconds <= 0) return "Expired";
    const hours = Math.floor(expiresInSeconds / 3600);
    const minutes = Math.floor((expiresInSeconds % 3600) / 60);
    if (hours > 0) return `Expires in ${hours}h ${minutes}m`;
    return `Expires in ${minutes}m`;
  }
  if (expiresAt) {
    return `Expires ${new Date(expiresAt).toLocaleString()}`;
  }
  return "Unknown expiry";
}

export function ChatGPTConnectionCard({ apiKey, onDisconnected, onRefreshed }: Props) {
  const [refreshing, setRefreshing] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [expiresInSeconds, setExpiresInSeconds] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleRefresh() {
    setRefreshing(true);
    setError(null);
    try {
      const result = await api.oauthOpenai.refresh(apiKey.id);
      setExpiresInSeconds(result.expires_in_seconds);
      onRefreshed();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Refresh failed";
      setError(message);
    } finally {
      setRefreshing(false);
    }
  }

  async function handleDisconnect() {
    setDisconnecting(true);
    setError(null);
    try {
      await api.oauthOpenai.delete(apiKey.id);
      onDisconnected();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Disconnect failed";
      setError(message);
    } finally {
      setDisconnecting(false);
    }
  }

  const plan = apiKey.oauth_plan_type ?? "Connected";
  const accountSuffix = apiKey.oauth_account_id
    ? `\u2026${apiKey.oauth_account_id.slice(-8)}`
    : null;

  return (
    <article className="newsletter-card">
      <div className="newsletter-card-header">
        <div>
          <h3>{apiKey.name}</h3>
          <p>ChatGPT subscription via OAuth</p>
        </div>
        <span className="status-chip status-active">Connected</span>
      </div>

      <dl className="newsletter-meta">
        <div>
          <dt>Plan</dt>
          <dd>{plan}</dd>
        </div>
        {accountSuffix && (
          <div>
            <dt>Account</dt>
            <dd>{accountSuffix}</dd>
          </div>
        )}
        <div>
          <dt>Token</dt>
          <dd>
            {formatExpiry(
              apiKey.oauth_expires_at,
              expiresInSeconds ?? (apiKey.oauth_expires_at
                ? Math.max(0, Math.floor((new Date(apiKey.oauth_expires_at).getTime() - Date.now()) / 1000))
                : null)
            )}
          </dd>
        </div>
      </dl>

      {error && (
        <div className="error-banner" style={{ marginBottom: 12 }}>
          <span>{error}</span>
          <button
            className="error-banner-dismiss"
            onClick={() => setError(null)}
            type="button"
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="card-actions">
        <button
          className="secondary-button"
          onClick={() => void handleRefresh()}
          disabled={refreshing}
          type="button"
        >
          {refreshing ? "Refreshing\u2026" : "Refresh Token"}
        </button>
        <button
          className="danger-button"
          onClick={() => void handleDisconnect()}
          disabled={disconnecting}
          type="button"
        >
          {disconnecting ? "Disconnecting\u2026" : "Disconnect"}
        </button>
      </div>
    </article>
  );
}
