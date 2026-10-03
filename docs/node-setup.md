# 配置 SnapGene 节点

节点就是装了 SnapGene、负责实际计算的那台电脑。目前**只验证过 Windows 11 + WSL2 + SnapGene 8.0.0**。macOS 和 Linux 的适配代码按官方命令行路径写好了，但还没在真机上测过，`status` 里会标成 `untested`。

## Windows 节点（已验证）

1. **装 SnapGene**，在桌面上手动打开一次：填完首次启动的姓名和邮箱对话框，完成激活或试用，然后完全关掉。只要这个对话框没处理，命令行就会一直卡在那里。
2. **装 WSL2**（例如 Ubuntu），里面要有 `python3`（3.11 以上），建议也装上 [uv](https://docs.astral.sh/uv/)。
3. **开启 OpenSSH 服务端**，把默认 shell 设为 WSL 的 bash。这样 SSH 进来就是 WSL 环境，可以通过 Windows 互操作直接调用 `SnapGene.exe`。
4. **在客户端配置密钥登录**，确认 `ssh <别名>` 不需要输入密码。

这种配置下，Windows OpenSSH 会**丢掉远程命令参数**，例如 `ssh host 'echo hi'` 什么也不会执行。本项目所有请求都以脚本的形式从标准输入发送，所以不受影响。如果你想恢复普通的 `ssh host 命令` 写法，需要自己在 Windows 的 OpenSSH 设置里调整默认 shell 的参数，本项目不会去改。

## 部署和验证

在客户端运行：

```bash
snapgene-bridge init --host <别名>
```

```bash
snapgene-bridge deploy
```

```bash
snapgene-bridge status
```

```bash
snapgene-bridge selftest
```

`deploy` 做三件事：在本地打包、经 SSH 传到节点，在节点的 `~/snapgene-bridge-node/.venv` 里安装（日志在 `~/snapgene-bridge-node/install.log`），最后返回节点状态。

如果节点上的代理环境变量指向一个没在运行的代理，安装会自动去掉代理变量再试一次。我们的 WSL 环境就遇到过这种情况：Windows 上的代理软件没开。

运行时的临时文件放在 Windows 的 `%TEMP%\snapgene-bridge\runs`，每次运行结束自动清理。需要换位置时，用 `init --scratch-dir` 指定。

## `status` 里要看的字段

| 字段 | 期望值 |
|---|---|
| `node.snapgene_found` | `true` |
| `node.snapgene_version` | 例如 `8.0.0` |
| `node.snapgene_running_pids` | `[]`，不为空就说明节点上开着 SnapGene |
| `node.scratch_writable` | `true` |
| `node.node_version` | 和客户端版本一致，不一致就重新运行 `deploy` |
| `ready` | `true` |

## 常见问题

| 现象 | 原因和处理 |
|---|---|
| `snapgene_timeout`，`dialog_text` 里有“名称、电子邮件” | 首次启动对话框没处理：在节点桌面上打开 SnapGene，填完后关掉 |
| `snapgene_timeout`，提示授权或更新 | 在桌面上处理完这个对话框再重试 |
| `snapgene_busy` | 节点上开着 SnapGene 界面，命令行不能同时运行，关掉即可 |
| `node_unreachable` | SSH 不通或要求输入密码：先手动 `ssh <别名>` 排查 |
| `node_error`，提示 not installed | 运行 `snapgene-bridge deploy` |
| 部署失败 | 查看节点上的 `~/snapgene-bridge-node/install.log` |
| `selftest` 不通过 | SnapGene 升级了或改过引物结合参数，先看 `mismatches` 再决定是否更新回归数据 |

## 安全边界

- 客户端只做两件事：经 SSH 把请求发到你配置的节点，在节点上运行本项目自己的代码。
- 节点上的程序只会启动 `SnapGene.exe --convert`。运行前发现 SnapGene 已经开着，就直接拒绝执行，不会动你的窗口。
- 超时时，只结束本次运行期间新出现的 SnapGene 进程。如果有人恰好在这几分钟里打开了 SnapGene，它也会被结束，所以节点最好专门用来跑计算。
- 不会修改系统设置、注册表或 SnapGene 的安装文件。
