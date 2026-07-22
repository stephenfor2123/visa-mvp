/**
 * API mock switch.
 *
 * Production: mock is OPT-IN only (VITE_MOCK=true). Missing/empty → real API.
 * Dev: keep historical default — mock ON unless VITE_MOCK=false.
 *
 * This prevents empty Vercel env from shipping a "login works" mock frontend.
 */
export function isApiMockMode() {
  const flag = String(import.meta.env.VITE_MOCK ?? '').trim().toLowerCase()
  if (import.meta.env.PROD) {
    return flag === 'true' || flag === '1' || flag === 'yes' || flag === 'on'
  }
  return flag !== 'false'
}
