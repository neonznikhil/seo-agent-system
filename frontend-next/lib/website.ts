const WEBSITE_ID_KEY = "current-website-id";

export function getCurrentWebsiteId(): string {
  if (typeof window === "undefined") return "";
  const id = localStorage.getItem(WEBSITE_ID_KEY) || "";
  if (id === "default-website-id" || id === "null" || id === "undefined") return "";
  return id;
}

export function getWebsiteId(): string {
  return getCurrentWebsiteId();
}

export function setCurrentWebsiteId(websiteId: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(WEBSITE_ID_KEY, websiteId);
  window.dispatchEvent(new CustomEvent("website-changed", { detail: websiteId }));
}
