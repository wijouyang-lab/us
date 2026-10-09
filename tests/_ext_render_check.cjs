// 校验 app.js 的 positionCard 在 Extended_Price 为空 / 有值时的渲染行为。
// 仅抽取 positionCard 函数本体（用 s=null 跳过 STOCKS 依赖分支），不加载整个 app.js。
const fs = require('fs');
const path = require('path');

const appJs = fs.readFileSync(path.join(__dirname, '..', 'app.js'), 'utf8');

function extractFn(src, name) {
  const sig = 'function ' + name + '(';
  const i = src.indexOf(sig);
  if (i < 0) throw new Error('找不到函数: ' + name);
  const j = src.indexOf('{', i);
  let depth = 0;
  for (let k = j; k < src.length; k++) {
    const c = src[k];
    if (c === '{') depth++;
    else if (c === '}') { depth--; if (depth === 0) return src.slice(i, k + 1); }
  }
  throw new Error('括号不匹配: ' + name);
}

// 最小桩：positionCard 在 s=null 时只用到 esc / nv / num / NA
const esc = (s) => String(s == null ? '' : s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
const nv = (v, d = 2) => (v == null || v === '' || isNaN(Number(v))) ? '—' : Number(v).toFixed(d);
const num = (v) => (v == null || v === '') ? null : Number(v);
const NA = '—';

// 抽取 positionCard 与其依赖的 extLabel，包进同一工厂函数，
// 让 positionCard 闭包捕获真实的 extLabel（不加载整个 app.js）。
const factory = eval('(function(){' + extractFn(appJs, 'extLabel') + ';'
    + extractFn(appJs, 'positionCard') + '; return positionCard; })');
const positionCard = factory();

let pass = 0, fail = 0;
function check(name, ok) {
  if (ok) { pass++; console.log('  [PASS] ' + name); }
  else { fail++; console.log('  [FAIL] ' + name); }
}

// 用例 1：Extended_Price 为空字符串 → 不渲染 pos-ext 行
const empty = positionCard({ ticker: 'AMD', current_price: 100.5, extended_price: '', extended_time: '' }, null);
check('ext 为空字符串 → 无 pos-ext 行', !empty.includes('pos-ext'));

// 用例 2：Extended_Price 为 null → 不渲染
const nullExt = positionCard({ ticker: 'AMD', current_price: 100.5, extended_price: null, extended_time: null }, null);
check('ext 为 null → 无 pos-ext 行', !nullExt.includes('pos-ext'));

// 用例 3：Extended_Price 有值 → 渲染盘后小字 + 价格 + 时间
const filled = positionCard({ ticker: 'AMD', current_price: 100.5, extended_price: '101.50', extended_time: '10-09 18:30 ET' }, null);
check('ext 有值 → 含 pos-ext 行', filled.includes('pos-ext'));
check('ext 有值 → 含盘后标签', filled.includes('盘后'));
check('ext 有值 → 含价格 101.50', filled.includes('101.50'));
check('ext 有值 → 含时间 18:30 ET', filled.includes('18:30 ET'));
check('ext 有值 → 仍渲染 Current_Price 100.50', filled.includes('100.50'));

console.log(`结果：通过 ${pass} / ${pass + fail}`);
process.exit(fail === 0 ? 0 : 1);
