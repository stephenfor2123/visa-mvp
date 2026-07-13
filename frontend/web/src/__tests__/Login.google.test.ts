/**
 * src/__tests__/Login.google.test.ts
 *
 * Unit tests for Login.vue's Google sign-in branch:
 *  - placeholder/divider rendered only when VITE_GOOGLE_CLIENT_ID is set
 *  - placeholder hidden when env var is empty
 *
 * GIS itself is mocked (window.google.accounts.id) so we don't depend on
 * the real Google Identity Services script loading.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createWebHashHistory } from 'vue-router'
import { createI18n } from 'vue-i18n'

// Mock the auth store so we don't pull in pinia + real network.
const loginWithGoogleMock = vi.fn().mockResolvedValue({ user: { id: 1 }, accessToken: 'mock', refreshToken: 'mock' })
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    hydrate: vi.fn(),
    loginByPassword: vi.fn(),
    loginWithGoogle: loginWithGoogleMock
  })
}))

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() })
}))

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: {
    en: {
      login: {
        title: 'Sign In',
        subtitle: 'Welcome back',
        account_label: 'Email or username',
        account_placeholder: 'you [at] example.com',
        pwd_label: 'Password',
        pwd_placeholder: '••••••••',
        remember: 'Remember me',
        forgot: 'Forgot password?',
        submit: 'Sign in',
        no_account: "Don't have an account?",
        go_signup: 'Sign up'
      },
      common: { or: 'or', auth_footer: 'footer' },
      validation: { pwd_too_short: 'too short' },
      errors: { invalid_email: 'bad email', invalid_account: 'bad account' },
      toast: { login_success: 'logged in', login_fail: 'login failed' }
    }
  }
})

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/login' },
    { path: '/login', component: { template: '<div />' } },
    { path: '/destinations', component: { template: '<div />' } },
    { path: '/profile', component: { template: '<div />' } },
    { path: '/register', component: { template: '<div />' } },
    { path: '/forgot-password', component: { template: '<div />' } }
  ]
})

const mountLogin = async () => {
  // Lazy import after env stub so the module picks up VITE_GOOGLE_CLIENT_ID.
  const { default: Login } = await import('@/views/Login.vue')
  return mount(Login, {
    global: {
      plugins: [router, i18n],
      stubs: {
        AppCard: { template: '<div class="stub-app-card"><slot /></div>' },
        AppInput: {
          template: '<input class="stub-app-input" />',
          props: ['modelValue', 'label', 'error'],
          emits: ['update:modelValue', 'blur']
        },
        AppButton: { template: '<button class="stub-app-btn"><slot /></button>' },
        AppHeader: { template: '<header class="stub-app-header" />' }
      }
    }
  })
}

describe('Login.vue — Google sign-in button visibility', () => {
  beforeEach(() => {
    loginWithGoogleMock.mockClear()
    // Reset cached module from previous test
    vi.resetModules()
  })

  afterEach(() => {
    vi.unstubAllEnvs()
    delete (window as any).google
  })

  it('hides Google button when VITE_GOOGLE_CLIENT_ID is unset', async () => {
    vi.stubEnv('VITE_GOOGLE_CLIENT_ID', '')
    const wrapper = await mountLogin()
    await flushPromises()
    expect(wrapper.find('.google-btn-wrap').exists()).toBe(false)
    expect(wrapper.find('.auth-divider').exists()).toBe(false)
  })

  it('renders placeholder Google button when VITE_GOOGLE_CLIENT_ID is set', async () => {
    vi.stubEnv('VITE_GOOGLE_CLIENT_ID', 'fake-client-id-for-test.apps.googleusercontent.com')

    // Mock GIS script — renderButton just no-ops, but the div gets a child.
    let capturedCallback: any = null
    let renderButtonCalled = false
    let renderButtonOpts: any = null
    ;(window as any).google = {
      accounts: {
        id: {
          initialize: (cfg: any) => { capturedCallback = cfg.callback },
          renderButton: (_el: any, opts: any) => {
            renderButtonCalled = true
            renderButtonOpts = opts
          }
        }
      }
    }

    const wrapper = await mountLogin()
    await flushPromises()

    // Placeholder div is rendered (GIS script was already loaded)
    expect(wrapper.find('.google-btn-wrap').exists()).toBe(true)
    expect(wrapper.find('.auth-divider').exists()).toBe(true)
    expect(renderButtonCalled).toBe(true)
    expect(renderButtonOpts?.locale).toBe('en')

    // callback wired — exercise it to make sure it calls loginWithGoogle
    expect(capturedCallback).toBeTruthy()
    await capturedCallback({ credential: 'fake.jwt.from.google' })
    await flushPromises()
    expect(loginWithGoogleMock).toHaveBeenCalledWith('fake.jwt.from.google')
  })
})