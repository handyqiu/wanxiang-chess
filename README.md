# 万象棋境 · 王者万象棋教学攻略平台

静态站点，可部署到 GitHub Pages / Netlify / Vercel。

## 目录结构

```
.
├── index.html                      # 页面 + Vue 渲染逻辑（从 data.json 读数据）
├── data.json                        # ★ 全部内容数据（阵容/视频/棋手/阵营/FAQ）
├── data-source.json                 # （可选）给 build-data.js 用的源数据
├── build-data.js                    # 构建脚本：生成/校验 data.json
├── netlify.toml                     # Netlify 配置 + SPA 重定向
├── check.cjs                        # 本地校验脚本
└── .github/workflows/refresh.yml    # GitHub Actions 定时自动更新
```

## 本地预览

```bash
# 需要本地服务器（直接双击 index.html 会因 fetch 跨域失败）
python3 -m http.server 8000
# 访问 http://localhost:8000
```

## 本地校验

```bash
node check.cjs
```

## 如何更新内容

### 方式一：直接改 data.json（最简单）

编辑 `data.json` → 提交推送 → GitHub Pages 自动重新发布（约 1 分钟）。

### 方式二：自动更新（推荐）

`refresh.yml` 已配置：
- 每 6 小时自动跑一次（`0 */6 * * *`，UTC）
- 支持手动触发：GitHub → Actions → refresh-data → Run workflow

**接入远程数据源（可选）：**
1. 准备一个返回 JSON 的接口（结构同 `data.json`），如飞书/Google Sheets 导出
2. 仓库 Settings → Secrets → Actions → 新建 `SOURCE_URL`，填接口地址
3. 工作流运行时会自动拉取并覆盖 `data.json`，提交后 Pages 更新

## GitHub Pages 部署

1. 上传本目录所有文件到 GitHub 仓库
2. Settings → Pages → Source: Deploy from a branch → Branch: 主要角色 / main → 目录: / (root)
3. 保存后访问 `https://<用户名>.github.io/<仓库名>/`

## 添加新阵容/视频

在 `data.json` 对应数组追加一项即可。阵容码须为纯数字。
