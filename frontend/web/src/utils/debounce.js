/**
 * 轻量防抖工具 — 不依赖 lodash
 *
 * 用法:
 *   const safeFn = debounce(async (...args) => { ... }, waitMs, leading)
 *   // leading=true: 立即执行首次,waitMs 内忽略后续
 *   // leading=false(默认): waitMs 后执行最后一次
 */

/**
 * @param {Function} fn
 * @param {number} wait  ms
 * @param {boolean} [leading]  是否优先执行第一次
 * @returns {Function} 防抖包装
 */
export function debounce(fn, wait, leading = false) {
  let timer = null
  let lastArgs = null

  function invoke(args) {
    return Reflect.apply(fn, null, args)
  }

  function debounced(...args) {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
    lastArgs = args

    if (leading && !timer) {
      // 立即执行
      invoke(args)
    }

    timer = setTimeout(() => {
      timer = null
      if (!leading && lastArgs !== null) {
        invoke(lastArgs)
        lastArgs = null
      }
    }, wait)
  }

  debounced.cancel = () => {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
    lastArgs = null
  }

  return debounced
}

/**
 * 带防重提交状态的包装
 * 返回 { fn, isPending } — isPending 可在模板中用于禁用按钮
 *
 * @param {Function} asyncFn
 * @param {number} [wait]  ms, 默认 2000
 * @returns {{ fn: Function, isPending: Ref<boolean> }}
 */
import { ref } from 'vue'

export function useDebounceFn(asyncFn, wait = 2000) {
  const isPending = ref(false)
  const safeFn = debounce(async (...args) => {
    isPending.value = true
    try {
      return await asyncFn(...args)
    } finally {
      isPending.value = false
    }
  }, wait, false)

  return { fn: safeFn, isPending }
}
