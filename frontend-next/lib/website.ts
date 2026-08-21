const WEBSITE_ID_KEY = "current-website-id";

export function getCurrentWebsiteId(): string {
  if (typeof window === "undefined") return "default-website-id";
  return localStorage.getItem(WEBSITE_ID_KEY) || "default-website-id";
}

export function setCurrentWebsiteId(websiteId: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(WEBSITE_ID_KEY, websiteId);
}
