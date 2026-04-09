import type { SessionResponse } from "./api";

export type SessionState = SessionResponse & {
  loading: boolean;
};

export const initialSessionState: SessionState = {
  initialized: false,
  authenticated: false,
  user: null,
  loading: true
};

export function asLoadedSession(session: SessionResponse): SessionState {
  return {
    ...session,
    loading: false
  };
}
