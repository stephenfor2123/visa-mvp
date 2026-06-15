// components/Card.js
Component({
  options: { multipleSlots: true },
  properties: {
    title: { type: String, value: '' },
    hoverable: { type: Boolean, value: false }
  },
  data: {
    hasFooter: true
  },
  ready() {
    // 检测 footer slot 是否有内容(微信基础库 2.12+ 支持 this.selectComponent 但 footer slot 检测靠运行时)
    // 简化处理:hasFooter 默认 true,如果用户没用 footer slot 也不会报错
  }
})
