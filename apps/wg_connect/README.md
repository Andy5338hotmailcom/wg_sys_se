# wg_connect —— 连接中心

> 立项日期：2026-11-19
> 状态：**WiFi 与蓝牙首版已实现；网络诊断待实现**
> 目录：`apps/wg_connect/`
> 范围：所有"连接"相关的事——网络状态、WiFi、蓝牙、基础诊断。名字就叫连接中心，不在名字上特指某一种连接。

---

## 一、这个软件是干什么的

桌面里所有「连不连得上」的事，都从这个窗口处理。四块：

1. 网络状态：通不通、什么类型、延迟多少
2. WiFi：扫描、连接（**有本地服务时**能做，没有时只能引导）
3. 蓝牙：适配器状态、已配对设备、扫描配对（BLE 直连需 https）
4. 诊断：出问题时看一眼环境，把排查信息复制出来

它是连接类事务的总入口，不是某一个协议的专用面板——所以标题、图标、菜单名都不出现"WiFi"或"网络"这类具体字样。

---

## 二、边界（先写死，省得后面反复争）

这套系统是网页。下面这些在纯浏览器里**做不到**，不是没写好，是接口不存在：

| 做不到的 | 说明 |
| --- | --- |
| 连 WiFi、断 WiFi、扫 WiFi 列表 | 浏览器没有连接网络的接口，`navigator.connection` 只读 |
| 读系统网络配置（IP、网关、DNS） | 无接口 |
| 打开系统"网络设置"页面 | 跳 `ms-settings:` 会被浏览器拦 |
| 开关蓝牙、列已配对设备、管理经典蓝牙设备 | 网页蓝牙只认 BLE（GATT）；需本地 Python 服务调用 Windows API |

**两种形态都要是完整的**：有本地服务时该有的功能都有；没有时每个入口都要灰掉并写清原因，不能点了没反应。

详细原因见 `体验增强计划.md` 第三章「这套系统做不到的事」。

---

## 三、能力探测（决定走哪条路）

启动时请求一次：

```
GET http://127.0.0.1:8554/wg/ping
→ { ok: true, version: "1.2", caps: ["wifi", "bluetooth"] }
```

- loopback / `file://` 来源的探测超时为 1.5 秒；非 loopback 网页延长至 60 秒，以等待 Windows 首次来源授权弹窗。连接被拒绝或本机服务未启动时仍会尽快进入降级模式
- 能力探测由 `apps/wg_connect` 内的页面脚本负责，连接中心不依赖 `desktop.js` 的全局状态
- 总览页面只在应用内部检查本地服务，并由 WiFi/蓝牙模块共享一次性令牌
- 前端若跑在 https（如 GitHub Pages），后端必须回 `Access-Control-Allow-Private-Network: true`

---

## 四、功能需求

### 4.1 网络状态卡片（P0，两种形态都做）

- 判断是否真的联网：`navigator.onLine` **加上**一次真实请求（取 `ico.svg` 之类的小文件），两个都过才算通。只用 `onLine` 会在"路由器连上了但没外网"时误报。
- 显示：通/不通、推测的连接类型（`navigator.connection.type` / `effectiveType`，拿不到写"未知"）、当前页面是否安全上下文。
- 不通时：显示引导（Win+I → 网络和 Internet → WLAN，附图），加「重新检测」按钮。
- 检测要有加载态，不能点完没反应。

### 4.2 WiFi 面板（P1，需 `wifi` 能力）

- **有本地服务**：列表显示 SSID、信号强度、加密方式、是否已连接；选中 → 输密码 → 连接 → 刷新状态。信号强度用 4 格图标，不要只写数字。
- **无本地服务**：整块灰掉，写"需要本地服务才能扫描和连接"，给跳转说明，不给假按钮。同时顶部服务状态条右侧出现「下载本地服务」按钮，指向 `app/windows/0.1.1.exe`（下载名 `wg_connect_0.1.1.exe`）；服务恢复后这个按钮自动消失。换新版本时只需改两处 `href` 与 `download` 文件名。
- 支持手动刷新；扫描有耗时，要有"正在扫描"状态与 15 秒超时。

### 4.3 蓝牙面板（P1）

按环境分三种情况，界面必须明确当前是哪一种：

