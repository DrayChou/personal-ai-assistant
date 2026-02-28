# Claude Code CLI Header 配置参考

本文档收集整理了 Claude Code CLI 在调用 Anthropic API 时使用的 Header 配置，供开发参考。

## 版本信息

| 属性 | 值 |
|------|-----|
| CLI 版本 | 2.1.50.b97 |
| 包版本 | 0.74.0 |
| Node 运行时 | v24.3.0 |

---

## 标准请求头 (Standard Headers)

```javascript
{
  "accept": "application/json",
  "anthropic-dangerous-direct-browser-access": "true",
  "anthropic-version": "2023-06-01",
  "user-agent": "claude-cli/2.1.50 (external, cli)",
  "x-app": "cli",
  "x-stainless-arch": "arm64",
  "x-stainless-lang": "js",
  "x-stainless-os": "MacOS",
  "x-stainless-package-version": "0.74.0",
  "x-stainless-retry-count": "0",
  "x-stainless-runtime": "node",
  "x-stainless-runtime-version": "v24.3.0",
  "x-stainless-timeout": "600"
}
```

### 字段说明

| Header | 值 | 说明 |
|--------|-----|------|
| `accept` | `application/json` | 接受 JSON 响应格式 |
| `anthropic-dangerous-direct-browser-access` | `true` | 允许浏览器直接访问（绕过某些限制） |
| `anthropic-version` | `2023-06-01` | Anthropic API 版本 |
| `user-agent` | `claude-cli/2.1.50 (external, cli)` | 客户端标识 |
| `x-app` | `cli` | 应用类型标识 |
| `x-stainless-arch` | `arm64` | 系统架构（x64/arm64） |
| `x-stainless-lang` | `js` | 编程语言 |
| `x-stainless-os` | `MacOS` | 操作系统 |
| `x-stainless-package-version` | `0.74.0` | SDK 包版本 |
| `x-stainless-retry-count` | `0` | 当前重试次数 |
| `x-stainless-runtime` | `node` | JavaScript 运行时 |
| `x-stainless-runtime-version` | `v24.3.0` | Node.js 版本 |
| `x-stainless-timeout` | `600` | 请求超时时间（秒） |

---

## Beta 功能标识 (Beta Flags)

### 基础 Beta 列表

以下 Beta 功能对所有模型启用：

```javascript
[
  "claude-code-20250219",          // Claude Code 功能集
  "oauth-2025-04-20",              // OAuth 认证
  "interleaved-thinking-2025-05-14", // 交错思考模式
  "prompt-caching-scope-2026-01-05", // Prompt 缓存范围
  "effort-2025-11-24",             // 思考力度控制
  "adaptive-thinking-2026-01-28"   // 自适应思考
]
```

### 模型专属 Beta

| 模型系列 | Beta 标识 |
|----------|-----------|
| Opus | `context-management-2025-06-27` |

---

## 计费头 (Billing Header)

Claude Code CLI 使用特殊的计费头来追踪请求来源：

### 格式

```
x-anthropic-billing-header: cc_version={版本}; cc_entrypoint=cli; cch={随机码};
```

### 示例

```
x-anthropic-billing-header: cc_version=2.1.50.b97; cc_entrypoint=cli; cch=a3f7b;
```

### 随机码生成规则

- 每次请求生成一个新的 5 字符十六进制随机码
- 使用 `crypto.randomBytes(3)` 生成，截取前 5 位

---

## TypeScript 类型定义

```typescript
/**
 * Header 配置档案
 */
interface HeaderProfile {
  /** CLI 版本号 */
  ccVersion: string;
  /** 标准请求头 */
  headers: Record<string, string>;
  /** 基础 Beta 功能列表 */
  betaBase: string[];
  /** 模型专属的 Beta 功能 */
  betaByModel: {
    opus?: string[];
  };
}

/**
 * Header 配置档案集合
 */
type HeaderProfiles = Record<string, HeaderProfile>;
```

---

## 完整配置代码参考

