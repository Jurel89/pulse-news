import { useEffect, useRef, useState } from "react";
import { api } from "../../lib/api";
import type { DeviceStartResponse } from "../../lib/api";

type Props = {
  onConnected: (apiKeyId: number) => void;
  onCancel: () => void;
};

type Phase = "starting" | "awaiting_user" | "polling" | "error";

export function ConnectChatGPTModal({ onConnected, onCancel }: Props) {
  const [phase, setPhase] = useState<Phase>("starting");
  const [init, setInit] = useState<DeviceStartResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeRef = useRef(true);
  const deadlineRef = useRef<number | null>(null);

  useEffect(() => {
    activeRef.current = true;
    void startFlow();
    return () => {
      activeRef.current = false;
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function startFlow() {
    setPhase("starting");
    try {
      const data = await api.oauthOpenai.deviceStart();
      if (!activeRef.current) return;
      setInit(data);
      deadlineRef.current = Date.now() + data.expires_in * 1000;
      setPhase("awaiting_user");
      schedulePoll(data, data.interval * 1000);
    } catch (err: unknown) {
      if (!activeRef.current) return;
      setErrorMsg(err instanceof Error ? err.message : "Failed to start device flow.");
      setPhase("error");
    }
  }

  function schedulePoll(data: DeviceStartResponse, delayMs: number) {
    pollTimerRef.current = setTimeout(() => {
      void doPoll(data);
    }, delayMs);
  }

  async function doPoll(data: DeviceStartResponse) {
    if (!activeRef.current) return;
    if (deadlineRef.current !== null && Date.now() > deadlineRef.current) {
      setErrorMsg("Device code expired. Click Try Again to request a new one.");
      setPhase("error");
      return;
    }
    setPhase("polling");
    try {
      const result = await api.oauthOpenai.devicePoll(data.device_auth_id);
      if (!activeRef.current) return;
      if (result.status === "complete" && result.api_key_id != null) {
        onConnected(result.api_key_id);
        return;
      }
      // Still pending — schedule next poll.
      setPhase("awaiting_user");
      schedulePoll(data, data.interval * 1000);
    } catch (err: unknown) {
      if (!activeRef.current) return;
      setErrorMsg(err instanceof Error ? err.message : "Polling failed.");
      setPhase("error");
    }
  }

  function handleCancel() {
    activeRef.current = false;
    if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    onCancel();
  }

  return (
    <div className="modal-overlay">
      <div className="modal-panel" style={{ maxWidth: 480 }}>
        <header className="section-header" style={{ marginBottom: 16 }}>
          <div>
            <p className="eyebrow">ChatGPT OAuth</p>
            <h2 className="section-title">Connect ChatGPT Subscription</h2>
          </div>
        </header>

        {phase === "starting" && (
          <p>Starting device-code flow&hellip;</p>
        )}

        {(phase === "awaiting_user" || phase === "polling") && init && (
          <div>
            <p style={{ marginBottom: 12 }}>
              Open the link below and enter the code to authorise Pulse News to
              use your ChatGPT subscription.
            </p>

            <div style={{ textAlign: "center", margin: "20px 0" }}>
              <a
                href={init.verification_uri}
                target="_blank"
                rel="noopener noreferrer"
                className="primary-button"
                style={{ display: "inline-block", marginBottom: 16 }}
              >
                Open {init.verification_uri}
              </a>
              <p style={{ fontSize: 13, color: "#5c6b78", marginBottom: 8 }}>
                Enter this code:
              </p>
              <code
                style={{
                  fontSize: 28,
                  fontWeight: 700,
                  letterSpacing: "0.15em",
                  display: "block",
                  padding: "12px 0"
                }}
              >
                {init.user_code}
              </code>
            </div>

            <p style={{ fontSize: 13, color: "#5c6b78" }}>
              {phase === "polling"
                ? "Checking for authorisation\u2026"
                : "Waiting for you to authorise\u2026"}
            </p>
          </div>
        )}

        {phase === "error" && (
          <div className="error-banner" style={{ marginBottom: 16 }}>
            <span>{errorMsg}</span>
          </div>
        )}

        <div style={{ display: "flex", gap: 8, marginTop: 20 }}>
          {phase === "error" && (
            <button className="primary-button" onClick={() => void startFlow()} type="button">
              Try Again
            </button>
          )}
          <button className="secondary-button" onClick={handleCancel} type="button">
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
