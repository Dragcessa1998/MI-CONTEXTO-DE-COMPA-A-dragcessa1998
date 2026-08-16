export const SESSION_TOKEN_KEY = "nexova_access_token";


export function sessionToken(): string {
  return typeof window === "undefined" ? "" : window.localStorage.getItem(SESSION_TOKEN_KEY) ?? "";
}
