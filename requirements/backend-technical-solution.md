# 股票交易系统 MVP 后端技术方案（Go 微服务 + DDD）

> 对应需求来源：`requirements/functional-requirements.md` 及 `requirements/mvp-requirements-spec.md`。
> 目标：MVP 全量需求可落地，支持多券商接入、统一交易与风控。

---

## 1. 设计原则

- 微服务解耦：按业务边界拆分服务，避免巨石。
- 领域驱动设计（DDD）：服务内部分层，领域规则内聚。
- 多券商兼容：Adapter 模式屏蔽券商差异。
- 高可用高一致：交易链路幂等、可审计、可回放。
- 安全合规优先：鉴权、凭据加密、审计追踪完整。

---

## 2. 技术栈

- 语言：Go 1.22+
- 框架：`gin`（HTTP）、`grpc-go`（内部 RPC）
- 服务治理：`Kubernetes + Istio`（可选）
- 消息队列：`Kafka`（行情、订单事件、通知事件）
- 缓存：`Redis`
- 数据库：`PostgreSQL 16`（核心交易与账户）
- 时序数据：`TimescaleDB`（行情K线，可选）
- 对象存储：`S3/MinIO`（审计快照、报表）
- 可观测：`Prometheus + Grafana + Loki + Tempo`

---

## 3. 微服务拆分与职责

## 3.1 服务清单

1. **api-gateway**
   - 统一入口、鉴权、限流、路由、灰度。
2. **iam-service**（账户与安全）
   - 注册登录、设备管理、MFA/验证码、登录风控。
3. **market-service**（行情）
   - 行情聚合、快照查询、订阅管理、延时/实时权限控制。
4. **watchlist-service**（自选）
   - 自选分组、标的管理、排序。
5. **chart-service**（图表数据）
   - K线聚合、指标计算、模板存储。
6. **order-service**（交易订单）
   - 下单、撤单、订单状态机、幂等处理。
7. **broker-gateway-service**（券商网关）
   - 统一券商适配、协议转换、回报标准化。
8. **portfolio-service**（资产持仓）
   - 资产汇总、持仓计算、汇率折算。
9. **risk-service**（风控）
   - 下单前规则校验（资金、仓位、时段、价格偏离）。
10. **alert-service**（提醒）
   - 价格提醒规则、触发引擎、去重与冷却。
11. **notification-service**（通知）
   - 站内信/邮件投递、模板渲染、状态回执。
12. **audit-service**（审计）
   - 高风险操作审计、链路追踪、合规导出。

## 3.2 MVP 功能到服务映射（无遗漏）

| MVP 功能 | 主要服务 | 协作服务 |
|---|---|---|
| ACC-01 登录注册 | iam-service | api-gateway, audit-service |
| ACC-02 登录风控 | iam-service | risk-service, audit-service |
| MKT-01 行情与搜索 | market-service | broker-gateway-service |
| MKT-02 自选分组 | watchlist-service | market-service |
| CHT-01 周期与指标 | chart-service | market-service |
| CHT-02 模板与绘图 | chart-service | iam-service |
| TRD-01 下单 | order-service | risk-service, broker-gateway-service |
| TRD-02 撤单与状态 | order-service | broker-gateway-service, notification-service |
| AST-01 资产总览 | portfolio-service | broker-gateway-service, fx-rate provider |
| AST-02 持仓筛选 | portfolio-service | iam-service |
| ALT-01 价格提醒 | alert-service | market-service |
| ALT-02 通知触达 | notification-service | alert-service, order-service |

---

## 4. 服务内 DDD 分层（统一模板）

```text
/interface
  http handler / grpc handler / dto
/application
  usecase / command / query / transaction script
/domain
  aggregate / entity / value object / domain service / repository interface
/infrastructure
  repository impl / mq producer-consumer / external adapter / cache
```

### 示例：order-service 聚合
- Aggregate：`Order`
- Entity：`OrderLeg`（预留期权）
- ValueObject：`Price`, `Quantity`, `OrderType`, `TimeInForce`
- DomainRule：状态机流转、可撤单判定、拒单映射
- Repository：`OrderRepo`, `OrderEventRepo`

---