```javascript
import { randomBytes } from "node:crypto";

/** @type {HeaderProfile} */
const CLAUDE_CLI_2_1_50_PROFILE = {
  ccVersion: "2.1.50.b97",
  headers: {
    accept: "application/json",
    "anthropic-dangerous-direct-browser-access": "true",
    "anthropic-version": "2023-06-01",
    "user-agent": "claude-cli/2.1.50 (external, cli)",
    "x-app": "cli",
    "x-stainless-arch": "arm64",
    "x-stainless-lang": "js",
    "x-stainless-os": "MacOS",
    "x-stainless-package-version": "0.74.0",
    "x-stainless-retry-count": "0",
    "x-stainless-runtime": "node",
    "x-stainless-runtime-version": "v24.3.0",
    "x-stainless-timeout": "600",
  },
  betaBase: [
    "claude-code-20250219",
    "oauth-2025-04-20",
    "interleaved-thinking-2025-05-14",
    "prompt-caching-scope-2026-01-05",
    "effort-2025-11-24",
    "adaptive-thinking-2026-01-28",
  ],
  betaByModel: {
    opus: ["context-management-2025-06-27"],
  },
};

/** @type {Record<string, HeaderProfile>} */
export const HEADER_PROFILES = {
  "claude-cli-default": CLAUDE_CLI_2_1_50_PROFILE,
  "claude-cli-2.1.50": CLAUDE_CLI_2_1_50_PROFILE,
};

export const DEFAULT_HEADER_PROFILE = "claude-cli-2.1.50";

/**
 * 获取 Header 配置档案
 * @param {string | undefined} profileName - 档案名称
 * @returns {HeaderProfile}
 */
export function getHeaderProfile(profileName) {
  if (profileName && HEADER_PROFILES[profileName]) {
    return HEADER_PROFILES[profileName];
  }
  return HEADER_PROFILES[DEFAULT_HEADER_PROFILE];
}

/**
 * 检测模型系列
 * @param {string | undefined} model - 模型名称
 * @returns {"opus" | null}
 */
function detectModelFamily(model) {
  if (!model) return null;
  const normalized = model.toLowerCase();
  if (normalized.includes("opus")) return "opus";
  return null;
}

/**
 * 获取默认 Beta 功能列表
 * @param {string | undefined} profileName - 档案名称
 * @param {string | undefined} model - 模型名称
 * @returns {string[]}
 */
export function getDefaultBetas(profileName, model) {
  const profile = getHeaderProfile(profileName);
  const family = detectModelFamily(model);
  const familyBetas = family ? profile.betaByModel[family] || [] : [];
  return [...profile.betaBase, ...familyBetas];
}

/**
 * 生成计费头系统块
 * @param {string | undefined} profileName - 档案名称
 * @returns {string}
 */
export function getBillingHeaderBlock(profileName) {
  const profile = getHeaderProfile(profileName);
  const cch = randomBytes(3).toString("hex").slice(0, 5);
  return `x-anthropic-billing-header: cc_version=${profile.ccVersion}; cc_entrypoint=cli; cch=${cch};`;
}
```

---

## 新增版本配置步骤

如需添加新版本的 Header 配置：

1. 定义新的 `CLAUDE_CLI_x_y_z_PROFILE` 常量，包含目标 Claude CLI 版本的捕获头信息
2. 向 `HEADER_PROFILES` 添加版本化条目（如 `"claude-cli-3.0.0"`）
3. 将 `"claude-cli-default"` 别名指向新的配置常量
4. 可选：更新 `DEFAULT_HEADER_PROFILE` 为新的版本化键
5. 更新测试以覆盖新的配置档案

---

## 多平台 Header 变体

### macOS (ARM64) - 默认配置

```javascript
{
  "x-stainless-arch": "arm64",
  "x-stainless-os": "MacOS",
  "x-stainless-runtime-version": "v24.3.0"
}
```

### macOS (Intel/x64)

