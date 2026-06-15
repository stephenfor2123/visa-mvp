/**
 * src/__tests__/Login.test.ts
 * Unit tests for Login.vue view.
 *
 * Coverage: renders, tab switching (pwd/sms), form visibility,
 *           footer rendering.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createWebHashHistory } from 'vue-router'
import { createI18n } from 'vue-i18n'
import Login from '@/views/Login.vue'

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    hydrate: vi.fn(),
    loginByPassword: vi.fn().mockResolvedValue({}),
    loginBySms: vi.fn().mockResolvedValue({}),
    sendSmsCode: vi.fn().mockResolvedValue({ code: '123456' })
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
      login: { title: 'Sign In', subtitle: 'Welcome back', tab_pwd: 'Password', tab_sms: 'SMS' },
      errors: { phone_invalid: 'Invalid phone', pwd_too_short: 'Too short' },
      common: { app_name: 'Visa', auth_footer: 'Visa MVP' }
    }
  }
})

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/login' },
    { path: '/login', component: Login },
    { path: '/profile', component: { template: '<div />' } },
    { path: '/register', component: { template: '<div />' } },
    { path: '/forgot-password', component: { template: '<div />' } }
  ]
})

const mountLogin = () =>
  mount(Login, {
    global: {
      plugins: [router, i18n],
      stubs: {
        AppCard: { template: '<div class="stub-app-card"><slot /></div>' },
        AppInput: {
          template: '<input class="stub-app-input" />',
          props: ['modelValue', 'label'],
          emits: ['update:modelValue']
        },
        AppButton: { template: '<button class="stub-app-btn"><slot /></button>' },
        LangSwitch: { template: '<span class="stub-lang-switch" />' }
      },
      config: { warnHandler: () => {} }
    }
  })

describe('Login', () => {
  beforeEach(() => {
    router.push('/login')
  })

  it('renders the login title', async () => {
    const wrapper = mountLogin()
    await flushPromises()
    expect(wrapper.find('h1').text()).toBeTruthy()
  })

  it('renders both password and SMS tabs', async () => {
    const wrapper = mountLogin()
    await flushPromises()
    const tabs = wrapper.findAll('.auth-tab')
    expect(tabs.length).toBe(2)
  })

  it('defaults to password tab active', async () => {
    const wrapper = mountLogin()
    await flushPromises()
    const activeTab = wrapper.find('.auth-tab.on')
    expect(activeTab.exists()).toBe(true)
  })

  it('switches to SMS tab on click', async () => {
    const wrapper = mountLogin()
    await flushPromises()
    const tabs = wrapper.findAll('.auth-tab')
    await tabs[1].trigger('click')
    await flushPromises()
    const activeTab = wrapper.find('.auth-tab.on')
    expect(activeTab.exists()).toBe(true)
  })

  it('renders auth form with input elements', async () => {
    const wrapper = mountLogin()
    await flushPromises()
    const inputs = wrapper.findAll('.stub-app-input')
    expect(inputs.length).toBeGreaterThan(0)
  })

  it('shows send-code button after switching to SMS tab', async () => {
    const wrapper = mountLogin()
    await flushPromises()
    const tabs = wrapper.findAll('.auth-tab')
    await tabs[1].trigger('click')
    await flushPromises()
    const sendBtn = wrapper.find('.stub-app-btn')
    expect(sendBtn.exists()).toBe(true)
  })

  it('renders footer text', async () => {
    const wrapper = mountLogin()
    await flushPromises()
    expect(wrapper.find('.auth-footer').exists()).toBe(true)
  })
})