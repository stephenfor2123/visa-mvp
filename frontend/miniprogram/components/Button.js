// components/Button.js
Component({
  options: { multipleSlots: true },
  properties: {
    text: { type: String, value: '' },
    variant: { type: String, value: 'primary' },  // primary | outline | ghost
    size: { type: String, value: 'md' },          // sm | md | lg
    block: { type: Boolean, value: false },       // 是否铺满 (lg 自带 block)
    disabled: { type: Boolean, value: false },
    loading: { type: Boolean, value: false },
    loadingText: { type: String, value: '...' }
  },
  methods: {
    onTap(e) {
      if (this.data.disabled || this.data.loading) return
      this.triggerEvent('trigger', {}, {})
    }
  }
})
