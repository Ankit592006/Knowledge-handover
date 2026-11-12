import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// In-memory token store (avoids insecure plaintext localStorage token persistence)
let inMemoryAccessToken: string | null = null;
let inMemoryRefreshToken: string | null = null;

export function setAuthTokens(accessToken: string | null, refreshToken: string | null = null): void {
  inMemoryAccessToken = accessToken;
  if (refreshToken !== null) {
    inMemoryRefreshToken = refreshToken;
  }
}

export function getAccessToken(): string | null {
  return inMemoryAccessToken;
}

export function getRefreshToken(): string | null {
  return inMemoryRefreshToken;
}

export function clearAuthTokens(): void {
  inMemoryAccessToken = null;
  inMemoryRefreshToken = null;
}

apiClient.interceptors.request.use((config) => {
  if (inMemoryAccessToken && config.headers) {
    config.headers.Authorization = `Bearer ${inMemoryAccessToken}`;
  }
  return config;
});
