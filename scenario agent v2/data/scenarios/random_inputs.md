# 随机议题输入与实测记录

> 用途：Day 7「随机议题演示输入测试」的固定台账，也是 Day 6 `scenario_qa.md` 的原始数据。
> 判定口径：三档结论 `direct` / `needs_narrowing` / `unsupported`。
> 版本：v1.0　　最后修改：2026-11-13

---

## 一、怎么跑

```powershell
cd "D:\华为杯\Huawei\scenario agent v2"
.\py.bat -c "from agent.scenario.compiler import compile_scenario; r=compile_scenario('中美先进计算芯片的许可门槛与审批时限'); print('ok=',r.ok,'attempts=',r.attempts)"
```

`unsupported` 与 `needs_narrowing` 两类**不调用模型**（`attempts=0`），不配 Key 也能验证。

---

## 二、七个输入

| # | 输入议题 | 预期 | 理由 | 实测 | 日期 | 可演示 |
|---|---|---|---|---|---|---|
| S1 | 中美先进计算芯片的许可门槛与审批时限 | `direct` | 双边、4 个可量化条款、有交换空间 | 待测（需 Key） | | ☐ |
| S2 | 两国跨境河流的年度取水量分配与生态补偿 | `direct` | 纯假设推演，结构清晰 | 待测（需 Key） | | ☐ |
| S3 | 中美科技竞争 | `needs_narrowing` | 太宽泛，拆不出可报价条款 | 待测（需 Key） | | ☐ |
| S4 | 六国数字税谈判 | `needs_narrowing`（U4） | 三方以上，应收窄为双边 | `needs_narrowing` ✅ | 11-13 | ☐ |
| S5 | 2028 年美国大选结果会怎样 | `unsupported`（U2） | 要求预测未发生事件 | `unsupported` ✅ | 11-13 | ☐ |
| S6 | 谁该为气候变暖负责 | `unsupported`（U1） | 单一二元是非题 | `unsupported` ✅ | 11-13 | ☐ |
| S7 | 某部长的私生活传闻 | `unsupported`（U3） | 涉及在世私人个体隐私 | `unsupported` ✅ | 11-13 | ☐ |

S4–S7 已通过规则层实测，不花 token。S1–S3 需要真实 Key。

---

## 三、每个输入跑 3 遍

同一输入 3 次结果不一致的，标记**不可演示**——不要赌现场运气。

| # | 第 1 遍 | 第 2 遍 | 第 3 遍 | 一致性 | 处理 |
|---|---|---|---|---|---|
| S1 | | | | | |
| S2 | | | | | |
| S3 | | | | | |

判定：
- 三遍相同且都能生成 → 可作演示备选
- 三遍相同但偶尔失败 → 可用，但必须预录
- 三遍不一致 → 从演示清单删除，或先修 Prompt

---

## 四、失败时的兜底文案（给 D）

| 情况 | 文案 | 行为 |
|---|---|---|
| `needs_narrowing` | 「这个议题太大，建议先聚焦到具体条款。可以点下面任一方向：」+ 2–3 个按钮 | 保留原场景，不覆盖当前进度 |
| `unsupported`（U1） | 「这个议题只能立场表态，无法拆成可报价的条款。试试『X 的适用门槛与审查程序』这类角度。」 | 不生成空壳报价板 |
| `unsupported`（U2） | 「我们不预测真实结果。可以切换为『假设推演』模式。」 | 给「切换为假设推演」按钮 |
| 超时 / 接口失败 | 「生成超时，已保留你当前的场景。可以重试，或改用固定场景。」 | 保留原场景 + 重试按钮 |
| 校验连续失败 | 「这次生成没通过自检，已丢弃。请稍后重试或换一个议题。」 | **绝不返回半成品** |

---

## 五、多边议题的收窄路径

`needs_narrowing` 之后用户点选方向，走 `compile_from_narrowing()`：

```python
from agent.scenario.compiler import compile_from_narrowing

r = compile_from_narrowing(
    "六国数字税",
    "中美两国数字服务税税率差",     # 用户点选的方向
)
```

成功后自动补一条假设：

> A_narrow_3：本场景为「六国数字税」的双边简化，仅保留最具交换结构的两个主体。

---

## 六、记录规范

- 每次保存：输入原文、`verdict`、`attempts`、命中规则、耗时、报错
- 成功案例留档 `data/scenarios/generated/`（不进 git）
- 失败的 `raw_output` 存 `proof/`，这是「一次校验失败」的过程证据
