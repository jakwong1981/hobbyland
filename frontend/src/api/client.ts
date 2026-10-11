// frontend/src/api/client.ts
import type { ApiResponse } from '../types';

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(path);
  const body = (await res.json()) as ApiResponse<T>;
  if (!res.ok) throw new ApiError(res.status, body.message);
  return body.data;
}

export async function apiUpload<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(path, { method: 'POST', body: form });
  const body = (await res.json()) as ApiResponse<T>;
  if (!res.ok) throw new ApiError(res.status, body.message);
  return body.data;
}
