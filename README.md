# Skill Creator King

SCK 是显式选择型 Skill，可在 Codex 与 Claude Code 中使用，有三个用途：创建新的 Codex／Claude Code Skill、检查通用／WorkBuddy／Codex
Skill 的书面缺口、根据实际使用过程复盘改进已有 Skill。它帮助把需求和真实经验
变成有边界的可复用指令，用同一份问题清单支持静态检查。

当前版本为 **5.6.7**。检查能力吸收原 Agent Skill Checker，
新增 Codex 专项与统一 JSON 报告，保留创建、复盘及敏感信息预扫描。

## 快速开始

明确点名 SCK 并提出动作即可，例如「用 SCK 检查这个 Skill」。
SCK 独立完成所选流程。创建和检查交付静态合规报告；检查默认只读，修改需确认。
使用某个 Skill 后，可以说「用 SCK 复盘刚才使用这个 Skill 的过程并优化它」。
SCK 复用当前对话，先说明问题归因与具体改法，再执行已授权范围的指令改进。
只说「复盘一下，先别修改」时保持只读，不重复索取已有上下文。

## 平台与命令

### 安装

按需克隆到对应宿主的个人 Skill 目录（目标目录须不存在，运行其中一条即可）：

```bash
git clone https://github.com/Odinary-AI/skill-creator-king.git ~/.codex/skills/skill-creator-king
git clone https://github.com/Odinary-AI/skill-creator-king.git ~/.claude/skills/skill-creator-king
```

### 调用

安装后的预期调用方式：在 Codex 中点名 `$skill-creator-king`，在 Claude Code 中
使用 `/skill-creator-king`（设计用法，两端实际调用尚未逐一验证）。SCK 只应被
用户显式调用：Codex 元数据关闭自动调用，Claude Code 的描述限定显式选择。

### 检查目标与项数

检查目标支持 `auto|generic|workbuddy|codex`，与运行宿主独立；只检查请求不进入
修改。`auto` 仅在目标自带 `agents/openai.yaml` 时选 Codex，否则选 generic；可
显式指定。创建支持 Codex 与 Claude Code 目标，未指明时采用当前宿主。

| 目标 | 检查项 |
|---|---|
| Codex | 23 项通用 + 4 项 Codex 专项 |
| Claude Code | 23 项通用（未提供 Claude 专项验收） |

### 命令行静态检查

```bash
python3 "<SCK安装目录>/scripts/check_skill.py" "<目标Skill目录>" --profile auto
```

需要 Python 3.9+；YAML 使用 PyYAML 6.x。入口优先使用 `SCK_PYTHON` 指定的既有
环境，其次当前 Python 或已有 WorkBuddy Python 环境；不会联网安装依赖。
缺少解析器会保留独立检查结果并标记未评估；无效显式环境配置返回运行错误。
完整 JSON 由语义检查后按 [统一报告契约](references/report-json.md)生成；脚本 JSON
只有静态事实。默认 Markdown/full，concise 仅缩短通过项解释，不隐藏问题与限制。

## 适合谁

需要创建有书面契约的 Skill、检查结构与引用，或在日常使用后持续改进指令的用户。
只需一次性提示词、泛化代码调试或无需使用证据的任意重构时，继续使用宿主默认工具。

## 何时使用

用户必须明确选择 SCK，并同时提出创建、检查或使用后的复盘改进动作，例如：

- “用 SCK 创建一个整理项目周报的 Codex Skill。”
- “/skill-creator-king 创建一个 Claude Code Skill。”
- “请 Skill Creator King 检查这个 Skill 有哪些常见缺口。”
- “用 SCK 复盘刚才的导出过程，先分析，不改文件。”
- “用 SCK 根据这次使用发现的问题，优化这个 Skill。”

泛化的“帮我创建一个 Skill”、关于 SCK 的介绍或比较、否定使用 SCK 的请求都不
触发本流程，宿主系统可以继续使用默认 Skill Creator。用户明确选择 SCK 后，SCK
独立完成所选流程，不再把工作转交给系统 Skill Creator。

## 三个流程

创建流程：

```text
明确选择 SCK
-> 盘点已有信息
-> 分轮澄清关键缺口
-> 必要时查找公开客观资料
-> 用户确认需求确认单
-> 创建蓝图与草稿
-> 运行共同问题清单
-> 交付 Skill 与静态合规报告
```

需求未达到创建条件时不会急于生成文件。联网只能补充公开、客观事实，不能替用户
决定目标、权限、隐私边界或偏好；采用的来源及其设计影响会写入需求确认单。

检查流程：

```text
明确选择 SCK
-> 只读检查目标
-> 脚本事实检查 + LLM 书面缺口检查
-> 静态合规报告
-> 存在必修或建议项时询问用户是否修改
-> 用户确认具体变更后才做最小修改并复查
```

没有必修或建议项时直接结束，不额外询问。修改前只把受影响的既有普通文件复制到系统
临时目录。成功后清理临时副本；失败时
恢复原文件并删除本次新建路径。默认不建立永久备份，只有用户明确要求并指定位置时
才创建长期备份。

