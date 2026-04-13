import type { SessionResponse } from "./api";

export type SessionState = SessionResponse & {
  loading: boolean;
};

export const initialSessionState: SessionState = {
  initialized: false,
  authenticated: false,
  user: null,
  ai_generation_mode: "live",
  email_delivery_mode: "live",
  loading: true
};

export function asLoadedSession(session: SessionResponse): SessionState {
  return {
    ...session,
    loading: false
  };
}
