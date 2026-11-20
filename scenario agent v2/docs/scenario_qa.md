# 场景 QA 表

> 生成时间：2026-11-20 21:39:33　｜　生成脚本：`scripts/build_qa.py`
> 判定口径：`validate_scenario`（R0–R11）零问题 + `zopa.py` 可行性计算

## 一、场景总表

| 文件 | scenario_id | 类型 | 议题 | 事实 | 校验 | ZOPA | 可演示 |
|---|---|---|---|---|---|---|---|
| `backup_dst_bilateral.json` | `scn-dst-cn-us-0001` | hypothesis | 4 | 8 | ✅ 0 问题 | ✅ 有 | ✅ |
| `main_chip_controls.json` | `scn-chip-controls-0001` | hypothesis | 4 | 8 | ✅ 0 问题 | ✅ 有 | ✅ |
| `no_zopa_variant.json` | `scn-chip-controls-nozopa-0001` | hypothesis | 4 | 8 | ✅ 0 问题 | ❌ 无（I4） | — |

## 二、逐份明细

### backup_dst_bilateral.json

- **中美跨境数字服务税与平台征税安排**
- 议题数：4　事实数：8　类型：`hypothesis`
- 校验：通过（R0–R11 全部无问题）
- ZOPA：各议题均有成交区间
- 参考成交方案：I1=3.0，I2=O2，I3=0.0，I4=O3
- 效用 vs BATNA：P1 52.5>38.0✅；P2 46.67>35.0✅

### main_chip_controls.json

- **中美先进计算芯片出口管制与关键矿产交换**
- 议题数：4　事实数：8　类型：`hypothesis`
- 校验：通过（R0–R11 全部无问题）
- ZOPA：各议题均有成交区间
- 参考成交方案：I1=1150.0，I3=O2，I4=O2，I5=O2
- 效用 vs BATNA：P1 65.0>40.0✅；P2 55.83>35.0✅

### no_zopa_variant.json

- **中美先进计算芯片出口管制与关键矿产交换（无合作区间变体）**
- 议题数：4　事实数：8　类型：`hypothesis`
- 校验：通过（R0–R11 全部无问题）
- ZOPA：无合作区间，议题 I4
- 参考成交方案：I1=1150.0，I3=O2，I5=O2
- 效用 vs BATNA：P1 35.0>40.0❌；P2 31.67>35.0❌
- **设计意图**：本份为「无合作区间」变体，用于测试规则引擎的僵局判定与理性退出，**不可当作缺陷去修**。

## 三、随机议题（规则层实测）

| 输入 | 结论 | 说明 |
|---|---|---|
| 六国数字税谈判 | `needs_narrowing`（U4） | 三方以上，需收窄为双边；可用 `compile_from_narrowing` 两步走 |
| 2028 年美国大选结果会怎样 | `unsupported`（U2） | 预测未发生事件，直接拒绝 |
| 谁该为气候变暖负责 | `unsupported`（U1） | 单一二元是非题 |
| 某部长的私生活传闻 | `unsupported`（U3） | 涉及在世私人个体隐私 |

> 详细台账见 `data/scenarios/random_inputs.md`。

## 四、已知限制（交付时如实说明）

1. **真实模型链路未验证**：`DEEPSEEK_API_KEY` 未配置，`compile_scenario` 的模型调用环节从未真实跑通；
   离线链路（解析 → Schema → R0–R11 → 回喂修复）已由 `scripts/offline_check.py` 四场景验证。
2. **美国 `.gov` 外链在国内网络不可达**（`bis.gov`/`commerce.gov`/`ustr.gov`/`federalregister.gov` 均超时），
   中方来源（`gov.cn`/`mofcom.gov.cn`）正常；演示时不现场点外链。
3. **`fastapi` 未安装**：接口以标准库模式提供（`py.bat -m agent.scenario.api`），
   集成到 A 的 FastAPI 应用时使用 `create_router()`。

## 五、复现方式

```powershell
cd "D:\华为杯\Huawei\scenario agent v2"
py.bat scripts\build_qa.py        # 重新生成本表
py.bat -m pytest tests -q          # 全量测试
py.bat scripts\offline_check.py    # 离线链路验证
py.bat -m agent.scenario.api --port 8000   # 起接口
```
