# 股票交易系统 MVP 前端技术方案（Web 优先，多端复用）

> 对应需求来源：`requirements/functional-requirements.md` 及 `requirements/mvp-requirements-spec.md`。
> 目标：覆盖 MVP 全需求（账户、行情、自选、图表、交易、资产、提醒）并支持后续 iOS/macOS/Android 复用。

---

## 1. 技术目标与约束

- 覆盖 MVP 全功能，不遗漏需求域。
- Web 为首发端，架构支持多端复用。
- 高性能实时行情与订单状态更新。
- 高安全：登录风控、敏感信息保护、前端防注入。
- 可观测与可测试：可灰度、可回放、可监控。

---

## 2. 技术选型（成熟开源）

### 2.1 框架与基础设施
- **Monorepo**：`pnpm workspace + Turborepo`。
- **跨端 UI 方案**：
  - Web：`React 18 + Next.js 14(App Router)`。
  - 移动复用层：`React Native + Expo`（P1 开始接入），复用业务逻辑层与设计系统 token。
  - 桌面：`Tauri`（可选）承载 Web 应用壳。
- **状态管理**：`Redux Toolkit + RTK Query`（服务端状态）+ `zustand`（局部交互态）。
- **图表引擎**：`TradingView Lightweight Charts`（MVP），绘图扩展自研 Overlay。
- **表单与校验**：`react-hook-form + zod`。
- **样式系统**：`TailwindCSS + CSS Variables + Design Tokens`。
- **国际化**：`react-intl`。
- **实时通信**：WebSocket（行情、订单回报）+ SSE（通知兜底）。

### 2.2 复用策略
- `packages/ui`: 通用组件库（按钮、表格、弹窗、行情卡片、订单状态徽标）。
- `packages/domain`: 业务领域模型（订单、持仓、提醒、行情实体定义与转换）。
- `packages/sdk`: API Client + 鉴权封装 + 重试/幂等逻辑。
- `packages/charts`: K线容器、指标插件、绘图工具。
- `apps/web`: Web 主应用。
- `apps/mobile`（P1）：直接复用 `domain/sdk/ui tokens`。

---

## 3. 前端总体架构分层

```text
[Presentation Layer]
  页面/路由/容器（Next.js）
      ↓
[Application Layer]
  UseCase Hooks（登录、下单、撤单、设置提醒）
      ↓
[Domain Layer]
  领域对象 + 规则（订单状态机、提醒去重、持仓计算）
      ↓
[Infrastructure Layer]
  API SDK / WS Client / Local Cache / 埋点与监控
```

### 3.1 分层职责
- Presentation：仅处理 UI 展示与交互编排。
- Application：编排跨域流程（如“下单前校验→确认→提交→状态追踪”）。
- Domain：沉淀跨端复用规则，避免散落在页面。
- Infrastructure：处理协议、重连、鉴权、缓存、错误映射。

---

## 4. MVP 需求逐项前端设计（无遗漏）

> 新增统一“账户模式切换器”（实盘/模拟），确保未开通真实券商时可体验全部核心功能。

## 4.1 MVP-ACC 账户与安全

### MVP-ACC-01 注册/登录
- 页面：`/auth/login`、`/auth/register`。
- 组件：登录表单、验证码输入、错误提示条。
- 规则：
  - 前端校验密码强度（8~32，大小写+数字）。
  - 验证码倒计时与重发节流。
- 状态：
  - `idle/loading/success/error/locked`。

### MVP-ACC-02 新设备验证与登录风控
- 交互：命中风控后弹出二次验证 `RiskChallengeModal`。
- 行为：展示失败剩余次数、锁定倒计时。
- 安全：仅在 HttpOnly Cookie 存 token，不存 localStorage。

## 4.2 MVP-MKT 行情与自选

### MVP-MKT-01 行情列表/搜索/个股详情
- 页面：`/markets`、`/symbol/[code]`。
- 组件：`QuoteTable`、`SearchBox`、`QuoteHeader`、`L1OrderBook`。
- 实时：
  - 行情 WS 增量订阅（按可见列表订阅，虚拟滚动优化）。
  - 弱网降级为 3~5 秒轮询。
- 性能：列表虚拟化 `react-virtualized`。

### MVP-MKT-02 自选分组管理
- 页面：`/watchlist`。
- 组件：分组树、拖拽排序（`dnd-kit`）、批量操作条。
- 规则：
  - 组上限 20，组内标的上限 500。
  - 停牌/退市标的展示状态徽标。

## 4.3 MVP-CHT 图表分析

### MVP-CHT-01 周期与指标
- 组件：`KlineChart`、`IndicatorPanel`。
- 周期：1m/5m/15m/1D。
- 指标：MA/EMA/MACD/RSI（可叠加上限 4）。
- 数据策略：先主图后指标，指标异步渲染。

