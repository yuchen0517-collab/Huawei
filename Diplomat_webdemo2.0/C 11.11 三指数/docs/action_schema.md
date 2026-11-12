# 行动结构契约

引擎以成员A 的 JSON Schema 为唯一契约，字段名、枚举值和
`additionalProperties: false` 一条不改。

## 1. Schema 原文

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "外交谈判行动",
  "description": "定义一次外交谈判行动的结构。offer_patch 仅在 offer、counter_offer、conditional_exchange、final_offer 行动中允许非空，其余行动类型中必须为空对象。",
  "type": "object",
  "required": [
    "action_id", "actor", "action_type", "card_id",
    "offer_patch", "conditions", "expected_effect", "public_message"
  ],
  "additionalProperties": false,
  "properties": {
    "action_id": {"type": "string", "description": "行动的唯一编号", "minLength": 1},
    "actor": {"type": "string", "description": "行动方，使用国家代码，例如 us、cn", "minLength": 1},
    "action_type": {
      "type": "string",
      "enum": ["offer", "counter_offer", "conditional_exchange", "accept", "reject", "final_offer", "walk_away", "probe", "statement"]
    },
    "card_id": {"type": ["string", "null"], "description": "使用的策略卡编号；未使用策略卡时为 null"},
    "offer_patch": {
      "type": "object",
      "description": "需要修改的议题条款，键为议题名，值包含 option 和 note",
      "additionalProperties": {
        "type": "object",
        "required": ["option", "note"],
        "additionalProperties": false,
        "properties": {
          "option": {"type": ["string", "number"], "description": "选项或数值"},
          "note": {"type": "string", "description": "一句话说明"}
        }
      }
    },
    "conditions": {"type": "array", "description": "附加条件；没有附加条件时为空数组", "items": {"type": "string"}},
    "expected_effect": {"type": "string", "description": "一句话说明预计达到的效果"},
    "public_message": {"type": "string", "description": "公开发言全文"}
  },
  "allOf": [
    {
      "if": {
        "properties": {"action_type": {"enum": ["offer", "counter_offer", "conditional_exchange", "final_offer"]}},
        "required": ["action_type"]
      },
      "else": {"properties": {"offer_patch": {"maxProperties": 0}}}
    }
  ]
}
```

## 2. 逐字段说明

| 字段 | 引擎用途 | 说明 |
|---|---|---|
| `action_id` | 计算 + 幂等 | 进入 `seen_action_ids`；重复提交返回 `DUPLICATE_ACTION` |
| `actor` | 计算 | 必须是场景 `parties[].id`，统一小写 `cn` / `us` |
| `action_type` | 计算 | 9 个枚举值，决定报价/终局/final_offer 规则 |
| `card_id` | 只存储 | 原样写入 `public_events`，引擎不参与计算 |
| `offer_patch` | 计算 | 键为条款名，值为 `{option, note}`；合并成新方案 |
| `conditions` | 计算 + 存储 | 进入 `Offer.conditions`；审计做模糊词/可核查性检查 |
| `expected_effect` | 只存储 | 原样写入 `public_events` |
| `public_message` | 只存储 | 原样写入 `public_events`，观战页显示发言全文 |

## 3. 校验错误码

| 检查 | 错误码 |
|---|---|
| 缺任一 required 字段 | `SCHEMA_VIOLATION` |
| 出现 required 之外的字段 | `SCHEMA_VIOLATION` |
| `action_type` 不在 9 个枚举值里 | `UNKNOWN_ACTION_TYPE` |
| `card_id` 既不是 string 也不是 null | `SCHEMA_VIOLATION` |
| `offer_patch` 某值缺 `option` 或 `note` | `SCHEMA_VIOLATION` |
| `offer_patch` 某值出现额外键 | `SCHEMA_VIOLATION` |
| `conditions` 不是字符串数组 | `SCHEMA_VIOLATION` |
| 非报价类行动 `offer_patch` 非空 | `PATCH_NOT_ALLOWED` |

## 4. 建议新增：`effect_labels`（可选）

成员A 的 schema 没有离散行为标签，而 Image / Trust 必须查表。引擎在 schema
校验中允许一个可选字段（不改变 required，不影响现有实现）：

```json
"effect_labels": {
  "type": "array",
  "items": {
    "type": "object",
    "required": ["label", "magnitude"],
    "additionalProperties": false,
    "properties": {
      "label": {
        "type": "string",
        "enum": [
          "constructive_proposal", "cite_rules", "hardline_stance", "broken_promise",
          "personal_attack", "redline_provoke", "procedural", "diplomatic_reframe",
          "protect_ally", "keep_promise", "betray_ally", "vague_stance", "conditional_concession"
        ]
      },
      "magnitude": {"type": "string", "enum": ["slight", "moderate", "major"]},
      "clause": {"type": ["string", "null"]},
      "reason": {"type": "string"}
    }
  }
}
```

不加也能跑：引擎会走路径 2（`action_type` 映射 + patch 幅度）。但 `statement`
无法区分“建设性表态”和“人身攻击”，因为两者 `action_type` 都是 `statement`，
表达力会明显变弱。

`effect_labels` 的形状/枚举非法统一返回 `SCHEMA_VIOLATION`（其中的 `clause`
引用不存在条款时返回 `UNKNOWN_CLAUSE`）。