# SnapGene Bridge

让 AI（Claude Code 等）直接调用你自己装的 SnapGene，计算引物的结合位点和 Tm，自动设计 PCR 和克隆引物，结果写回 SnapGene 原生的 `.dna` 文件。

报给你的 Tm 是 **SnapGene 自己算的数**，和你在 SnapGene 界面上看到的一致，不是 primer3 或其他计算器的近似值。

## 它怎么工作

SnapGene 没有插件接口，也没有公开 API。但它的官方命令行 `--convert` 在导入 SnapGene 风格的 GenBank 时，会用自己的算法给每条引物计算结合位点和 Tm。本项目把这一步当成黑盒计算器：

```text
Claude Code / 终端（Mac）
  snapgene-bridge  生成候选引物 → 打分选对 → 写文件和订购表
        │ SSH（请求走标准输入，base64 编码）
        ▼
SnapGene 节点（装了 SnapGene 的电脑，例如 Windows + WSL）
  候选写成 GenBank → SnapGene.exe --convert（一批一个进程）→ 从 .dna 读回位点和 Tm
```

- 本地只负责出候选（primer3 和最近邻估算），**最终数字一律以 SnapGene 为准**。
- 不注入、不修改、不反编译 SnapGene，只用官方命令行和文件格式。
- 序列只在你的电脑和你自己的节点之间传输，不经过任何第三方服务。

## 实测（SnapGene 8.0.0，Windows 11 + WSL2）

| 项目 | 结果 |
|---|---|
| 一批 1000 条引物 | 约 4.8 秒，几乎全是 SnapGene 启动开销 |
| 位点和 Tm | 与 SnapGene 界面一致，Tm 为整数 |
| 回归自检 | 208 条引物的位点和 Tm 全部逐条一致 |
| pUC19 AmpR 亚克隆引物 | 一次 `clone` 约 20 秒，两条 Tm 都是 60°C |

## 准备

