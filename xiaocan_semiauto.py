import json
import logging
import asyncio
import pandas as pd
from mitmproxy import http
from tabulate import tabulate


logging.basicConfig(level=logging.INFO)

TARGET_URL = "gw.xiaocantech.com/rpc"
TARGET_METHODS = [
    "FusionService.GetFeedPromotions", 
    "SilkwormRcsService.MeituanShangjinGetPoiList"
]
CAPTURED_DATA = []

def parse_distance(dist_str: str) -> float:
    """将距离字符串解析为千米 (例如 '3.3km' -> 3.3, '800m' -> 0.8)"""
    if not dist_str:
        return 0.0
    dist_str = str(dist_str).lower().strip()
    try:
        if dist_str.endswith('km'):
            return float(dist_str[:-2])
        elif dist_str.endswith('m'):
            return float(dist_str[:-1]) / 1000.0
        else:
            return float(dist_str)
    except ValueError:
        return 0.0

def process_method_1(data: dict):
    """处理 FusionService.GetFeedPromotions 的响应"""
    items = data.get("feed_items", [])
    for item in items:
        # 为了与方法二统一格式以及更易读，将分转换为元
        order_money = item.get("order_money", 0) / 100.0
        user_rebate = item.get("user_rebate", 0) / 100.0
        
        CAPTURED_DATA.append({
            "name": item.get("store", {}).get("name", ""),
            "order_money": order_money,
            "user_rebate": user_rebate,
            "left_number": item.get("left_number", 0),
            "distance": item.get("distance", 0) / 1000.0,
            "real_cost": order_money - user_rebate,
            "ratio": user_rebate / order_money
        })

def process_method_2(data: dict):
    """处理 SilkwormRcsService.MeituanShangjinGetPoiList 的响应"""
    items = data.get("poi_list", [])
    for item in items:
        name = item.get("name", "")
        dist_str = item.get("delivery_distance", "0m")
        distance = parse_distance(dist_str)
        
        activities = item.get("plan_activity_info_list", [])
        for act in activities:
            inventory = act.get("inventory", 0)
            if inventory == 0:
                continue
            
            # 最高可返还金额转为元
            max_commission = act.get("max_commission", 0) / 100.0
            
            ratio_val = act.get("ratio", 0) / 10000.0
            real_cost = (max_commission / ratio_val) - max_commission
            
            CAPTURED_DATA.append({
                "name": name,
                "distance": distance,
                "ratio": ratio_val,
                "max_commission": max_commission,
                "left_number": inventory,
                "real_cost": real_cost
            })

async def async_process_response(method: str, text: str):
    """异步处理响应体，避免阻塞 mitmproxy 主线程"""
    try:
        data = json.loads(text)
        if method == TARGET_METHODS[0]:
            process_method_1(data)
        elif method == TARGET_METHODS[1]:
            process_method_2(data)
    except Exception as e:
        logging.error(f"处理 {method} 数据时出错: {e}")

def response(flow: http.HTTPFlow):
    """mitmproxy 的响应拦截入口"""
    if TARGET_URL not in flow.request.pretty_url:
        return
    actual_method = flow.request.headers.get("methodName", "")
    if actual_method not in TARGET_METHODS:
        return

    text = flow.response.get_text()
    if text:
        # 开启并发任务，不阻塞当前数据流的处理
        asyncio.create_task(async_process_response(actual_method, text))

def done():
    """mitmproxy 退出时的钩子函数，Ctrl+C 后执行"""
    if not CAPTURED_DATA:
        logging.info("本次没有采集到任何数据。")
        return
    
    try:
        df = pd.DataFrame(CAPTURED_DATA)
        # 删行
        df = df.drop_duplicates()
        df = df[(df['distance'] <= 4.0) & 
                (df['left_number'] > 0) ]
        df = df[df['name'].notna() & (df['name'].astype(str).str.strip() != '')]
        #   name相同时的去重: 保留 ratio 最高的, 若相等则保留real_cost 最低的 (通过全局排序后去重，避免 groupby 把列变为index)
        df = df.sort_values(by=['ratio', 'real_cost'], ascending=[False, True], na_position='last')
        df = df.drop_duplicates(subset=['name'], keep='first')

        # 行、列排序
        #   把列 max_commission 合并到列 user_rebate
        df['user_rebate'] = df['user_rebate'].fillna(df.get('max_commission', pd.NA))
        df = df[['distance', 'real_cost', 'order_money', 'user_rebate', 'ratio', 'left_number', 'name'] ]
        df = df.sort_values(by=['real_cost', 'ratio'], ascending=[True, False]).reset_index(drop=True)

        # 美化
        df['distance'] = df['distance'].apply(lambda x: f"{float(x):.1f}k" if pd.notna(x) else "")
        df.columns = ['距离', '实掏', '低消', '返还', '返率', '余量', '店名']
        df.to_csv("today_results.csv", index=False, encoding="utf-8-sig")
        print(tabulate(df, headers='keys', tablefmt='grid', showindex=False, floatfmt=".2f"))
    except ImportError:
        logging.error("无法生成 DataFrame：未安装 pandas 或 tabulate。")
        print("\n原始采集数据：")
        print(json.dumps(CAPTURED_DATA, ensure_ascii=False, indent=2))
    except Exception as e:
        logging.exception(f"生成 DataFrame 时出错: {e}")