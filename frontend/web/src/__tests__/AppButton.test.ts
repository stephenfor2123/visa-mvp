/**
 * src/__tests__/AppButton.test.ts
 * Unit tests for AppButton.vue component.
 *
 * Coverage: render, variants, sizes, loading state, disabled state,
 *           click handler, setOnTrigger / trigger() manual trigger.
 *
 * Note: tested directly without ErrorBoundary wrapper — ErrorBoundary
 *       uses slots.default?.() which wraps multi-root content in a <div>,
 *       causing wrapper.element.tagName to return 'DIV'.  Test the component
 *       directly for accurate assertions.
 */
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import AppButton from '@/components/AppButton.vue'

const mountBtn = (props = {}) => mount(AppButton, { props } as any)

describe('AppButton', () => {
  it('renders slot content', () => {
    const wrapper = mountBtn()
    expect(wrapper.html()).toContain('Sign In')
  })

  it('renders as a button element', () => {
    const wrapper = mountBtn()
    expect(wrapper.element.tagName).toBe('BUTTON')
  })

  it('has the base app-btn class', () => {
    const wrapper = mountBtn()
    expect(wrapper.html()).toContain('app-btn')
  })

  it('adds app-btn--primary by default', () => {
    const wrapper = mountBtn()
    expect(wrapper.html()).toContain('app-btn--primary')
  })

  it('adds app-btn--outline variant class', () => {
    const wrapper = mountBtn({ variant: 'outline' })
    expect(wrapper.html()).toContain('app-btn--outline')
  })

  it('adds app-btn--ghost variant class', () => {
    const wrapper = mountBtn({ variant: 'ghost' })
    expect(wrapper.html()).toContain('app-btn--ghost')
  })

  it('adds app-btn--danger variant class', () => {
    const wrapper = mountBtn({ variant: 'danger' })
    expect(wrapper.html()).toContain('app-btn--danger')
  })

  it('adds app-btn--sm size class', () => {
    const wrapper = mountBtn({ size: 'sm' })
    expect(wrapper.html()).toContain('app-btn--sm')
  })

  it('adds app-btn--lg size class', () => {
    const wrapper = mountBtn({ size: 'lg' })
    expect(wrapper.html()).toContain('app-btn--lg')
  })

  it('is disabled when disabled prop is true', () => {
    const wrapper = mountBtn({ disabled: true })
    expect(wrapper.element.hasAttribute('disabled')).toBe(true)
  })

  it('is disabled when loading prop is true', () => {
    const wrapper = mountBtn({ loading: true })
    expect(wrapper.element.hasAttribute('disabled')).toBe(true)
  })

  it('adds is-loading class when loading', () => {
    const wrapper = mountBtn({ loading: true })
    expect(wrapper.html()).toContain('is-loading')
  })

  it('emits click event on button click', async () => {
    const wrapper = mountBtn()
    await wrapper.trigger('click')
    expect(wrapper.emitted('click')).toBeTruthy()
  })

  it('does not emit click when disabled', async () => {
    const wrapper = mountBtn({ disabled: true })
    await wrapper.trigger('click')
    expect(wrapper.emitted('click')).toBeFalsy()
  })

  it('does not emit click when loading', async () => {
    const wrapper = mountBtn({ loading: true })
    await wrapper.trigger('click')
    expect(wrapper.emitted('click')).toBeFalsy()
  })

  it('calls setOnTrigger injected callback on click', async () => {
    const wrapper = mountBtn()
    const handler = vi.fn()
    ;(wrapper.vm as any).setOnTrigger(handler)
    await wrapper.trigger('click')
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('trigger() manually fires callback without DOM click', async () => {
    const wrapper = mountBtn()
    const handler = vi.fn()
    ;(wrapper.vm as any).setOnTrigger(handler)
    ;(wrapper.vm as any).trigger()
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('uses nativeType prop for button type attribute', () => {
    const wrapper = mountBtn({ nativeType: 'submit' })
    expect(wrapper.attributes('type')).toBe('submit')
  })

  it('defaults type to button', () => {
    const wrapper = mountBtn()
    expect(wrapper.attributes('type')).toBe('button')
  })
})