**这台电脑（客户端）**：Python 3.11 以上，以及 [uv](https://docs.astral.sh/uv/)。

**SnapGene 节点**（可以就是另一台办公电脑），详见 [docs/node-setup.md](docs/node-setup.md)：

1. 装好 SnapGene，并在桌面上**手动打开一次**，填完首次启动的姓名和邮箱对话框、完成激活，然后**关掉**。
2. 能用 SSH 密钥免密登录，登录后是 POSIX shell。Windows 上目前只验证过把 OpenSSH 默认 shell 设为 WSL bash 的配置。
3. 节点上有 `python3`（3.11 以上），最好也装上 `uv`。

## 安装和配置

```bash
git clone <本仓库> snapgene-bridge && cd snapgene-bridge
uv tool install --editable .
```

装好后有两个等价命令：`snapgene-bridge` 和简写 `sgb`。

```bash
snapgene-bridge init --host my-node
```

`my-node` 换成 `~/.ssh/config` 里节点的别名，配置写到 `~/.config/snapgene-bridge/config.toml`。

```bash
snapgene-bridge deploy
```

把本仓库打包装到节点的 `~/snapgene-bridge-node` 下。每次更新代码后都要重新部署一次。

```bash
snapgene-bridge status
```

`"ready": true` 表示节点可用。

```bash
snapgene-bridge selftest --quick
```

用存下的 SnapGene 8.0.0 结果做回归。全部通过说明节点上的 SnapGene 和预期一致。

## 常用命令

所有命令都输出一个 JSON 对象。**命令里的位置用 SnapGene 和 GenBank 的写法：从 1 开始、两端都包含**，例如 `1626..2486`。环状质粒可以跨原点，例如 `2600..120`。

**查 SnapGene 算的 Tm 和结合位点（含脱靶）：**

```bash
sgb check plasmid.dna --primer F1=GCTCTTGATCCGGCAAACAAACC --primer M13F=GTAAAACGACGGCCAGT
```

**克隆引物**：引物两端固定在插入片段的两头，可以加 5′ 尾巴，长度按 SnapGene 的 Tm 选：

```bash
sgb clone pUC19.gb --region 1626..2486 --strand - --tail-f GCGCTAGC --tail-r GCCTCGAG --name bla --output bla.dna --order bla_order.tsv
```

也可以用 `--feature AmpR` 直接按特征名取区间和方向。

**PCR 引物**：产物要完整包含目标区段，由 primer3 出候选、SnapGene 打分：

```bash
sgb pcr plasmid.dna --feature AmpR --product-size 900-1600 --output amp.dna
```

常用参数：

- `--target-tm 60`：目标 SnapGene Tm。
- `--max-dtm 2`：一对引物允许的 Tm 差。
- `--length 18-28`：退火段长度范围。
- `--offtarget-max-tm 45`：任何其他位点的 Tm 达到这个值就淘汰。
- `--offline`：没有节点时改用本地估算。结果会标成 `estimate:nn`，下单前要用节点复核。

## 看懂输出

- **`tm_standard`**：`snapgene-8.0.0` 表示数字来自 SnapGene，`estimate:nn` 表示本地估算。
- **坐标**：`start`/`end` 从 0 开始、左闭右开；`location` 是和 SnapGene 一样的 `a..b` 写法。
- **`sites`**：SnapGene 报告的所有结合位点。`components` 列出哪些碱基配上了模板哪一段，5′ 尾巴、错配和凸起都会体现出来。
- **`imported: false`**：SnapGene 认为这条引物没有 Tm 达到 40°C 的结合位点，也就是它默认的结合门槛。
- **`--output x.dna`**：在有节点时，文件由 SnapGene 自己生成，里面的引物位点和 Tm 就是它算的。原文件的特征会带过去，但颜色、注释和历史记录不会。
- **`--output x.gb`**：写出 SnapGene 风格的 GenBank，用 SnapGene 打开时会自动计算引物位点。

## 限制和注意

- **跑命令时，节点上不能开着 SnapGene 界面**，这是官方命令行的限制。开着时会返回 `snapgene_busy`。
- 命令行碰到任何对话框都会卡住，比如首次启动、授权或更新提示。超时后会返回 `snapgene_timeout`，并附上读到的对话框文字。
- SnapGene 只给出整数 Tm，算的是退火部分，不含 5′ 尾巴。它的条件是 50 mM Na+、不含 Mg2+，和聚合酶厂家的计算器不同。按 SnapGene 的说法，Phusion 或 Q5 的退火温度一般比它显示的 Tm 高 6 到 12°C。
- “GenBank 里有 `Exported ... from SnapGene` 这一行才会把 `primer_bind` 当引物导入”，是在 8.0.0 上实测出来的行为，不是官方文档承诺。**升级 SnapGene 后先跑 `selftest`。**
- 授权：如果是绑定单台电脑的授权，SnapGene 条款写明不得远程访问。用之前确认授权类型。

## 出错时怎么办

| `error.code` | 含义和处理 |
|---|---|
| `node_not_configured` | 没配置节点：运行 `init --host`，或者加 `--offline` |
| `node_unreachable` | SSH 不通：先确认 `ssh <host>` 能免密登录 |
| `node_error` | 节点上没装或版本旧：运行 `deploy` |
| `snapgene_busy` | 节点上开着 SnapGene：关掉 |
| `snapgene_timeout` | 有隐藏对话框：看 `details.dialog_text`，在节点桌面上处理一次 |
| `snapgene_not_found` | 找不到 SnapGene：用 `init --snapgene-exe` 指定路径 |
| `no_valid_design` | 没有满足条件的引物对：按 `details` 放宽长度、Tm 差或脱靶阈值 |

## 开发

```bash
uv run --group dev python -m pytest
```

单元测试不需要 SnapGene。

```bash
uv run --group dev python -m pytest -m node
```

连真实节点跑端到端测试。

代码结构：

- `src/snapgene_bridge/cli.py`：命令和 JSON 输出格式。
- `design/`：PCR 和克隆引物的候选生成与打分。
- `oracle.py`：SnapGene 黑盒接口和离线估算。
- `transport.py`、`deploy.py`：SSH 通道和部署。
- `node/`：在节点上运行，负责驱动 SnapGene 命令行和解析结果。
- `snapgene_genbank.py`：写 SnapGene 风格的 GenBank。
- `selftest_data/`：SnapGene 8.0.0 的回归数据。

设计取舍见 [docs/decisions](docs/decisions)，实测依据见 [docs/research/snapgene-platform.md](docs/research/snapgene-platform.md)，输出格式见 [docs/json-contract.md](docs/json-contract.md)。