```javascript
{
  "x-stainless-arch": "x64",
  "x-stainless-os": "MacOS",
  "x-stainless-runtime-version": "v24.3.0"
}
```

### Linux (x64)

```javascript
{
  "x-stainless-arch": "x64",
  "x-stainless-os": "Linux",
  "x-stainless-runtime-version": "v20.11.0"
}
```

### Linux (ARM64)

```javascript
{
  "x-stainless-arch": "arm64",
  "x-stainless-os": "Linux",
  "x-stainless-runtime-version": "v20.11.0"
}
```

### Windows (x64)

```javascript
{
  "x-stainless-arch": "x64",
  "x-stainless-os": "Windows",
  "x-stainless-runtime-version": "v20.11.0"
}
```

### Windows (ARM64)

```javascript
{
  "x-stainless-arch": "arm64",
  "x-stainless-os": "Windows",
  "x-stainless-runtime-version": "v20.11.0"
}
```

---

## 历史版本配置参考

### CLI 2.1.49 配置

```javascript
const CLAUDE_CLI_2_1_49_PROFILE = {
  ccVersion: "2.1.49.b96",
  headers: {
    accept: "application/json",
    "anthropic-dangerous-direct-browser-access": "true",
    "anthropic-version": "2023-06-01",
    "user-agent": "claude-cli/2.1.49 (external, cli)",
    "x-app": "cli",
    "x-stainless-arch": "arm64",
    "x-stainless-lang": "js",
    "x-stainless-os": "MacOS",
    "x-stainless-package-version": "0.74.0",
    "x-stainless-retry-count": "0",
    "x-stainless-runtime": "node",
    "x-stainless-runtime-version": "v24.3.0",
    "x-stainless-timeout": "600",
  },
  betaBase: [
    "claude-code-20250219",
    "oauth-2025-04-20",
    "interleaved-thinking-2025-05-14",
    "prompt-caching-scope-2026-01-05",
    "effort-2025-11-24",
  ],
  betaByModel: {
    opus: ["context-management-2025-06-27"],
  },
};
```

### CLI 2.0.x 系列配置 (早期版本)

```javascript
const CLAUDE_CLI_2_0_PROFILE = {
  ccVersion: "2.0.31",
  headers: {
    accept: "application/json",
    "anthropic-dangerous-direct-browser-access": "true",
    "anthropic-version": "2023-06-01",
    "user-agent": "claude-cli/2.0.31 (external, cli)",
    "x-app": "cli",
    "x-stainless-arch": "arm64",
    "x-stainless-lang": "js",
    "x-stainless-os": "MacOS",
    "x-stainless-package-version": "0.24.0",
    "x-stainless-retry-count": "0",
    "x-stainless-runtime": "node",
    "x-stainless-runtime-version": "v18.19.0",
    "x-stainless-timeout": "600",
  },
  betaBase: [
    "claude-code-20250219",
    "oauth-2025-04-20",
  ],
  betaByModel: {},
};
```

### SDK 版本对应关系

| CLI 版本 | SDK 版本 | Node 版本 | 发布日期 |
|----------|----------|-----------|----------|
| 2.1.63 | 0.74.0+ | v24.3.0 | 2025-02 |
| 2.1.50 | 0.74.0 | v24.3.0 | 2025-01 |
| 2.1.49 | 0.74.0 | v24.3.0 | 2025-01 |
| 2.0.31+ | 0.24.0+ | v18.19.0 | 2024-08 |

---

## 关于 Stainless SDK

