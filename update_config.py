import argparse
import json
import re
from pathlib import Path

def extract_podcast_names(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    podcast_names = set()
    
    # 综合正则表达式，匹配所有可能出现的播客名称
    # 考虑到Word转文本后格式可能不规则，使用更宽松的匹配
    # 匹配“节目名称”列下的播客名，以及“同业基金粉丝增长情况”下的播客名
    
    # 匹配表格中以播客名称开头的行
    # 播客名称通常是2-15个汉字，后面可能跟着特定的词语（基金、小酒馆等）
    # 后面跟着至少一个空格和非空白字符（表示有后续数据，是表格行）
    pattern_table_name = re.compile(r'^\s*([\u4e00-\u9fa5]{2,15}(?:基金|小酒馆|谈钱|同享|托出|宴宾客|下班|面基|涨声|钱话|求真|财经列车|经济学|漫步|钱程|Talk|嘉讲|连篇|方程式|播客|规划局|直播间|访谈录|聊天局|同行|心动|论市)?)\s+\S+', re.MULTILINE)
    matches = pattern_table_name.findall(content)
    for name in matches:
        podcast_names.add(name.strip())

    # 针对一些可能被遗漏的、或者格式不完全符合表格模式的名称进行补充
    # 这些名称可能出现在标题或不规则的行中
    specific_names = [
        "大方谈钱", "中欧基金", "有富同享", "人间钱话", "深度求真", "德邦基金财经列车",
        "茶水间经济学", "随基漫步", "莫问钱程", "泰客Talk", "时间嘉讲", "财话连篇",
        "养基方程式", "好朋友的播客", "钱途规划局", "好朋友的直播间", "投资心法·基金访谈录",
        "投资心得·基金聊天局", "与财同行", "鹏然心动", "基金经理一周论市",
        "和盘托出", "知行小酒馆", "起朱楼宴宾客", "三点下班", "面基", "听懂涨声"
    ]
    for name in specific_names:
        if name in content:
            podcast_names.add(name)

    # 移除不需要的字符串
    unwanted_names = {"公募基金官方播客", "其他财经类播客", "节目名称"}
    podcast_names = podcast_names - unwanted_names

    return sorted(list(podcast_names))

def update_config(config_path, new_podcast_names):
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    existing_podcasts = {p['name'] for p in config['podcasts']}
    
    for name in new_podcast_names:
        if name not in existing_podcasts:
            # 尝试根据名称判断分类
            category = "公募基金" if "基金" in name or name in ["大方谈钱", "有富同享", "人间钱话", "深度求真", "德邦基金财经列车", "茶水间经济学", "随基漫步", "莫问钱程", "泰客Talk", "时间嘉讲", "财话连篇", "养基方程式", "好朋友的播客", "钱途规划局", "好朋友的直播间", "投资心法·基金访谈录", "投资心得·基金聊天局", "与财同行", "鹏然心动", "基金经理一周论市"] else "泛财经"
            config['podcasts'].append({
                "name": name,
                "podcast_id": "", # 待补充
                "category": category,
                "enabled": True
            })
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update config.json with new podcast names.")
    parser.add_argument(
        "--names",
        default="podcast_list_v2.txt",
        help="Path to the podcast names source file (default: podcast_list_v2.txt)",
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to config.json (default: config.json)",
    )
    args = parser.parse_args()

    names_path = Path(args.names).expanduser()
    config_path = Path(args.config).expanduser()

    podcast_names = extract_podcast_names(str(names_path))
    print("Extracted podcast names:", podcast_names)
    update_config(str(config_path), podcast_names)
    print("Config updated with new podcast names.")
