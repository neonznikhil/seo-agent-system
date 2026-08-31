const PRIMARY_KEY = "current-website-id";
const ALIAS_KEY = "active_website_id";

export function getCurrentWebsiteId(): string {
  if (typeof window === "undefined") return "";
  const id = localStorage.getItem(PRIMARY_KEY) || localStorage.getItem(ALIAS_KEY) || "";
  if (id === "default-website-id" || id === "null" || id === "undefined" || id === "default") return "";
  return id;
}

export function getWebsiteId(): string {
  return getCurrentWebsiteId();
}

export function setCurrentWebsiteId(websiteId: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(PRIMARY_KEY, websiteId);
  localStorage.setItem(ALIAS_KEY, websiteId);
  window.dispatchEvent(new CustomEvent("website-changed", { detail: websiteId }));
}