Claude Code CLI 使用 [Stainless](https://www.stainless.com/) 生成的 SDK 与 Anthropic API 通信。
Stainless 是一个基于 OpenAPI Spec 自动生成多语言 SDK 的工具。

### Stainless 特有 Header

所有 `x-stainless-*` 开头的 Header 均由 Stainless SDK 自动生成：

| Header | 说明 | 来源 |
|--------|------|------|
| `x-stainless-lang` | SDK 语言 | SDK 生成时固定 |
| `x-stainless-package-version` | SDK 包版本 | package.json 版本 |
| `x-stainless-os` | 操作系统 | 运行时检测 |
| `x-stainless-arch` | CPU 架构 | 运行时检测 |
| `x-stainless-runtime` | JS 运行时 | 固定为 `node` |
| `x-stainless-runtime-version` | Node.js 版本 | process.version |
| `x-stainless-retry-count` | 重试计数 | 请求中间件维护 |

### 参考资料

- [Anthropic TypeScript SDK GitHub](https://github.com/anthropics/anthropic-sdk-typescript)
- [Claude Code CLI GitHub](https://github.com/anthropics/claude-code)
- [Stainless 文档](https://www.stainless.com/docs)

---

## 完整 Header Profiles 配置

```javascript
import { randomBytes } from "node:crypto";

/**
 * @typedef {object} HeaderProfile
 * @property {string} ccVersion
 * @property {Record<string, string>} headers
 * @property {string[]} betaBase
 * @property {{ opus?: string[] }} betaByModel
 */

/** @type {HeaderProfile} */
const CLAUDE_CLI_2_1_63_PROFILE = {
  ccVersion: "2.1.63.b110",
  headers: {
    accept: "application/json",
    "anthropic-dangerous-direct-browser-access": "true",
    "anthropic-version": "2023-06-01",
    "user-agent": "claude-cli/2.1.63 (external, cli)",
    "x-app": "cli",
    "x-stainless-arch": "arm64",
    "x-stainless-lang": "js",
    "x-stainless-os": "MacOS",
    "x-stainless-package-version": "0.74.3",
    "x-stainless-retry-count": "0",
    "x-stainless-runtime": "node",
    "x-stainless-runtime-version": "v24.3.0",
    "x-stainless-timeout": "600",
  },
  betaBase: [
    "claude-code-20250219",
    "oauth-2025-04-20",
    "interleaved-thinking-2025-05-14",
    "prompt-caching-scope-2026-01-05",
    "effort-2025-11-24",
    "adaptive-thinking-2026-01-28",
    "agent-teams-2025-08-15",
  ],
  betaByModel: {
    opus: ["context-management-2025-06-27"],
  },
};

/** @type {HeaderProfile} */
const CLAUDE_CLI_2_1_50_PROFILE = {
  ccVersion: "2.1.50.b97",
  headers: {
    accept: "application/json",
    "anthropic-dangerous-direct-browser-access": "true",
    "anthropic-version": "2023-06-01",
    "user-agent": "claude-cli/2.1.50 (external, cli)",
    "x-app": "cli",
    "x-stainless-arch": "arm64",
    "x-stainless-lang": "js",
    "x-stainless-os": "MacOS",
    "x-stainless-package-version": "0.74.0",
    "x-stainless-retry-count": "0",
    "x-stainless-runtime": "node",
    "x-stainless-runtime-version": "v24.3.0",
    "x-stainless-timeout": "600",
  },
  betaBase: [
    "claude-code-20250219",
    "oauth-2025-04-20",
    "interleaved-thinking-2025-05-14",
    "prompt-caching-scope-2026-01-05",
    "effort-2025-11-24",
    "adaptive-thinking-2026-01-28",
  ],
  betaByModel: {
    opus: ["context-management-2025-06-27"],
  },
};

/** @type {HeaderProfile} */
const CLAUDE_CLI_2_1_49_PROFILE = {
  ccVersion: "2.1.49.b96",
  headers: {
    accept: "application/json",
    "anthropic-dangerous-direct-browser-access": "true",
    "anthropic-version": "2023-06-01",
    "user-agent": "claude-cli/2.1.49 (external, cli)",
    "x-app": "cli",
    "x-stainless-arch": "arm64",
    "x-stainless-lang": "js",
    "x-stainless-os": "MacOS",
    "x-stainless-package-version": "0.74.0",
    "x-stainless-retry-count": "0",
    "x-stainless-runtime": "node",
    "x-stainless-runtime-version": "v24.3.0",
    "x-stainless-timeout": "600",
  },
  betaBase: [
    "claude-code-20250219",
    "oauth-2025-04-20",
    "interleaved-thinking-2025-05-14",
    "prompt-caching-scope-2026-01-05",
    "effort-2025-11-24",
  ],
  betaByModel: {
    opus: ["context-management-2025-06-27"],
  },
};

/** @type {Record<string, HeaderProfile>} */
export const HEADER_PROFILES = {
  // 默认配置（始终指向最新稳定版）
  "claude-cli-default": CLAUDE_CLI_2_1_63_PROFILE,

  // 2.1.x 系列
  "claude-cli-2.1.63": CLAUDE_CLI_2_1_63_PROFILE,
  "claude-cli-2.1.50": CLAUDE_CLI_2_1_50_PROFILE,
  "claude-cli-2.1.49": CLAUDE_CLI_2_1_49_PROFILE,

  // 早期版本（简化配置）
  "claude-cli-2.0": {
    ccVersion: "2.0.31",
    headers: {
      accept: "application/json",
      "anthropic-dangerous-direct-browser-access": "true",
      "anthropic-version": "2023-06-01",
      "user-agent": "claude-cli/2.0.31 (external, cli)",
      "x-app": "cli",
      "x-stainless-arch": "arm64",
      "x-stainless-lang": "js",
      "x-stainless-os": "MacOS",
      "x-stainless-package-version": "0.24.0",
      "x-stainless-retry-count": "0",
      "x-stainless-runtime": "node",
      "x-stainless-runtime-version": "v18.19.0",
      "x-stainless-timeout": "600",
    },
    betaBase: ["claude-code-20250219", "oauth-2025-04-20"],
    betaByModel: {},
  },
};

export const DEFAULT_HEADER_PROFILE = "claude-cli-2.1.63";

/**
 * @param {string | undefined} profileName
 * @returns {HeaderProfile}
 */
export function getHeaderProfile(profileName) {
  if (profileName && HEADER_PROFILES[profileName]) {
    return HEADER_PROFILES[profileName];
  }
  return HEADER_PROFILES[DEFAULT_HEADER_PROFILE];
}

/**
 * @param {string | undefined} model
 * @returns {"opus" | null}
 */
function detectModelFamily(model) {
  if (!model) return null;
  const normalized = model.toLowerCase();
  if (normalized.includes("opus")) return "opus";
  return null;
}

/**
 * @param {string | undefined} profileName
 * @param {string | undefined} model
 * @returns {string[]}
 */
export function getDefaultBetas(profileName, model) {
  const profile = getHeaderProfile(profileName);
  const family = detectModelFamily(model);
  const familyBetas = family ? profile.betaByModel[family] || [] : [];
  return [...profile.betaBase, ...familyBetas];
}

/**
 * Generate a billing header system block matching official Claude Code format.
 * The `cch` value is a random 5-char hex string generated per call (per request).
 *
 * @param {string | undefined} profileName
 * @returns {string}
 */
export function getBillingHeaderBlock(profileName) {
  const profile = getHeaderProfile(profileName);
  const cch = randomBytes(3).toString("hex").slice(0, 5);
  return `x-anthropic-billing-header: cc_version=${profile.ccVersion}; cc_entrypoint=cli; cch=${cch};`;
}
```

---

## 注意事项

1. **动态值**：`x-stainless-retry-count` 和 `cch` 是每次请求动态生成的
2. **架构适配**：`x-stainless-arch` 应根据实际运行环境调整为 `x64` 或 `arm64`
3. **OS 适配**：`x-stainless-os` 应根据实际系统调整为 `MacOS`、`Linux` 或 `Windows`
4. **版本同步**：使用新版 CLI 时，建议重新捕获实际的 Header 值进行更新
5. **Beta 功能**：Beta 标识会随版本更新而变化，请参考官方文档获取最新列表
6. **安全性**：`anthropic-dangerous-direct-browser-access` 仅用于特定场景，普通调用不需要
