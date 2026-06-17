/**
 * Thin HTTP client composable.
 * All API calls go through here so we can swap base URL, add auth headers,
 * or inject a mock transport in tests.
 */

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api/v1'

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly path: string,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('access_token')
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
    ...init,
  })

  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText)
    throw new ApiError(res.status, path, `${init.method ?? 'GET'} ${path} → ${res.status}: ${detail}`)
  }

  // 204 No Content
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export function useApi() {
  return {
    get:    <T>(path: string)                   => request<T>(path),
    post:   <T>(path: string, body: unknown)    => request<T>(path, { method: 'POST',   body: JSON.stringify(body) }),
    patch:  <T>(path: string, body: unknown)    => request<T>(path, { method: 'PATCH',  body: JSON.stringify(body) }),
    put:    <T>(path: string, body: unknown)    => request<T>(path, { method: 'PUT',    body: JSON.stringify(body) }),
    delete: (path: string)                      => request<void>(path, { method: 'DELETE' }),
  }
}
