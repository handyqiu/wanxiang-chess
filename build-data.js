/**
 * build-data.js
 * 生成站点数据文件 data.json
 *
 * 用法:
 *   node build-data.js            # 使用本地源 data-source.json
 *   node build-data.js --remote   # 尝试从远程数据源拉取（需配置 SOURCE_URL）
 *
 * 扩展：要接入飞书/Google Sheets 时，实现下方 fetchRemote() 即可
 */
const fs = require('fs');
const path = require('path');

const OUT = path.join(__dirname, 'data.json');
const SOURCE_URL = process.env.SOURCE_URL; // 远程数据源 URL（可选）

// ---------- 本地数据源（默认）----------
function loadLocal() {
  const src = path.join(__dirname, 'data-source.json');
  if (fs.existsSync(src)) {
    return JSON.parse(fs.readFileSync(src, 'utf8'));
  }
  // 无源文件时，保持现有 data.json 不变
  if (fs.existsSync(OUT)) {
    console.log('[build] 未找到 data-source.json，沿用现有 data.json');
    return null;
  }
  throw new Error('缺少数据源文件 data-source.json');
}

// ---------- 远程数据源（可选扩展）----------
async function fetchRemote() {
  if (!SOURCE_URL) return null;
  console.log('[build] 拉取远程数据源:', SOURCE_URL);
  const res = await fetch(SOURCE_URL);
  if (!res.ok) throw new Error('远程数据源拉取失败: ' + res.status);
  return res.json(); // 需与 data.json 结构一致
}

// ---------- 数据校验 ----------
function validate(data) {
  const errors = [];
  if (!data.rosters?.length) errors.push('rosters 为空');
  if (!data.videos?.length) errors.push('videos 为空');
  (data.rosters || []).forEach((r, i) => {
    if (!/^\d+$/.test(r.code)) errors.push(`rosters[${i}] 阵容码非纯数字: ${r.code}`);
    if (!r.name || !r.faction) errors.push(`rosters[${i}] 缺少字段`);
  });
  if (errors.length) throw new Error('数据校验失败:\n' + errors.join('\n'));
  console.log('[build] 校验通过');
}

(async () => {
  try {
    let data = await fetchRemote();
    if (!data) data = loadLocal();
    if (data) {
      validate(data);
      fs.writeFileSync(OUT, JSON.stringify(data, null, 2), 'utf8');
      console.log('[build] 已生成', OUT, `(${(data.rosters||[]).length} 套阵容)`);
    }
  } catch (e) {
    console.error('[build] 错误:', e.message);
    process.exit(1);
  }
})();
