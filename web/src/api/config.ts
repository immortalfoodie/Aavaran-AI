/**
 * Aavaran API Configuration
 *
 * In local development:
 *   VITE_API_URL is unset; paths remain relative (e.g., /api/v1/recommend)
 *   and are proxied by Vite dev server to http://127.0.0.1:8000.
 *
 * In production on Vercel:
 *   Set VITE_API_URL to your deployed backend URL:
 *   e.g., https://aavaran-ai-api.onrender.com
 *   Calls will resolve to https://aavaran-ai-api.onrender.com/api/v1/recommend.
 */

export const API_BASE_URL: string = (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '');

export function getApiUrl(path: string): string {
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  if (!API_BASE_URL) {
    return cleanPath;
  }
  return `${API_BASE_URL}${cleanPath}`;
}
