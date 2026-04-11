export type ApiKeySummary = {
  id: number;
  name: string;
  provider_type: string;
  masked_key: string;
  is_active: boolean;
  last_used_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ApiKeyDetail = ApiKeySummary;

export type ApiKeyInput = {
  name: string;
  provider_type: string;
  key_value: string | null;
  is_active: boolean;
};

export const providerTypes = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "gemini", label: "Gemini" },
  { value: "google", label: "Google" },
  { value: "openrouter", label: "OpenRouter" },
  { value: "resend", label: "Resend" }
] as const;

export const emptyApiKeyInput: ApiKeyInput = {
  name: "",
  provider_type: "openai",
  key_value: "",
  is_active: true
};

export function toApiKeyInput(detail: ApiKeyDetail): ApiKeyInput {
  return {
    name: detail.name,
    provider_type: detail.provider_type,
    key_value: "",
    is_active: detail.is_active
  };
}