| 环境 | 能做到 |
| --- | --- |
| 有本地服务 + `bluetooth` 能力 | 适配器状态、已配对设备、主动扫描、配对、移除 |
| 无本地服务 + https / localhost | 只能用 Web Bluetooth 连 **BLE 设备**（手环、灯泡、传感器） |
| 无本地服务 + `file://` | 完全不可用，灰掉并写明原因 |

- Web Bluetooth 必须由用户点击触发，不能在页面加载时自动扫。
- 本地服务负责 Windows 蓝牙设备枚举、配对与移除；配对确认由 Windows 处理。
- 无本地服务时不伪装成完整的系统蓝牙管理，只提供浏览器支持时的临时 BLE GATT 连接。
- 已配对设备不显示"已连接/未连接"——读不到，别编。
- 空列表写"还没有配对设备"，不留白。

### 4.4 基础诊断（P2）

- 延迟测试：对同一小文件请求 3 次取平均，显示毫秒数与失败次数。
- 环境摘要：是否 https、`onLine`、`effectiveType`、有无本地服务、各能力项。
- 「复制诊断信息」输出纯文本，方便贴到反馈里。

---

## 五、界面要求

- 总览页面：`white.html` / `black.html`，直接显示 WiFi 与蓝牙面板，不提供打开分界面的按钮。
- 独立调用：`wifi.html` 与 `bluetooth.html` 会按 `WG_color` 打开相应主题的单项页面；也可直接调用 `white.html?panel=wifi`、`black.html?panel=bluetooth` 等路径。
- 图标：`apps/wg_connect/ico.svg`，风格与 `apps/welcome/ico.svg` 一致。图标不画 WiFi 扇形或蓝牙符号，避免把范围画窄。
- 布局：卡片式，自上而下「状态 → WiFi → 蓝牙 → 诊断」；窄屏单列，不横向滚动。
- 状态色：可用绿、不可用灰、进行中蓝、失败红；灰掉的区块要标注原因，不要只降低透明度。
- 每个异步操作都有进行中 / 成功 / 失败（可重试）三态。
- 黑白两版正文结构一致，只差配色。

## 六、数据与键名

- 只读系统键：`WG_color`、`wg_lang`。
- 本应用自己的键一律加前缀：`wg_connect_last_ssid`、`wg_connect_last_device`。
- **WiFi 密码绝不落 localStorage**，也不落 sessionStorage，只在内存里传给本地服务，传完即弃。
- 不新增全局配置键；要加先在 `apps/reg` 里开专属小节，按归属约定只由一处写。

## 七、本地服务接口约定

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/wg/ping` | 能力探测 |
| GET | `/wg/wifi/status` | 无线网卡状态与 WiFi 开关状态 |
| GET | `/wg/wifi/scan` | 扫描附近 WiFi |
| POST | `/wg/wifi/connect` | `{ssid, password}` 连接 |
| POST | `/wg/wifi/disconnect` | `{ssid}` 只断开指定的当前连接，保留无线网卡和已保存配置 |
| POST | `/wg/wifi/toggle` | `{enabled: true/false}` 开启或关闭系统 WiFi |
| GET | `/wg/bluetooth/status` | 适配器状态 |
| GET | `/wg/bluetooth/devices` | 已配对设备 |
| GET | `/wg/bluetooth/scan` | 主动扫描附近设备 |
| POST | `/wg/bluetooth/pair` | `{address}` 配对 |
| POST | `/wg/bluetooth/unpair` | `{address}` 移除配对 |

安全控制：只绑定 `127.0.0.1`，每次操作使用一次性 token，并校验 `Origin`。loopback 和显式配置来源直接允许；首次遇到新的有效 HTTP(S) 来源时，Windows 本机 Python 服务会弹出系统确认框，显示完整来源及其将访问 WiFi/蓝牙控制能力。选择“是”只在服务本次运行期间授权该来源；选择“否”返回 403，并在服务退出前不重复弹窗。未授权来源不能读写控制接口。授权弹窗期间页面的短超时可能先显示服务不可用；批准后点“重新检测服务器”即可重试。

## 八、本地化

- `apps/wg_connect/lang.js`，与 `apps/reg`、`apps/wgver` 同构：页面只留 `data-wg-i18n="key"`，按 `wg_lang` 取值，取不到回落 `zh-cn`。
- `en-us` 词条等英文仓库对应页面同步时从其原文取，不自行编写。
- 状态词（已连接 / 扫描中 / 不可用）也要 key 化。

## 九、验收清单

- [ ] 断网时打开，状态卡片在 3 秒内给出"未连接"，引导与「重新检测」可用
- [ ] 恢复网络后点「重新检测」，状态自动转为已连接，无需刷新页面
- [ ] 无本地服务时，WiFi 与蓝牙面板显示为不可用并写明原因，无假按钮
- [ ] loopback 页面上的 `/wg/ping` 无响应时，1.5 秒内降级，界面不卡
- [ ] `file://` 打开时 BLE 区块显示"当前打开方式不支持"
- [ ] WiFi 密码不出现在任何 storage 键里
- [ ] 已配对列表不出现"已连接"这种读不到的状态
- [ ] 扫描有进行中状态，15 秒超时后给出"没找到设备"而不是一直转圈
- [ ] 黑白两版在 `WG_color` 切换后显示正确
- [ ] 所有文案都能在 `lang.js` 找到 key，页面无裸中文

