<p align="center">
  <img src="../assets/banner.svg" alt="SnapGene Bridge" width="100%"/>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/SnapGene-8.0.0%20verified-0B6FB8?style=flat-square" alt="SnapGene 8.0.0 verified"/>
  <img src="https://img.shields.io/badge/node-Windows%20%2B%20WSL2-555555?style=flat-square" alt="Node: Windows + WSL2"/>
  <img src="https://img.shields.io/badge/selftest-208%2F208-2E8B57?style=flat-square" alt="selftest 208/208"/>
  <img src="https://img.shields.io/badge/license-Apache--2.0-green?style=flat-square" alt="License: Apache-2.0"/>
  <img src="https://img.shields.io/badge/status-alpha-orange?style=flat-square" alt="Status: alpha"/>
</p>

<p align="center">
  <a href="../README.md">English</a> | 简体中文
</p>

面向 AI 智能体的 **SnapGene 引物设计桥接层**。智能体在本地设计 PCR 和克隆引物；所有结合位点和 Tm 都由 SnapGene 通过官方命令行计算。SnapGene 可以在本机运行，也可以在通过 SSH 访问的实验室电脑上运行。

### 为什么用 SnapGene Bridge？

**1. 数字直接来自 SnapGene**，不需要再对照第二套 Tm 标准。
- 结合位点、Tm 和比对细节直接取自 SnapGene 的导入结果，与界面显示一致。
- 错配、凸起和脱靶位点按 SnapGene 的判定报告。
- `selftest` 会把 208 条引物与记录下来的 SnapGene 8.0.0 结果逐条比对，防止结果在不知不觉中变化。

**2. 远程 SnapGene 节点**，SnapGene 留在持有授权的实验室电脑上。
- 一批任务只启动一次 SnapGene，1000 条引物约 5 秒。
- 开箱支持 Windows OpenSSH + WSL：请求走标准输入，响应用 JSON 分帧返回。
- SnapGene 界面开着时拒绝运行；遇到隐藏对话框会报告内容；运行结束后自动清理。

**3. 为编程智能体设计**，例如 Claude Code、Codex、Cursor。
- 每条命令输出一个 JSON 对象，错误码稳定，并附带处理建议。
- 自带智能体技能（`skills/snapgene/`），智能体可以直接按流程操作。
- 输出由 SnapGene 生成的 `.dna` 文件和引物订购表，供人工复核。

> **如果你是 AI 智能体**，请先阅读 [`AGENTS.md`](../AGENTS.md) 和 [`skills/snapgene/SKILL.md`](../skills/snapgene/SKILL.md)。

## 选择流程

| 需求 | 命令 | 前提 |
|---|---|---|
| 查询已有引物在 SnapGene 中的 Tm 和结合位点 | `sgb check` | SnapGene 节点 |
| 亚克隆插入片段，可加酶切位点或同源臂尾巴 | `sgb clone` | SnapGene 节点 |
| 扩增一个区段，用于筛选或鉴定 PCR | `sgb pcr` | SnapGene 节点 |
| 不连 SnapGene 先试用 | 加 `--offline` | 无；数值为本地估算，标记为 `estimate:nn` |
| 在另一台电脑上运行 SnapGene | 先 `sgb init --host`，再 `sgb deploy` | SSH 密钥登录，节点已安装 SnapGene |

## 快速开始

```bash
# 0. 获取源码
git clone https://github.com/Ryuwang3/snapgene-bridge.git
cd snapgene-bridge

# 1. 安装命令行（提供 `snapgene-bridge` 和简写 `sgb`）
uv tool install --editable .

# 2. 指定 SnapGene 节点（~/.ssh/config 中的别名）
sgb init --host my-node

# 3. 部署节点端并验证
sgb deploy
sgb status             # 应显示 "ready": true
sgb selftest --quick   # 与记录的 SnapGene 8.0.0 结果比对
```

首次使用前，需要在节点上手动打开一次 SnapGene，完成首次启动对话框和授权激活，然后关闭。SnapGene 命令行遇到任何对话框都会卡住。详见[节点配置](../docs/node-setup.md)。

### 示例：从 pUC19 亚克隆 AmpR