创建新 Skill 时同样记录本次新建路径；草稿或自检失败只清理这些新路径，绝不覆盖
或删除原有目标。清理失败时报告剩余路径，不把半成品写成成功交付。

复盘改进流程：

```text
明确选择 SCK，并指定本次使用的 Skill
-> 复用已有对话和脱敏证据，扫描后读取当前 Skill
-> 比较预期与实际，核对原因及当前版本是否仍有问题
-> 提炼可复用的改进，展示具体文件、修改、影响和授权
-> 有授权才改；无需修改或证据不足也可结束
-> 复查改动及相关契约，交付简短复盘报告
-> 下次相关使用时观察效果，再按需调用 SCK
```

明确要求「复盘并优化」已经授权原目的和权限内的最小指令改动，不再逐项重复询问。
改变用途、扩大触发或权限、破坏输出兼容性、删除/重命名文件需要相应明确授权。
只分析不写入的复盘可以给建议；临时偏好不会自动变成永久规则。

复盘可以调整步骤、方法切换、前提、输出和失败处理，保留仍有效的行为。它不执行
目标 Skill，也不修改可执行代码；真正的脚本缺陷会提供证据和调试交接建议。
只取得另一会话的名称并不代表能看到内容；缺证据时只询问必要的脱敏片段。
默认不保存日志或复盘历史，不自动监控下次使用。

修改前建立受影响文件的临时回滚副本，并检查没有并发变更；新引入静态缺口或写入
失败时只撤回本次改动，不覆盖其他编辑。复盘后的相关复查不等于全包静态合规，
实际效果待后续使用验证。详见 [复盘指南](references/reflect.md)。

## 检查范围

查什么——一份共同问题清单，两类条目：

- `SCK-Sxx`：脚本可重复证明的结构事实：目录、UTF-8、frontmatter、名称、
  Markdown 引用、路径边界、符号链接、孤立资源等。
- `SCK-Lxx`：需要 LLM 理解文字的书面契约：目标与触发、输入、流程、输出、权限、
  副作用、失败行为、跨文档一致性、README 自足、指令去重等。

谁来查——脚本与 LLM 分工。脚本只产出确定性结构事实；LLM 独立核对所有实际本地
引用和语义适用，即使脚本没有提醒、目录里没有资源。确认缺失的必需资源属于必修项，
不随链接写法降级；脚本提取的候选经上下文证明只是示例时，可记录证据后判为不适用，
但真实缺失或越界不能改判为有效。条目细则与边界情况见
[共同问题清单](references/common-issues.md)。

不做什么——SCK 不运行、导入或调试目标 Skill，不测试其依赖、网络服务、性能或
实际功能，也不提供安全认证、质量分数或 marketplace 就绪结论。创建和完整检查
报告必须说明：

`运行行为：未评估，超出 SCK 范围。`

复盘报告分别说明历史证据、当前修改与相关复查，并明确未执行目标 Skill；
修改效果待后续使用验证。旧记录不能证明新版本已经有效。

## 标准输出

重要阶段使用需求确认单、创建蓝图、静态合规报告、修改确认单和复盘改进报告。
完整静态报告用中文逐条可数全部 23 项（Codex 另加 4 项），结论行自带覆盖计数，非通过项前置，
通过块收尾。日常复盘只交付有证据的问题、改进及复查结果，不要求完整审计。字段、判词、
颜色和展示细则统一见 [标准输出](references/report.md)，
不在此维护另一份细则。

## 运行包

SCK 区分两个集合：

**运行包**——两个宿主安装同一套内容，复盘指南和 Codex 专项按需加载：

```text
SKILL.md
templates/SKILL.template.md
references/create.md
references/reflect.md
references/common-issues.md
references/report.md
scripts/validate_skill.py
scripts/check_skill.py
scripts/render_report.py
references/profile-codex.md
references/report-json.md
agents/openai.yaml
```

另附 README、LICENSE 与 NOTICE 供使用和追溯。`tests/`、开发设计与
迁移证据仅保留在源码项目，不随安装包分发。静态检查不等于宿主验收。

校验器需要 Python 3.9+；完整 YAML 检查另外需要同一
Python 环境中的 PyYAML 6.x，使用安全加载器，不执行 YAML 对象。

没有 PyYAML 或遇到安全加载器不支持的构造时，JSON 的 `not_assessed` 会说明未评估
条目，`passed` 为 false；独立的路径检查继续进行。这是检查能力不足，不是 Skill
格式错误。SCK 不自动安装依赖；需要时使用已有合适环境，或取得用户授权后安装：

```bash
python3 -m pip install 'PyYAML>=6,<7'
```

## 静态验证

在已具备 Python 3.9+ 和 PyYAML 6.x 的环境中，运行
`python3 scripts/validate_skill.py . --operation check --profile codex`。
这只检查包的静态事实，不证明 Claude Code 或 Codex 的实际调用行为。
