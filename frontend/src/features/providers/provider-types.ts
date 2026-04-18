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
  configuration?: string;
};

export type ProviderPreset = {
  key: string;
  name: string;
  adapter: string;
  base_url: string | null;
  recommended_models: string[];
  supports_discovery: boolean;
  auth_mode?: "api_key" | "oauth";
};

export type ProviderTypeOption = {
  value: string;
  label: string;
};

// Provider type and model suggestions come from backend presets.
export const providerTypes: ProviderTypeOption[] = [];

// Model suggestions come from backend presets.
export const providerModelCatalog: Record<string, string[]> = {};

export function getProviderTypeOptionsFromPresets(presets: ProviderPreset[]): ProviderTypeOption[] {
  return presets.map((preset) => ({
    value: preset.key,
    label: preset.name
  }));
}

export const emptyProviderInput: ProviderInput = {
  name: "",
  provider_type: "",
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