```bash
sgb clone tests/data/pUC19_L09137.gb --region 1626..2486 --strand - \
    --tail-f GCGCTAGC --tail-r GCCTCGAG --name bla \
    --output bla.dna --order bla_order.tsv
```

| 引物 | 序列（5'→3'） | SnapGene Tm |
|---|---|---|
| `bla_F26` | `GCGCTAGCATGAGTATTCAACATTTCCGTGTCGC` | 60 °C |
| `bla_R24` | `GCCTCGAGTTACCAATGCTTAATCAGTGAGGC` | 60 °C |

- SnapGene 在一个批次中评估了全部 42 种长度的候选，耗时 4.7 秒。
- `bla.dna` 由 SnapGene 生成，打开后显示的就是同样的数值。
- `bla_R24` 尾巴上有两个碱基恰好与模板配对，SnapGene 按 26 个碱基计算退火。自行重写的 Tm 模型发现不了这一点。

## 命令参考

所有命令都支持 `--help`。位置采用 SnapGene 的写法：从 1 开始计数、两端包含，例如 `a..b`。环状分子上的区段可以跨过原点，例如 `2600..120`。

| 命令 | 作用 |
|---|---|
| **节点** | |
| `init --host HOST` | 写入 `~/.config/snapgene-bridge/config.toml` |
| `deploy` | 打包并安装到节点的 `~/snapgene-bridge-node` |
| `status` | 报告本地依赖、节点状态和版本是否一致；全部可用时 `ready` 为 true |
| `selftest [--quick]` | 重跑 208 条引物，与记录的 SnapGene 8.0.0 结果比对 |
| **分析** | |
| `check FILE --primer NAME=SEQ` | 报告 SnapGene 给出的结合位点、Tm、比对组成和脱靶位点 |
| **设计** | |
| `clone FILE`，加 `--region a..b` 或 `--feature NAME` | 引物固定在插入片段两端，可加 5' 尾巴，长度按 SnapGene Tm 选择 |
| `pcr FILE`，加 `--target a..b` 或 `--feature NAME` | 由 primer3 提出侧翼引物对，再按 SnapGene 结果重新排序 |
| **文件** | |
| `read FILE`、`validate FILE` | 把 `.dna`、GenBank 或 FASTA 解析成统一的 JSON |
| `open FILE` | 用本地桌面程序打开文件 |

设计参数：

| 参数 | 默认值 | 含义 |
|---|---|---|
| `--target-tm` | 60 | 目标 SnapGene Tm |
| `--max-dtm` | 2 | 一对引物之间允许的最大 Tm 差 |
| `--length MIN-MAX` | `clone` 为 16-36，`pcr` 为 18-28 | 退火段长度范围 |
| `--offtarget-max-tm` | 45 | 任一其他位点的 Tm 达到该值即淘汰候选 |
| `--output NEW.dna` 或 `NEW.gb` | 无 | 输出带所选引物的模板文件 |
| `--order NEW.tsv` | 无 | 输出制表符分隔的订购表 |
| `--offline` | 关闭 | 用本地估算代替 SnapGene |

## 把技能交给编程智能体

```bash
mkdir -p ~/.claude/skills
ln -s "$(pwd)/skills/snapgene" ~/.claude/skills/snapgene-bridge
```

Codex 等智能体会读取 [`AGENTS.md`](../AGENTS.md)。如果智能体支持技能目录，把它指向 `skills/` 即可。

## 架构

<p align="center">
  <img src="../assets/architecture.svg" alt="架构" width="100%"/>
</p>

