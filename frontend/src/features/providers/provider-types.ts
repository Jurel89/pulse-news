export type ProviderSummary = {
  id: number;
  name: string;
  provider_type: string;
  is_enabled: boolean;
  description: string | null;
  default_model: string | null;
  configuration: string | null;
  created_at: string;
  updated_at: string;
};

export type ProviderDetail = ProviderSummary & {
  configuration: string | null;
};

export type ProviderInput = {
  name: string;
  provider_type: string;
  is_enabled: boolean;
  description: string;
  default_model: string;
  configuration: string;
};

export const providerTypes = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "gemini", label: "Gemini" },
  { value: "google", label: "Google" },
  { value: "openrouter", label: "OpenRouter" }
] as const;

export const providerModelCatalog: Record<string, string[]> = {
  openai: ["gpt-4o-mini", "gpt-4o", "o4-mini"],
  anthropic: ["claude-3-5-sonnet-latest", "claude-3-7-sonnet-latest"],
  gemini: ["gemini-2.5-flash", "gemini-2.5-pro"],
  google: ["gemini-2.5-flash", "gemini-2.5-pro"],
  openrouter: [
    "openai/gpt-4o-mini",
    "anthropic/claude-3.5-sonnet",
    "google/gemini-2.0-flash-001"
  ]
};

export const emptyProviderInput: ProviderInput = {
  name: "",
  provider_type: "openai",
  is_enabled: true,
  description: "",
  default_model: "",
  configuration: ""
};

export function toProviderInput(detail: ProviderDetail): ProviderInput {
  return {
    name: detail.name,
    provider_type: detail.provider_type,
    is_enabled: detail.is_enabled,
    description: detail.description ?? "",
    default_model: detail.default_model ?? "",
    configuration: detail.configuration ?? ""
  };
}
