import { chromium } from 'playwright'
const browser = await chromium.launch()
async function snap(url, out, label, country) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 1600 }, locale: 'zh-CN' })
  const page = await ctx.newPage()
  await page.goto(url)
  await page.waitForTimeout(1500)
  // 用 Vue 3 app instance hack: __VUE_APP__ 是 Vue 暴露的
  await page.evaluate(() => {
    // 找 vue app 的根节点 - 拿 wizard exposed state
    const root = document.getElementById('app')
    if (!root) return
    // 拿 Vue instance (Vue 3 不暴露在 __vue__ 上, 在 __vue_app__ 上)
    const app = root.__vue_app__
    if (!app) return
    // 找 MaterialWizard 组件 instance
    const seen = new WeakSet()
    function walk(node) {
      if (!node || seen.has(node)) return null
      seen.add(node)
      // node 可能是 app 本身, 也可能是 component
      if (node.setupState && node.setupState.state && node.setupState.state.categories) {
        // 把所有 category 标 validated → 这样 goToCategory 不会卡
        const cats = node.setupState.state.categories
        for (const k of Object.keys(cats)) {
          cats[k] = cats[k] || {}
          cats[k].validated = true
        }
        // 同时改 activeCategory
        node.setupState.state.activeCategory = 'financial'
        return node
      }
      // 递归子树
      const children = node.subTree ? [node.subTree] : []
      for (const c of children) {
        const r = walk(c)
        if (r) return r
      }
      return null
    }
    walk(app._instance)
  })
  await page.waitForTimeout(800)
  const allMtp = await page.locator('.mtp').all()
  console.log(`[${label}] ${allMtp.length} mtp blocks`)
  let target = null
  for (const b of allMtp) {
    const t = await b.textContent()
    if (t && (t.includes('银行存款') || t.includes('Bank Statement') || t.includes('Sao kê') || t.includes('ngân hàng') || t.includes('銀行'))) {
      target = b
      break
    }
  }
  if (target) {
    await target.scrollIntoViewIfNeeded()
    await page.waitForTimeout(300)
    await target.screenshot({ path: out })
    console.log(`saved ${out} (${label})`)
  } else {
    await page.screenshot({ path: out, fullPage: true })
    console.log(`fallback full page ${out}`)
  }
  await ctx.close()
}
await snap('http://127.0.0.1:5173/materials-wizard?country=US&visa_type=tourism', '/tmp/tpl-US.png', 'US', 'US')
await snap('http://127.0.0.1:5173/materials-wizard?country=VN&visa_type=tourism', '/tmp/tpl-VN.png', 'VN', 'VN')
await browser.close()
