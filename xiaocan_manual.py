import requests
import json

class XiaoCanSpider:
    def __init__(self, raw_headers_str):
        self.url = "https://gw.xiaocantech.com/rpc"
        self.headers = self._parse_headers(raw_headers_str)

    def _parse_headers(self, raw_str):
        """将从 Fiddler 粘贴的原始 Header 字符串转换为字典"""
        header_dict = {}
        for line in raw_str.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                header_dict[key.strip()] = value.strip()
        return header_dict

    def fetch_and_parse(self, payload):
        """执行请求并提取指定字段"""
        try:
            response = requests.post(self.url, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            feed_items = data.get("feed_items", [])
            for item in feed_items:
                # 提取目标字段
                extracted = {
                    "distance": item.get("distance"),
                    "meituan_shop_url": item.get("meituan_shop_url"),
                    "order_money": item.get("order_money"),
                    "user_rebate": item.get("user_rebate")
                }
                # 紧凑格式打印：一行一个条目
                print(json.dumps(extracted, ensure_ascii=False))
                
        except Exception as e:
            print(f"发生错误: {e}")

# =================使用说明=================

# 1. 直接从 Fiddler 的 Inspectors -> Raw 窗口复制全部 Header 粘贴到下面
RAW_HEADERS = """
POST https://gw.xiaocantech.com/rpc HTTP/1.1
Host: gw.xiaocantech.com
Connection: keep-alive
Content-Length: 96
appid: 20
x-Vayne: 490465
x-Annie: XC
xweb_xhr: 1
x-Teemo: 556479056
X-Ashe: 30be7b6599375d588de7a5cb44df324b
X-Model: microsoft microsoft
Content-Type: application/json
X-Nami: 60a3556479056f1f
X-Platform: mini
X-Version: 3.15.9.10
serverName: SilkwormRcs
x-Sivir: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJVc2VySWQiOjQ5MDQ2NSwiZXhwIjoxNzgwODMyNzc3fQ.OKMVOdwpYsNlkpXyc-j5XlNj8EjzDevHlu4Pzl-S_ZQ
methodName: SilkwormRcsService.MeituanShangjinGetPoiList
x-City: 130681
X-Garen: 1777692719740
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf254186b) XWEB/19481
version: 3.15.9.10
Accept: */*
Sec-Fetch-Site: cross-site
Sec-Fetch-Mode: cors
Sec-Fetch-Dest: empty
Referer: https://servicewechat.com/wx52ae177248081591/740/page-frame.html
Accept-Encoding: gzip, deflate, br
Accept-Language: zh-CN,zh;q=0.9
"""

# 2. 对应的请求 Body (根据需要修改 offset 翻页)
PAYLOAD = {"lat":39.485291,"lng":115.974388,"silk_id":556479056,"page_pv_id":"","sort_type":1,"app_id":20}

# 3. 运行
spider = XiaoCanSpider(RAW_HEADERS)
spider.fetch_and_parse(PAYLOAD)