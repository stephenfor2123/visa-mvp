/**
 * src/__tests__/api/auth.test.ts
 *
 * Unit tests for `loginWithGoogle` in @/api/auth.
 *
 * Coverage:
 *  - mock mode: returns fake token without network
 *  - real mode: posts { id_token } to /v2/auth/google, maps envelope
 *  - real mode: throws on non-1000 envelope code
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// We toggle VITE_MOCK via vi.stubEnv so the module picks up the right code path.
const flushEnvs = () => {
  vi.resetModules()
}

describe('api/auth.loginWithGoogle', () => {
  let mockPost: any
  let httpModule: any

  beforeEach(async () => {
    mockPost = vi.fn()
    vi.doMock('@/api/http', () => ({
      default: { post: (...args: any[]) => mockPost(...args) }
    }))
  })

  afterEach(() => {
    vi.doUnmock('@/api/http')
    vi.unstubAllEnvs()
  })

  it('mock mode: returns fake token without hitting network', async () => {
    vi.stubEnv('VITE_MOCK', 'true')
    flushEnvs()
    const { loginWithGoogle } = await import('@/api/auth')

    const data = await loginWithGoogle('any.credential.token')
    expect(data.accessToken).toMatch(/^mock\.access\./)
    expect(data.refreshToken).toMatch(/^mock\.refresh\./)
    expect(data.user.email).toBe('google_user@gmail.com')
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('real mode: posts { id_token } to /v2/auth/google', async () => {
    vi.stubEnv('VITE_MOCK', 'false')
    flushEnvs()
    const { loginWithGoogle } = await import('@/api/auth')

    mockPost.mockResolvedValue({
      code: '1000',
      message: 'OK',
      data: {
        access_token: 'real.access.jwt',
        refresh_token: 'real.refresh.jwt',
        token_type: 'Bearer',
        expires_in: 7200,
        user: { id: 7, email: 'real@gmail.com', username: 'g_abc12345' }
      }
    })

    const data = await loginWithGoogle('real.credential')
    expect(mockPost).toHaveBeenCalledWith('/v2/auth/google', { id_token: 'real.credential' })
    expect(data.accessToken).toBe('real.access.jwt')
    expect(data.refreshToken).toBe('real.refresh.jwt')
    expect(data.user.email).toBe('real@gmail.com')
    expect(data.expiresIn).toBe(7200)
  })

  it('real mode: throws on non-1000 envelope', async () => {
    vi.stubEnv('VITE_MOCK', 'false')
    flushEnvs()
    const { loginWithGoogle } = await import('@/api/auth')

    mockPost.mockResolvedValue({
      code: '2001',
      message: 'Invalid Google token',
      data: null
    })

    await expect(loginWithGoogle('bad.token')).rejects.toThrow('Invalid Google token')
  })

  it('real mode: throws default message when envelope has no message', async () => {
    vi.stubEnv('VITE_MOCK', 'false')
    flushEnvs()
    const { loginWithGoogle } = await import('@/api/auth')

    mockPost.mockResolvedValue({ code: '9999', data: null })

    await expect(loginWithGoogle('x')).rejects.toThrow('Google login failed')
  })
})