/**
 * RankForge Client-Side Authentication & Session Manager.
 * Handles JWT tokens, active user profiles, and multi-tenant account switching.
 */

export interface UserProfile {
  id: string;
  email: string;
  full_name?: string;
  role?: "owner" | "admin" | "editor" | "viewer";
  avatar_url?: string;
  preferences?: {
    theme?: string;
    default_tone?: string;
    auto_publish?: boolean;
    target_word_count?: number;
    cadence_morning_brief?: boolean;
    cadence_content_writer?: boolean;
    cadence_tech_seo?: boolean;
    cadence_evening_summary?: boolean;
    [key: string]: any;
  };
}

const AUTH_TOKEN_KEY = "rankforge_auth_token";
const AUTH_USER_KEY = "rankforge_auth_user";

export const DEFAULT_USER: UserProfile = {
  id: "a0000000-0000-0000-0000-000000000001",
  email: "admin@rankforge.ai",
  full_name: "Lead SEO Architect",
  role: "owner",
  avatar_url: "https://api.dicebear.com/7.x/bottts/svg?seed=RankForgeAdmin",
  preferences: {
    theme: "dark",
    default_tone: "authoritative",
    auto_publish: false,
    target_word_count: 1500,
    cadence_morning_brief: true,
    cadence_content_writer: true,
    cadence_tech_seo: true,
    cadence_evening_summary: true,
  },
};

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

export function getCurrentUser(): UserProfile {
  if (typeof window === "undefined") return DEFAULT_USER;
  try {
    const raw = localStorage.getItem(AUTH_USER_KEY);
    if (!raw) return DEFAULT_USER;
    return JSON.parse(raw);
  } catch {
    return DEFAULT_USER;
  }
}

export function setAuthSession(token: string, user: UserProfile): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(AUTH_TOKEN_KEY, token);
  localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
  window.dispatchEvent(new CustomEvent("rankforge-auth-changed", { detail: user }));
}

export function clearAuthSession(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_USER_KEY);
  window.dispatchEvent(new CustomEvent("rankforge-auth-changed", { detail: null }));
}

export function isAuthenticated(): boolean {
  if (typeof window === "undefined") return false;
  return Boolean(getAuthToken() || localStorage.getItem(AUTH_USER_KEY));
}
