// Where the GovMind API lives. When the dashboard is served by the backend itself
// (the Modal deployment), that's simply this page's origin.
export function backendUrl(): string {
  if (process.env.NEXT_PUBLIC_BACKEND_URL) return process.env.NEXT_PUBLIC_BACKEND_URL;
  if (typeof window === "undefined") return "http://localhost:8000";
  return window.location.port === "3000" ? "http://localhost:8000" : window.location.origin;
}
