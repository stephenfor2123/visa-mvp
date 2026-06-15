import { ref } from 'vue'

const toasts = ref([])
let id = 0

function push(type, message, opts = {}) {
  const item = {
    id: ++id,
    type,
    message,
    duration: opts.duration ?? 3000
  }
  toasts.value.push(item)
  if (item.duration > 0) {
    setTimeout(() => remove(item.id), item.duration)
  }
  return item.id
}

function remove(tid) {
  const idx = toasts.value.findIndex(t => t.id === tid)
  if (idx !== -1) toasts.value.splice(idx, 1)
}

export function useToast() {
  return {
    toasts,
    success: (msg, opts) => push('success', msg, opts),
    error: (msg, opts) => push('error', msg, opts),
    warning: (msg, opts) => push('warning', msg, opts),
    info: (msg, opts) => push('info', msg, opts),
    remove
  }
}