- **设计层**（`design/`）负责生成候选、筛选并给引物对排序。`clone` 会尝试插入片段两端的每一种退火长度；`pcr` 使用 primer3 的候选，盐浓度设置贴近 SnapGene。
- **Oracle**（`oracle.py`）有两种实现：`SnapGeneOracle` 向节点请求结果；`EstimateOracle` 是离线备用方案，做精确的 3' 端锚定搜索，再加最近邻估算。
- **传输层**（`transport.py`）把 base64 编码的请求放进 POSIX 脚本，经 SSH 标准输入发送；响应是分帧的 JSON，不受登录横幅或结尾 `logout` 的干扰。
- **节点**（`node/`）先加锁，SnapGene 开着时拒绝运行；然后写出 GenBank-SnapGene 文件，每批只运行一次 `SnapGene --convert`，再用 [sgffp](https://github.com/merv1n34k/sgffp) 解析每个 `.dna`。

> **SnapGene 如何计算。** 只有当 GenBank 文件带有 SnapGene 自己写的 `JOURNAL   Exported … from SnapGene` 行时，SnapGene 才会把 `primer_bind` 特征导入为引物，并计算它们的位点和 Tm。见 [`snapgene_genbank.py`](../src/snapgene_bridge/snapgene_genbank.py) 和 [ADR 0002](../docs/decisions/0002-snapgene-cli-oracle.md)。

## 基准测试

SnapGene 8.0.0，运行在 Windows 11 + WSL2 上；客户端为 macOS。

| 测试项 | 结果 |
|---|---|
| 一批 1000 条引物 | 4.8 秒，主要是 SnapGene 启动时间 |
| 20 个文件，每个 50 条引物 | 6.7 秒 |
| `selftest`，208 条引物 | 位点和 Tm 全部一致 |
| pUC19 AmpR 的 `clone`，端到端 | 约 17 秒，含 `.dna` 输出 |
| 教科书最近邻模型与 SnapGene 对比 | 2162 个位点中 61% 的整数 Tm 完全一致，平均误差 0.51 °C |

## 对比

| | snapgene-bridge | SnapGene 界面 | 基于 primer3 的脚本 | 托管式克隆 MCP 服务 |
|---|---|---|---|---|
| Tm 与 SnapGene 一致 | ✅ | ✅ | ❌ 模型不同 | ❌ 模型不同 |
| 可被编程智能体调用 | ✅ 命令行、JSON、技能 | ❌ | ✅ | ✅ |
| 序列只在自己的机器之间传输 | ✅ | ✅ | ✅ | ❌ 需要上传 |
| 写出 SnapGene `.dna` | ✅ 由 SnapGene 生成 | ✅ | ❌ | ❌ 只能读取（截至 2026-10） |
| 批量评估 | ✅ 5 秒约 1000 条 | ❌ 需手动操作 | ✅ | ✅ |

## 限制

- 运行命令时，节点上的 SnapGene 界面必须关闭，否则返回 `snapgene_busy`。
- 任何模态对话框都会让命令行卡住。超时后返回 `snapgene_timeout`，并附上对话框文字。
- SnapGene 的 Tm 是整数，只计算退火部分，不含 5' 尾巴；条件为 50 mM Na+、不含 Mg2+。使用 Phusion 或 Q5 时，SnapGene 建议退火温度比它显示的 Tm 高 6 到 12 °C。
- `JOURNAL` 触发条件是在 SnapGene 8.0.0 上观察到的行为，不是官方文档承诺的接口。每次升级 SnapGene 后都应运行 `selftest`。
- 目前只验证过 Windows + WSL 节点，macOS 和 Linux 后端尚未测试。
- 请确认 SnapGene 授权类型：绑定单台电脑的授权禁止远程访问。

## 文档

- [节点配置与故障排查](../docs/node-setup.md)
- [架构](../docs/architecture.md)、[JSON 约定](../docs/json-contract.md)、[决策记录](../docs/decisions)、[路线图](../docs/roadmap.md)
- [已验证的 SnapGene 行为](../docs/research/snapgene-platform.md)

## 开发

```bash
uv run --group dev python -m pytest            # 单元测试，不需要 SnapGene
uv run --group dev python -m pytest -m node    # 连接已配置的节点做端到端测试
uv run --group dev ruff check src tests
```

## 致谢

- [sgffp](https://github.com/merv1n34k/sgffp)：读取 SnapGene `.dna` 文件。
- [primer3-py](https://github.com/libnano/primer3-py) 和 [Biopython](https://biopython.org)：生成候选、做本地估算。
- [virtuoso-bridge-lite](https://github.com/Arcadia-1/virtuoso-bridge-lite)：本项目沿用的智能体桥接模式。

## 许可证

Apache-2.0。SnapGene 是其所有者的商标。本项目与 SnapGene 的开发方没有关联，也未获其背书。
