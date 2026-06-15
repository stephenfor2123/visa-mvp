/**
 * ErrorBoundary.tsx — Vue 3 Error Boundary Component
 *
 * Catches child component errors and displays an elegant fallback UI
 * instead of a blank white screen / crash.  Works as a drop-in wrapper.
 *
 * Uses React-style class-based lifecycle (errorCaptured) since Vue 3
 * function-components don't support the ErrorBoundary contract natively.
 */
import { defineComponent, h, ref } from 'vue'

interface Props {
  /** Custom fallback UI text */
  message?: string
  /** Called when an error is caught — useful for logging */
  onError?: (err: Error, info: string) => void
}

export const ErrorBoundary = defineComponent({
  name: 'ErrorBoundary',
  props: {
    message: { type: String, default: 'Something went wrong. Please refresh the page.' },
    onError: { type: Function, default: null }
  },

  setup(props: Props, { slots }) {
    /** true after any child error is caught */
    const hasError = ref(false)
    /** the caught Error instance */
    const caughtError = ref<Error | null>(null)

    return () => {
      if (hasError.value) {
        return h('div', {
          role: 'alert',
          'aria-live': 'assertive',
          style: `
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 60vh;
            padding: 40px 24px;
            font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif;
            background: #F8FAFC;
            color: #0F172A;
            text-align: center;
            gap: 16px;
          `
        }, [
          h('div', {
            style: `
              width: 64px; height: 64px;
              border-radius: 50%;
              background: #FEE2E2;
              display: inline-flex; align-items: center; justify-content: center;
              font-size: 32px;
              margin-bottom: 4px;
            `
          }, '⚠️'),
          h('h2', {
            style: 'margin: 0; font-size: 20px; font-weight: 700; color: #991B1B;'
          }, 'Oops! Something went wrong'),
          h('p', {
            style: 'margin: 0; font-size: 14px; color: #64748B; max-width: 400px;'
          }, props.message),
          caughtError.value && import.meta.env.DEV
            ? h('pre', {
                style: `
                  margin: 8px 0 0;
                  padding: 12px 16px;
                  background: #1E293B;
                  color: #E2E8F0;
                  border-radius: 8px;
                  font-size: 12px;
                  text-align: left;
                  max-width: 600px;
                  overflow: auto;
                  white-space: pre-wrap;
                  word-break: break-all;
                `
              }, String(caughtError.value?.stack || caughtError.value?.message || 'Unknown error'))
            : null,
          h('button', {
            onClick: () => {
              hasError.value = false
              caughtError.value = null
              window.location.reload()
            },
            style: `
              margin-top: 8px;
              padding: 9px 20px;
              background: #3B6EF5;
              color: #fff;
              border: none;
              border-radius: 8px;
              font-size: 14px;
              font-weight: 500;
              cursor: pointer;
            `
          }, 'Refresh Page')
        ])
      }

      return slots.default?.()
    }
  },

  errorCaptured(err: Error, instance: any, info: string) {
    hasError.value = true
    caughtError.value = err instanceof Error ? err : new Error(String(err))
    if (typeof props.onError === 'function') {
      props.onError(caughtError.value, info)
    }
    // Return false to prevent the error from propagating further
    return false
  }
})

export default ErrorBoundary