## 5. 多券商兼容设计（核心）

## 5.1 Adapter 抽象

```go
type BrokerAdapter interface {
    PlaceOrder(ctx context.Context, req UnifiedOrderRequest) (UnifiedOrderResponse, error)
    CancelOrder(ctx context.Context, req UnifiedCancelRequest) (UnifiedCancelResponse, error)
    QueryOrder(ctx context.Context, brokerOrderID string) (UnifiedOrderStatus, error)
    QueryPositions(ctx context.Context, accountID string) ([]UnifiedPosition, error)
    QueryAssets(ctx context.Context, accountID string) (UnifiedAssetSnapshot, error)
    SubscribeQuote(ctx context.Context, symbols []string) (<-chan UnifiedQuoteEvent, error)
}
```

## 5.2 统一字段模型
- 统一订单号：`platform_order_id`（平台生成）+ `broker_order_id`（券商原生）。
- 统一账户：`platform_account_id` 映射多券商 `broker_account_id`。
- 统一错误码：`Uxxxx`（例如 `U1003_BALANCE_NOT_ENOUGH`）。
- 统一状态：`PENDING/SUBMITTED/PARTIAL/FILLED/CANCELED/REJECTED/EXPIRED`。

## 5.3 券商差异处理
- 最小交易单位差异（整股/碎股）由 Adapter 内部转换。
- 交易时段差异（盘前盘后支持）由能力探针 `BrokerCapability` 决策。
- 费用字段差异通过 `fee_breakdown_jsonb` 扩展存储。

---

## 6. 核心流程设计

## 6.1 下单流程
1. API Gateway 鉴权 + 限流。
2. order-service 接收请求，生成 `platform_order_id` + 幂等键校验。
3. 调用 risk-service 执行前置风控。
4. 通过后调用 broker-gateway-service 路由到券商 Adapter。
5. 回写订单状态并发布 `order.status.changed` 事件（Kafka）。
6. notification-service 向站内信/邮件推送。

## 6.2 提醒触发流程
1. alert-service 持久化规则并构建内存索引。
2. market-service 推送行情事件到 Kafka。
3. alert-service 消费行情并判定穿越阈值。
4. 命中后写触发记录 + 发布通知事件。

## 6.3 资产同步流程
1. portfolio-service 按账户拉取券商资产与持仓。
2. 汇率服务折算多币种资产。
3. 持仓快照写库并更新缓存。

---

## 7. 数据库模型与索引设计

> 主库：PostgreSQL。字段含多券商兼容字段，关键查询均有复合索引。

## 7.1 账户与安全

### `users`
- `id (pk)`
- `email (unique)`
- `phone (unique)`
- `password_hash`
- `status`
- `created_at`
- 索引：`idx_users_status_created(status, created_at desc)`

### `user_devices`
- `id (pk)`
- `user_id`
- `device_fingerprint`
- `last_login_ip`
- `risk_level`
- `last_seen_at`
- 索引：
  - `uniq_user_device(user_id, device_fingerprint)`
  - `idx_device_last_seen(last_seen_at desc)`

## 7.2 券商账户映射

### `broker_accounts`
- `id (pk)`
- `user_id`
- `broker_type`（IBKR/FUTU/...）
- `broker_account_id`
- `account_mask`
- `base_currency`
- `permission_jsonb`
- `credential_ref`（KMS 引用）
- `status`
- 索引：
  - `uniq_broker_account(broker_type, broker_account_id)`
  - `idx_user_broker_status(user_id, broker_type, status)`

## 7.3 订单

### `orders`
- `id (pk)`
- `platform_order_id (unique)`
- `client_order_id`
- `user_id`
- `platform_account_id`
- `broker_type`
- `broker_account_id`
- `broker_order_id`
- `symbol`
- `market`
- `side`
- `order_type`
- `time_in_force`
- `price`
- `quantity`
- `filled_quantity`
- `avg_fill_price`
- `status`
- `reject_code`
- `reject_reason`
- `fee_breakdown_jsonb`
- `idempotency_key`
- `created_at`
- `updated_at`
- 索引：
  - `uniq_orders_platform_order_id(platform_order_id)`
  - `uniq_orders_idempotency(user_id, idempotency_key)`
  - `idx_orders_user_status_time(user_id, status, created_at desc)`
  - `idx_orders_broker_order(broker_type, broker_order_id)`
  - `idx_orders_account_time(platform_account_id, created_at desc)`

