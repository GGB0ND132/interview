# 面试练习前端

React 19 + TypeScript + Vite。完整的首次配置和题库初始化见[根 README](../README.md)。目录名沿用 `fronted`。

## 运行

在本目录执行，先确保后端已在 8017 端口启动：

```powershell
npm ci
$env:INTERVIEW_BACKEND_URL='http://127.0.0.1:8017'
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5177 --strictPort
```

`/api` 由 Vite 代理至后端。没有设置环境变量时，默认后端为 `http://127.0.0.1:8000`；变量须在启动 Vite 的终端设置，修改后重启 Vite。

| 路由 | 内容 |
| --- | --- |
| `/question-practice` | 真实随机单题、反馈、最近练习和问题报告 |
| `/practice` | 真实模拟面试、JD/简历确认和最近会话/报告 |
| `/materials`、`/history` | 仍含演示数据，不能当作真实资料入库和统一历史 |

草稿使用浏览器 localStorage；服务端保存已提交答案及报告。浏览器或端口改变会切换草稿存储空间。密钥不要放到前端变量中。

## 验证

```powershell
npm test
npm run lint
npm run build
```

设计依据：[UI.md](../UI.md)和[当前页面稿](../docs/design/页面设计稿_V3.md)。验收步骤：[阶段演示手册](../docs/acceptance/17-demo-runbook.md)。