## 十、明确不做的

- 不做通用网页代理（绕 iframe 禁嵌），原因见计划文档第三章第 6 节
- 不做 BLE GATT 服务特征读写；无本地服务时只提供浏览器临时连接
- 不做测速（既耗流量又受运营商影响，意义不大）
- 不做系统级网络配置修改（静态 IP、DNS）
- 不伪造"已连接 WiFi"的成功态

---

## 十一、独立调用（非默认应用）

连接中心不登记在 `desktop.js` 的 `DEFAULT_APPS` 中。需要时由调用方单独打开：

- 总览：`apps/wg_connect/white.html` 或 `black.html`
- WiFi：`apps/wg_connect/wifi.html`
- 蓝牙：`apps/wg_connect/bluetooth.html`

应用页面自行探测本地 Python 服务，不依赖桌面全局能力对象。Windows 本地服务使用系统 API 管理 WiFi 和蓝牙；配对新蓝牙设备时可能需要在 Windows 确认。若系统拒绝操作，请检查 Windows 权限与适配器状态。网络诊断仍未实现。

### 首版启动

1. 在 Windows 安装 Python 3.10+，并在项目根目录运行：

   ```powershell
   python apps\wg_connect\server.py
   ```

   服务只监听 `127.0.0.1:8554`，不使用第三方 Python 依赖。
2. 推荐通过本地网页服务打开桌面（例如项目根目录运行 `python -m http.server 8000`，再访问 `http://127.0.0.1:8000`）。支持的浏览器也可以直接用 `file://` 打开。
3. WiFi 密码只通过用户点击发出的连接请求短暂传递，不写入网页存储。为支持 Windows 后续自动重连，Windows WLAN 服务可能保存已添加的网络配置。

服务默认允许 loopback 网页来源和 `https://andy5338hotmailcom.github.io`。其他网站首次请求会弹出来源授权框；也可显式添加完整来源地址以免提示，例如：

```powershell
python apps\wg_connect\server.py --allow-origin https://example.com
```

服务默认允许 `Origin: null`，所以可直接用 `file://` 打开。如果不希望本机 HTML 文件访问 WiFi 服务，可这样启动：

```powershell
python apps\wg_connect\server.py --deny-file-origin
```

**安全提示：** 浏览器不给本地文件来源提供可区分的路径，所有 `file://` 页面都会以 `Origin: null` 呈现。默认放行后，本机其他 HTML 文件也可能请求此服务；如不信任本机 HTML 文件，请使用 `--deny-file-origin`。来源授权弹窗只对合法的 HTTP(S) 来源显示，不会放行 `Origin: null`；批准的来源只保存到服务退出。该确认框由 Python 服务所在的 Windows 登录会话显示，需在交互式桌面运行服务。页面中的“重新检测服务器”按钮可在服务启动后再次探测。蓝牙配对/移除需要 Windows 蓝牙服务与适配器。没有本地服务时，页面仅在 HTTPS 或 localhost 等安全上下文、且浏览器支持 Web Bluetooth 的情况下提供用户主动触发的 BLE 临时连接；`file://` 下不支持此回退。Web Bluetooth 不能代替经典蓝牙设备管理。