### MVP-CHT-02 绘图与模板
- 组件：`DrawingToolbar`、`TemplateManager`。
- 绘图：趋势线、水平线、文本标注。
- 模板：最多 3 套，支持覆盖与重命名。

## 4.4 MVP-TRD 交易与订单

### MVP-TRD-01 下单（市价/限价）
- 页面：个股详情右侧下单面板 + 独立交易页 `/trade`。
- 组件：`OrderForm`、`BuyingPowerCard`、`PreCheckResult`。
- 流程：
  1) 本地字段校验 → 2) 服务端 pre-check → 3) 二次确认弹窗 → 4) 下单提交。
- 防重：按钮防抖 + 客户端 `clientOrderId`。

### MVP-TRD-02 订单跟踪与撤单
- 页面：`/orders`。
- 组件：`OrderStatusTable`、`CancelAction`、`RejectReasonTag`。
- 实时：订单状态 WS push；断线后自动补拉。

## 4.5 MVP-AST 资产与持仓

### MVP-AST-01 资产总览
- 页面：`/portfolio`。
- 组件：总资产卡、现金卡、当日盈亏卡。
- 刷新：10 秒轮询 + 手动刷新。

### MVP-AST-02 持仓明细与多账户筛选
- 组件：`PositionTable`、`AccountFilter`。
- 字段：可卖数量、成本价、现价、收益率。
- 异常：汇率失败显示“估算”。

## 4.6 MVP-ALT 提醒与通知

### MVP-ALT-01 价格提醒
- 页面：个股页提醒弹窗 + `/alerts`。
- 组件：`AlertForm`、`AlertList`、`AlertHistory`。
- 规则：每用户最多 30 条；同标的同方向同阈值去重。

### MVP-ALT-02 通知中心
- 页面：`/notifications`。
- 组件：通知列表、已读/未读筛选、归档。
- 渠道：站内信为主，邮件状态回显。

---


## 4.7 MVP-SIM 模拟账户与模拟交易

### MVP-SIM-01 模拟账户初始化
- 组件：`AccountModeSwitcher`、`SimAccountBadge`、`SimResetDialog`。
- 行为：
  - 无真实账户时默认进入模拟模式。
  - 模拟账户展示“SIM”标识，避免与实盘误操作。

### MVP-SIM-02 模拟交易闭环
- 复用页面：`/trade`、`/orders`、`/portfolio`、`/notifications`。
- 交互规则：
  - 下单/撤单/订单状态/持仓资产展示与实盘一致。
  - 所有模拟数据使用独立数据源标签 `source=paper`。
- 安全提示：在交易确认弹窗中固定显示“当前为模拟交易，不会产生真实资金变动”。

---

## 5. 前端关键流程定义

### 5.1 登录与风控流程
1. 提交账号密码。
2. 返回风控挑战则弹窗验证。
3. 验证通过写入会话，跳转行情页。
4. 失败达到阈值展示锁定倒计时。

### 5.2 下单流程
1. 用户填写参数并选择账户模式（实盘/模拟）。
2. 调用 pre-check 接口返回风控结果。
3. 若价格偏离>5%，强制二次确认。
4. 提交订单并展示订单号（模拟单标记 SIM）。
5. 在订单列表追踪状态并可撤单。

### 5.3 提醒触发流程
1. 创建提醒并写入提醒列表。
2. 服务端触发后推送通知事件。
3. 前端通知中心展示触发详情与时间。

---

## 6. 前端安全设计

- XSS：默认 React 转义 + 富文本白名单（如后续接入社区）。
- CSRF：SameSite Cookie + CSRF Token 双校验。
- 点击劫持：`X-Frame-Options: DENY`。
- 敏感信息：token 仅 HttpOnly Cookie；禁止明文持久化。
- API 签名：高风险操作（下单/撤单）附带一次性 nonce 与时间戳。
- 内容安全策略：`CSP` 白名单（仅可信域名脚本/WS）。

---

## 7. 可观测与质量保障

- 日志埋点：登录、下单、撤单、提醒设置、错误码分布。
- 性能指标：FCP/LCP、首屏行情时间、下单交互耗时。
- 错误监控：`Sentry`（前端异常 + 会话重放）。
- 自动化测试：
  - 单测：Vitest + Testing Library。
  - E2E：Playwright（登录、下单、撤单、提醒）。

---

## 8. 迭代与交付建议

- Sprint 1：账号、行情列表、搜索、自选。
- Sprint 2：图表、指标、模板。
- Sprint 3：下单、订单状态、撤单。
- Sprint 4：资产持仓、提醒通知、性能与安全加固。

## 9. 文档版本

- v1.1：补充可评审状态标识与交付说明。