### `order_events`
- `id (pk)`
- `platform_order_id`
- `event_type`
- `event_payload_jsonb`
- `event_time`
- 索引：`idx_order_events_order_time(platform_order_id, event_time desc)`

## 7.4 持仓与资产

### `position_snapshots`
- `id (pk)`
- `user_id`
- `platform_account_id`
- `broker_type`
- `broker_account_id`
- `symbol`
- `market`
- `qty_total`
- `qty_available`
- `cost_price`
- `last_price`
- `unrealized_pnl`
- `snapshot_time`
- 索引：
  - `idx_positions_user_account_time(user_id, platform_account_id, snapshot_time desc)`
  - `idx_positions_symbol_time(symbol, snapshot_time desc)`

### `asset_snapshots`
- `id (pk)`
- `user_id`
- `platform_account_id`
- `broker_type`
- `broker_account_id`
- `base_currency`
- `total_asset`
- `cash`
- `market_value`
- `buying_power`
- `fx_rate_jsonb`
- `snapshot_time`
- 索引：`idx_assets_user_time(user_id, snapshot_time desc)`

## 7.5 提醒与通知

### `price_alerts`
- `id (pk)`
- `user_id`
- `symbol`
- `market`
- `direction`（UP/DOWN）
- `target_price`
- `status`（ACTIVE/PAUSED/DELETED）
- `cooldown_sec`
- `last_triggered_at`
- `created_at`
- 索引：
  - `uniq_alert_rule(user_id, symbol, direction, target_price, status)`（部分唯一，status=ACTIVE）
  - `idx_alert_symbol_status(symbol, status)`

### `alert_trigger_logs`
- `id (pk)`
- `alert_id`
- `trigger_price`
- `triggered_at`
- `payload_jsonb`
- 索引：`idx_alert_logs_alert_time(alert_id, triggered_at desc)`

### `notifications`
- `id (pk)`
- `user_id`
- `channel`（INBOX/EMAIL）
- `type`（ALERT/ORDER/RISK/SYSTEM）
- `title`
- `content`
- `status`（SENT/FAILED/READ）
- `provider_msg_id`
- `created_at`
- 索引：
  - `idx_notify_user_status_time(user_id, status, created_at desc)`
  - `idx_notify_user_type_time(user_id, type, created_at desc)`

---

## 8. 安全与合规设计

- 鉴权：OIDC + JWT（短期）+ Refresh Token（旋转）。
- 服务间鉴权：mTLS + SPIFFE（或签名 Token）。
- API 凭据：券商密钥使用 KMS 加密，数据库仅存 `credential_ref`。
- 数据脱敏：日志脱敏（账号、订单、邮箱、手机号）。
- 幂等与防重放：`idempotency_key + nonce + timestamp`。
- 权限模型：RBAC（用户/运营/管理员）+ 资源级校验。
- 审计：下单/撤单/登录风控命中全量审计不可变更存储。
- 合规：按地区配置行情授权策略与数据保留策略。

---

## 9. 稳定性与可观测

- SLO：
  - 下单接口 P95 < 2s
  - 行情查询 P95 < 300ms（缓存命中）
  - 订单状态回报延迟 < 1s（事件链路）
- 限流：用户级、IP级、接口级令牌桶。
- 熔断：券商 Adapter 熔断 + 退避重试。
- 补偿：订单状态对账任务（分钟级增量 + 日终全量）。
- 监控：
  - 业务指标：下单成功率、拒单率、提醒触发率。
  - 系统指标：QPS、错误率、延迟、消费者积压。

---

## 10. MVP 交付里程碑（后端）

- M1（2周）：IAM、行情读取、基础网关。
- M2（3周）：订单服务 + 券商网关 + 风控前置。
- M3（2周）：资产持仓、提醒通知。
- M4（2周）：审计、对账、安全加固、压测验收。

## 11. 文档版本

- v1.1：补充可评审状态标识与交付说明。
