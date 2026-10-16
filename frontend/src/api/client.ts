// frontend/src/api/client.ts
import type { ApiResponse } from '../types';
import { getApiBase } from './serverConfig';

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

function apiUrl(path: string): string {
  return `${getApiBase()}${path}`;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(apiUrl(path));
  const body = (await res.json()) as ApiResponse<T>;
  if (!res.ok) throw new ApiError(res.status, body.message);
  return body.data;
}

export async function apiPost<T>(path: string): Promise<T> {
  const res = await fetch(apiUrl(path), { method: 'POST' });
  const body = (await res.json()) as ApiResponse<T>;
  if (!res.ok) throw new ApiError(res.status, body.message);
  return body.data;
}

export async function apiUpload<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(apiUrl(path), { method: 'POST', body: form });
  const body = (await res.json()) as ApiResponse<T>;
  if (!res.ok) throw new ApiError(res.status, body.message);
  return body.data;
}
