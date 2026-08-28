import { api } from "./api-client";

export interface AiProviderKey {
  id: string;
  organization_id: string | null;
  provider_name: "gemini" | "openai" | "claude" | "deepseek" | "openrouter" | string;
  label: string;
  masked_api_key: string;
  model_name: string;
  priority: number;
  is_active: boolean;
  last_error_at: string | null;
  error_count: number;
  last_used_at: string | null;
  usage_count: number;
  status: "active" | "rate_limited" | "warning" | "inactive" | string;
  created_at: string;
  updated_at: string;
}

export interface AiProviderKeyCreatePayload {
  provider_name: string;
  label: string;
  api_key: string;
  model_name: string;
  priority: number;
  is_active?: boolean;
}

export interface AiProviderKeyUpdatePayload {
  label?: string;
  api_key?: string;
  model_name?: string;
  priority?: number;
  is_active?: boolean;
}

export interface AiProviderKeyTestResult {
  status: string;
  provider: string;
  model: string;
  latency_ms: number;
  response_sample: string;
}

export async function getAiProviderKeys(): Promise<AiProviderKey[]> {
  const res = await api.get<AiProviderKey[]>("/ai-providers");
  return res || [];
}

export async function createAiProviderKey(
  payload: AiProviderKeyCreatePayload
): Promise<AiProviderKey> {
  return await api.post<AiProviderKey>("/ai-providers", payload);
}

export async function updateAiProviderKey(
  id: string,
  payload: AiProviderKeyUpdatePayload
): Promise<AiProviderKey> {
  return await api.put<AiProviderKey>(`/ai-providers/${id}`, payload);
}

export async function deleteAiProviderKey(id: string): Promise<{ data: { deleted: boolean; id: string } }> {
  return await api.delete<{ data: { deleted: boolean; id: string } }>(`/ai-providers/${id}`);
}

export async function testStoredAiKey(id: string): Promise<AiProviderKeyTestResult> {
  return await api.post<AiProviderKeyTestResult>(`/ai-providers/${id}/test`);
}

export async function testRawAiKey(payload: {
  provider_name: string;
  api_key: string;
  model_name: string;
}): Promise<AiProviderKeyTestResult> {
  return await api.post<AiProviderKeyTestResult>("/ai-providers/test-raw", payload);
}
