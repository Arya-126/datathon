/*
 * Runtime config for the KSP Crime AI client.
 *
 * Local dev / AppSail-served: leave apiBase empty (same-origin).
 * Catalyst Web Client Hosting: after `catalyst deploy --only appsail`,
 * copy the AppSail URL from the console and set it here, then
 * `catalyst deploy --only client` again. Backend sends CORS *, so a
 * cross-origin base works.
 *
 * Example:
 *   apiBase: "https://ksp-ai-backend-123456789.development.catalystappsail.com"
 */
window.KSP_CONFIG = {
  apiBase: "",
};
