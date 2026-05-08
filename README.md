微信内部爬取

# 获取数据

## 抓包法

### 用Fiddler抓包

-  搭建Fiddler抓包环境
    - 安装并配置证书
        * 下载安装 [Fiddler Classic](https://www.telerik.com/fiddler/fiddler-classic)。
        * **开启 HTTPS 抓包：** `Tools` -> `Options` -> `HTTPS` -> 勾选 `Decrypt HTTPS traffic`。
        * **关键一步：** 点击右侧的 `Actions` -> `Trust Root Certificate`，在 Win11 的弹窗中点击“是”。如果不装证书，你只能看到一堆 `Tunnel to...`。
        * ⚠️ 注意: 任务完成后，在 Fiddler 中点击 `Actions -> Remove Interception Certificates` 彻底清理。
    - 绕过 Win11 系统代理限制  (❇️ 经测试, 我开了clash的`TUN模式`, skip该步骤似乎没有影响)  
        Win11 的微信 PC 版小程序有时不走系统代理。如果 Fiddler 抓不到小程序的包：
        * 使用 **强制代理工具：** 下载 `Proxifier`。
        * 设置一条规则：将 `WeChatAppEx.exe`（小程序的进程名）的所有流量强制转发到 `127.0.0.1:8888`（Fiddler 默认端口）。
    - 启动抓包: 打开 Fiddler, 让其常驻进行监测.  
- 锁定目标session
    > 这里以"爬取`小蚕`小程序首页的外卖商品列表"为例. 

    - 重开`目标小程序窗口`, Fiddler的list里就能抓到许多session
    - 点击`Find`高亮搜索关键词`xiaocan`
    - 逐个检索, 锁定符合条件的session:
        - host是: `gw.xiaocantech.com`
        - url是: `rpc`
        - response body size很大, 且形如: `{"status":{"code":0},"feed_items":[{"store":{"id":1871102,"name":"店铺名","longitude":115.996341,"latitude":39.485831,"address":"地址"`

### 获取response body

最简单且笨的方法是直接复制session里的response body来分析.   
下面介绍另一种: `解密request-header`
- 研究抓到的session里request的header和body, 破解其动态的`加密字段`, 就能直接模拟请求来获取响应了.
- ⚠️ 难点: 需要深入研究 MD5 算法, 逆向分析, 而 `脱壳 -> 搜索关键字符串（如 X-Ashe）-> 定位加密函数 -> 用 Python 改写或直接用 execjs 调用`这个流程对逆向小白来说很陌生, 很难.  

```http
POST https://gw.xiaocantech.com/rpc HTTP/1.1
Host: gw.xiaocantech.com
Connection: keep-alive
Content-Length: 108
appid: 20
x-Vayne: 490465
x-Annie: XC
xweb_xhr: 1
x-Teemo: 556479056
X-Ashe: 2857b2128f39b6d3c85762319a6af95a
X-Model: microsoft microsoft
Content-Type: application/json
X-Nami: 578c5564790561fb
X-Platform: mini
X-Version: 3.15.9.10
serverName: SilkwormFusion
x-Sivir: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJVc2VySWQiOjQ5MDQ2NSwiZXhwIjoxNzgwODMyNzc3fQ.OKMVOdwpYsNlkpXyc-j5XlNj8EjzDevHlu4Pzl-S_ZQ
methodName: FusionService.GetFeedPromotions
x-City: 130681
X-Garen: 1777687169803
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf254186b) XWEB/19481
version: 3.15.9.10
Accept: */*
Sec-Fetch-Site: cross-site
Sec-Fetch-Mode: cors
Sec-Fetch-Dest: empty
Referer: https://servicewechat.com/wx52ae177248081591/740/page-frame.html
Accept-Encoding: gzip, deflate, br
Accept-Language: zh-CN,zh;q=0.9

{"silk_id":556479056,"lon":115.974388,"lat":39.485291,"number":20,"offset":0,"sort":0,"scene":1,"app_id":20}
```
重点条目:
- [慢动态] x-Sivir (希维尔) —— 身份令牌 (JWT)：  
    这一串 eyJhbGci... 是标准 JWT Token。我简单解密了一下，它包含你的 UserId: 490465。  
    风险： 它的 exp（过期时间）是动态的。一旦这个 Token 过期，你的 curl 就会返回 401 或权限错误，需要重新从 Fiddler 抓取。

- [动态] X-Ashe (艾希) —— 请求签名 (Signature)：
    这串 07a48cf0... 是 MD5 签名。它大概率是将请求体（Body）加上一个“密钥”进行哈希计算得出的。  
    风险： 如果你修改了 Body 里的 offset（翻页）或 silk_id，但没有对应修改 X-Ashe，服务器会认为请求被篡改。

- [动态] X-Garen (盖伦) —— 毫秒级时间戳。服务器可能会校验这个时间，防止“重放攻击”。
- [动态] X-Nami (娜美) —— 
- methodName：这个字段非常重要，它告诉后台具体执行哪个函数。当前的 GetFeedPromotions 显然是获取促销/商品列表。

## 半自动嗅探法
> 半自动嗅探（Mitm-Sniffing）, 上面`抓包法`的进阶版.

优点: 不必费心研究请求头的`加密字段`, 零逆向成本.  
注意:
- 首次运行, 要在浏览器访问 `http://mitm.it`。下载并安装 Windows 版证书，存入 “受信任的根证书颁发机构”
    - url里有非常细致的装配教程
    - 这步和 Fiddler 是一样的，没这步你解密不了 HTTPS

### mitmproxy嗅探步骤

- 安装: `uv tool install mitmproxy`, 它像命令行版本的fiddler, 将得到3个工具: mitmproxy, mitmdump, mitmweb
- 把你想做的逻辑写入脚本里的`def response(flow: http.HTTPFlow)`
- 启动: `mitmdump -s xiaocan_semiauto.py --mode upstream:http://127.0.0.1:7897`
    - 默认下, mitmproxy服务静默在`8080`运行.  
    - `mode`参数实现了`链式代理`, 是为了不影响系统内已经运行的代理服务(如 clash).  
- 设置win11代理: 系统设置 -> 网络和 internet -> 代理 -> 手动启用 `127.0.0.1:8080`
- 刷新小程序页面, 并持续滚动商品列表. 

### 用于mitmdump的脚本设计

该脚本 (`xiaocan_semiauto.py`) 采用 `mitmproxy` 提供的钩子机制，实现了对小蚕小程序数据的自动化采集、清洗与优雅展示：

1.  **精准拦截**：通过 `response` 钩子锁定目标域名 `gw.xiaocantech.com/rpc`，并根据 `methodName` 请求头精准过滤 `GetFeedPromotions` (外卖列表) 和 `MeituanShangjinGetPoiList` (赏金列表) 两类关键数据。
2.  **异步非阻塞**：利用 `asyncio` 将解析逻辑从主线程剥离，确保在高频滚动翻页时不会导致拦截延迟或卡顿。
3.  **数据标准化**：
    *   统一将不同接口的字段映射到一套数据模型中。
    *   自动处理单位换算（分 -> 元，m -> km）。
    *   计算关键指标：`real_cost` (实掏 = 低消 - 返还) 和 `ratio` (返率)。
4.  **智能化后处理** (基于 `done` 钩子，按 `Ctrl+C` 退出时触发)：
    *   **深度去重**：自动剔除重复项；针对同名店铺，仅保留返还比例最高且实掏成本最低的最佳方案。
    *   **多维过滤**：默认过滤掉 4km 以外、余量为 0 或名称为空的无效数据。
    *   **优雅展示**：使用 `pandas` 进行多列组合排序（实掏由低到高，返率由高到低），并通过 `tabulate` 在终端渲染精美的表格。
    *   **持久化**：自动生成 `today_results.csv`（UTF-8-BOM 编码），方便直接用 Excel 打开查阅。



## RPC注入法

也常被称为“桥接（Briding）”或“内部钩子（In-App Hooking）”。  
核心逻辑：既然我算不出你的加密算法，那我就直接住在你的“身体”里，命令你帮我发请求。

### 方法1-(deprecated)控制台直接调用法

> 目前业内在 4.x 上开启调试通常需要修改微信的 dll 文件（俗称“打补丁”），这对普通用户来说门槛极高且容易导致微信闪退。

如果你已经通过 -remote-debugging-port 开启了微信小程序的开发者工具界面：

寻找入口： 在 Sources 面板里，寻找那个包含 FusionService.GetFeedPromotions 字样的 JS 文件。

定位对象： 找到发送请求的全局对象（通常是某个 app、Service 或 request 封装类）。

注入代码： 在 Console 中直接写一个循环，不断调用该函数。

### 方法2-Websocket 桥接

（真正意义上的 RPC）  
你在小程序内部注入一段代码，让小程序连接到一个你本地运行的 Python 服务（通过 Websocket）。

- Python 端： 建立一个 Websocket Server，像一个指挥官。
- 小程序端（注入）： 监听指挥官的指令。当指挥官说 next，小程序就执行一次请求，并将结果通过 Websocket 传回给 Python。

优势： 你可以用 Python 完美地控制抓取节奏、处理数据并保存到数据库，而小程序沦为了你的“代练”。

### 方法3-Frida (动态插桩)

这是移动端逆向的神。它可以直接在内存级别修改微信的运行逻辑。

做法： 编写一个 Frida 脚本（JavaScript），挂载到 WeChatAppEx.exe 进程上。

效果： 它可以拦截所有的 HTTPS 发送函数，在参数进入加密流程之前把它们替换掉，或者直接调用内部的发送逻辑。

### 方法4-SeimiAgent或Playwright注入

如果你更习惯用自动化框架：

Playwright： 可以连接到微信开启的调试端口。

逻辑：
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
# 连接到微信小程序已经开启的 9222 调试端口
browser = p.chromium.connect_over_cdp("http://localhost:9222")
# 找到小程序的页面对象
page = browser.contexts[0].pages[0]
# 注入并执行 JS，获取结果
data = page.evaluate("window.someInternalRequestFunction(payload)")
print(data)
```

## UI自动化法

工具： Airtest 或 Appium。
原理： 模拟人的手指滑动。脚本每滑一次，就自动识别屏幕上的文字，或者直接从微信的内存里读取数据。



# 项目常态化使用

- 手动
    1. windows系统设置 -> 网络和 internet -> 代理 -> 手动启用 `127.0.0.1:8080`
    2. 运行 `cd C:\Users\raymo\rays\repos\_me\scraper-xiaocan; .\.venv\Scripts\activate.ps1; mitmdump -s xiaocan_semiauto.py --mode upstream:http://127.0.0.1:7897`
        - ⚠️ 260506: 无法找到`系统代理关闭 & clash是TUN模式`时抓不到包的bug, 因此使用方法回退到`关闭clash + 运行时不用'--mode'参数`.
    3. 打开微信小程序，进入小蚕，持续滚动商品列表，直到你觉得数据够了。
    4. `Ctrl+C`终止命令, 目标表格将打印在命令行里.
- 自动: 将手动方法封装成[pwsh函数](https://github.com/draymski/utils101/blob/main/src/utils101/shell_kit/general_funcs.ps1)中的`Invoke-Xcan`.
