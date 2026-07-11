// test/unit/run-fill-engine-test.mjs
// =============================================================================
// fillEngine.js 单测(jsdom + 真实模拟表单)。覆盖:
//   - text/select/radio/checkbox/textarea
//   - select 精确优先(MALE ≠ FEMALE 子串误配)
//   - date 三连下拉拆填
//   - autoFill postback 跟填
//   - Does Not Apply 复选框
//   - not_found 不乱填别的框
// =============================================================================
import { JSDOM } from 'jsdom'
import { readFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const EXT_ROOT = resolve(__dirname, '..', '..')

const mappingSrc = readFileSync(resolve(EXT_ROOT, 'src/mapping.js'), 'utf8')
const fillEngineSrc = readFileSync(resolve(EXT_ROOT, 'src/fillEngine.js'), 'utf8')

function loadInJsdom(html) {
  const dom = new JSDOM(html, { runScripts: 'outside-only', pretendToBeVisual: true })
  const win = dom.window
  win.eval(mappingSrc)
  win.eval(fillEngineSrc)
  return { dom, win, doc: dom.window.document }
}

// ────────────────────────────────────────────────────────
// 工具:构建一个仿真 DS-160 表单
// ────────────────────────────────────────────────────────
function buildPersonal1Html() {
  return `<!doctype html><html><body>
    <table>
      <tr><td><label for="s1">Surnames</label></td><td><input id="s1" type="text"></td></tr>
      <tr><td><label for="g1">Given Names</label></td><td><input id="g1" type="text"></td></tr>
      <tr><td><label for="nat1">Full Name in Native Alphabet</label></td>
          <td><input id="nat1" type="text"> <input id="nat1na" type="checkbox"><label for="nat1na">Does Not Apply</label></td></tr>
      <tr><td><label for="sx1">Sex</label></td><td>
        <select id="sx1"><option value=""></option><option>MALE</option><option>FEMALE</option></select></td></tr>
      <tr><td><label for="ms1">Marital Status</label></td><td>
        <select id="ms1"><option value=""></option><option>SINGLE</option><option>MARRIED</option><option>SEPARATED</option></select></td></tr>
      <tr><td><label>Date of Birth</label></td><td>
        <input id="d1" type="text" size="4">  <!-- day 文本 -->
        <select id="d2"><option></option>${['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'].map(m=>`<option value="${['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'].indexOf(m)+1}">${m}</option>`).join('')}</select>
        <input id="d3" type="text" size="6"></td></tr>
      <tr><td><label for="bc1">City of Birth</label></td><td><input id="bc1" type="text"></td></tr>
      <tr><td><label for="bco1">Country/Region of Birth</label></td><td>
        <select id="bco1"><option value=""></option><option>VIETNAM</option><option>INDONESIA</option><option>CHINA</option></select></td></tr>
    </table>
  </body></html>`
}

function buildPersonal2Html() {
  return `<!doctype html><html><body>
    <table>
      <tr><td><label for="nat2">Country/Region of Origin (Nationality)</label></td><td>
        <select id="nat2"><option value=""></option><option>VIETNAM</option><option>INDONESIA</option><option>CHINA</option></select></td></tr>
      <tr><td><label>Do you hold or have you held any nationality other than the one indicated above?</label></td><td>
        <input type="radio" name="han" id="han_y" value="Y"><label for="han_y">YES</label>
        <input type="radio" name="han" id="han_n" value="N"><label for="han_n">NO</label></td></tr>
      <tr><td><label for="nid">National Identification Number</label></td>
          <td><input id="nid" type="text"> <input id="nidna" type="checkbox"><label for="nidna">Does Not Apply</label></td></tr>
    </table>
  </body></html>`
}

let pass = 0, fail = 0
function ok(name, cond) { if (cond) { pass++; console.log('  ✓ ' + name) } else { fail++; console.error('  ✗ ' + name) } }

// ─── Case 1: Personal 1 全填 ───
console.log('Case 1: Personal 1 全字段填')
{
  const { win } = loadInJsdom(buildPersonal1Html())
  const profile = {
    identity: {
      surname: 'nguyen', givenName: 'van an', sex: 'M', maritalStatus: 'separated',
      dob: '1992-05-14', birthCity: 'Ho Chi Minh', birthCountry: 'VIETNAM',
      nativeName: '',
    },
  }
  const g = win.HTEX.buildGuide(profile)
  // 只取 personal1 section
  const sec = g.sections.find(s => s.section === 'personal1')
  // 单独 fill 这一节
  const r = win.HTEX.fill(g, 'personal1')
  ok('filled 计数', r.summary.filled === 7) // 8 个里 nativeName 是 optional 空 → na, 剩 7
  ok('na 计数', r.summary.na === 1)
  ok('Surnames 大写', win.document.getElementById('s1').value === 'NGUYEN')
  ok('Given Names 大写', win.document.getElementById('g1').value === 'VAN AN')
  ok('Sex = MALE', win.document.getElementById('sx1').value === 'MALE')
  ok('Marital Status = SEPARATED', win.document.getElementById('ms1').value === 'SEPARATED')
  ok('DOB day = 14', win.document.getElementById('d1').value === '14')
  ok('DOB month = 5 (MAY)', win.document.getElementById('d2').value === '5')
  ok('DOB year = 1992', win.document.getElementById('d3').value === '1992')
  ok('Birth city = Ho Chi Minh', win.document.getElementById('bc1').value === 'Ho Chi Minh')
  ok('Birth country = VIETNAM', win.document.getElementById('bco1').value === 'VIETNAM')
  ok('Does Not Apply 勾上', win.document.getElementById('nat1na').checked === true)
}

// ─── Case 2: select 精确匹配,MALE ≠ FEMALE 子串误配 ───
console.log('\nCase 2: select 精确优先 — 不被 FEMALE 误配')
{
  const { win } = loadInJsdom(`<!doctype html><html><body>
    <label for="sx">Sex</label><select id="sx">
      <option value=""></option><option>MALE</option><option>FEMALE</option>
    </select></body></html>`)
  const profile = { identity: { sex: 'F' } }
  const g = win.HTEX.buildGuide(profile)
  const r = win.HTEX.fill(g, 'personal1')
  ok('Sex = FEMALE', win.document.getElementById('sx').value === 'FEMALE')
  ok('filled 计数 = 1', r.summary.filled === 1)
}

// ─── Case 3: radio YES/NO ───
console.log('\nCase 3: Personal 2 radio')
{
  const { win } = loadInJsdom(buildPersonal2Html())
  const profile = {
    identity: { nationality: 'VIETNAM', hasOtherNationality: false },
  }
  // 跑全字段(personal2 + nationalId 空 → na)
  // 需要 buildGuide 知道所有 section; 这里只模拟 personal2
  const g = win.HTEX.buildGuide(profile)
  const r = win.HTEX.fill(g, 'personal2')
  ok('Nationality = VIETNAM', win.document.getElementById('nat2').value === 'VIETNAM')
  ok('Radio NO checked', win.document.getElementById('han_n').checked === true)
  ok('Radio YES NOT checked', win.document.getElementById('han_y').checked === false)
  ok('NationalId DoesNotApply 勾', win.document.getElementById('nidna').checked === true)
}

// ─── Case 4: not_found — 标签找不到时,不动别的框 ───
console.log('\nCase 4: not_found 不乱填别的框')
{
  const { win } = loadInJsdom(`<!doctype html><html><body>
    <table>
      <tr><td><label for="ot">Some Other Field</label></td><td><input id="ot" type="text"></td></tr>
    </table></body></html>`)
  const profile = { identity: { surname: 'nguyen', givenName: 'van' } }
  const g = win.HTEX.buildGuide(profile)
  const r = win.HTEX.fill(g, 'personal1')
  ok('not_found 计数 > 0 或 manual 计数 > 0', (r.summary.not_found + r.summary.manual) >= 7)
  ok('"Some Other Field" 没被填', win.document.getElementById('ot').value === '')
}

// ─── Case 5: 必填缺值 → manual ───
console.log('\nCase 5: 必填缺值 = manual')
{
  const { win } = loadInJsdom(buildPersonal1Html())
  const profile = { identity: {} }
  const g = win.HTEX.buildGuide(profile)
  const r = win.HTEX.fill(g, 'personal1')
  ok('manual 计数 > 0', r.summary.manual >= 7) // 必填缺值
  ok('na 计数 = 1', r.summary.na === 1) // nativeName 可空
}

// ─── Case 6: textarea ───
console.log('\nCase 6: textarea 填值')
{
  const { win } = loadInJsdom(`<!doctype html><html><body>
    <table>
      <tr><td><label>Primary Occupation</label></td><td><input id="occ" type="text"></td></tr>
      <tr><td><label>Briefly describe your duties</label></td><td><textarea id="duties" rows="3"></textarea></td></tr>
    </table></body></html>`)
  const profile = { work: { occupation: 'Engineer', duties: 'Build APIs and review code' } }
  const g = win.HTEX.buildGuide(profile)
  const r = win.HTEX.fill(g, 'work_education')
  ok('textarea filled', win.document.getElementById('duties').value === 'Build APIs and review code')
  ok('text filled', win.document.getElementById('occ').value === 'Engineer')
}

// ─── Case 7: autoFill postback 跟填 ───
console.log('\nCase 7: autoFill 跟填')
{
  const { win, doc } = loadInJsdom(`<!doctype html><html><body>
    <table>
      <tr><td><label>Purpose of Trip to the U.S.</label></td><td>
        <select id="pur"><option value=""></option>
          <option>TEMP. BUSINESS PLEASURE VISITOR (B)</option>
        </select></td></tr>
    </table>
    <div id="postback-container"></div>
  </body></html>`)
  const profile = {
    travel: { purpose: 'tourism' },
  }
  const g = win.HTEX.buildGuide(profile)
  const updates = []
  win.HTEX.autoFill(g, { onUpdate: (r) => updates.push(r), watchMs: 200 })

  // 模拟 postback:选了 B 类后冒一个新字段
  setTimeout(() => {
    const tbl = doc.getElementById('postback-container')
    tbl.innerHTML = '<table><tr>' +
      '<td><label>Specify (sub-question)</label></td>' +
      '<td><input id="sub" type="text"></td>' +
      '</tr></table>'
  }, 50)

  // 等 MutationObserver 触发(250ms 防抖)
  await new Promise(r => setTimeout(r, 500))
  // sub 这个字段不在 guide 里,所以不会被填;但前面 not_found 的 Purpose 应该已经被填
  ok('Purpose 已填', doc.getElementById('pur').value === 'TEMP. BUSINESS PLEASURE VISITOR (B)')
}

console.log(`\n${pass}/${pass + fail} 通过`)
if (fail) process.exit(1)