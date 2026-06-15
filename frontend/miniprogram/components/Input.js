// components/Input.js
Component({
  options: { multipleSlots: true },
  properties: {
    label: { type: String, value: '' },
    placeholder: { type: String, value: '' },
    value: { type: String, value: '' },
    inputType: { type: String, value: 'text' },   // text | number | digit | idcard | safe-password
    password: { type: Boolean, value: false },
    maxlength: { type: Number, value: 140 },
    disabled: { type: Boolean, value: false },
    error: { type: String, value: '' },
    hint: { type: String, value: '' }
  },
  methods: {
    onInput(e) {
      this.setData({ value: e.detail.value })
      this.triggerEvent('input', { value: e.detail.value }, {})
    },
    onFocus(e) { this.triggerEvent('focus', e.detail, {}) },
    onBlur(e) { this.triggerEvent('blur', e.detail, {}) }
  }
})
