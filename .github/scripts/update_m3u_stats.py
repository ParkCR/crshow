import os
import re
import sys
from datetime import datetime
from pathlib import Path
import json
from tqdm import tqdm

# 配置
STATS_DIR = Path("stats")
STATS_DIR.mkdir(exist_ok=True)

def count_m3u8_entries(m3u_content):
    """统计M3U文件中的M3U8条目数量"""
    return len([line for line in m3u_content.splitlines() 
               if line.strip() and not line.startswith("#") and line.endswith(".m3u8")])

def get_previous_stats(m3u_file, force_update=False):
    """获取上一次的统计信息"""
    if force_update:
        return None
        
    stats_file = STATS_DIR / f"{m3u_file.name}.json"
    if stats_file.exists():
        with open(stats_file, 'r') as f:
            return json.load(f)
    return None

def save_current_stats(m3u_file, count):
    """保存当前统计信息"""
    stats_file = STATS_DIR / f"{m3u_file.name}.json"
    stats = {
        "count": count,
        "timestamp": datetime.now().isoformat()
    }
    with open(stats_file, 'w') as f:
        json.dump(stats, f)
    return stats

def update_m3u_file(m3u_file, current_count, previous_count=None):
    """更新M3U文件头信息"""
    with open(m3u_file, 'r+', encoding='utf-8') as f:
        content = f.read()
        
        # 移除旧的统计信息行
        lines = [line for line in content.splitlines() 
                if not line.startswith("# STATS:")]
        
        # 计算变化量
        change = None
        if previous_count is not None:
            change = current_count - previous_count
            change_str = f"+{change}" if change > 0 else str(change)
        else:
            change_str = "N/A"
        
        # 创建新的统计信息行
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stats_line = f"# STATS: {date_str} - Total: {current_count} - Change: {change_str}"
        
        # 插入到文件开头
        lines.insert(0, stats_line)
        
        # 写回文件
        f.seek(0)
        f.write("\n".join(lines))
        f.truncate()

def process_m3u_file(m3u_file, force_update=False):
    """处理单个M3U文件"""
    with open(m3u_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    current_count = count_m3u8_entries(content)
    previous_stats = get_previous_stats(m3u_file, force_update)
    previous_count = previous_stats["count"] if previous_stats else None
    
    update_m3u_file(m3u_file, current_count, previous_count)
    save_current_stats(m3u_file, current_count)
    
    return {
        "filename": m3u_file.name,
        "current_count": current_count,
        "previous_count": previous_count,
        "change": current_count - previous_count if previous_count else None
    }

def main():
    # 检查是否强制更新
    force_update = len(sys.argv) > 1 and sys.argv[1].lower() == 'true'
    
    # 查找所有M3U文件
    m3u_files = list(Path(".").glob("**/*.m3u"))
    
    if not m3u_files:
        print("No M3U files found.")
        return
    
    print(f"Found {len(m3u_files)} M3U file(s). Processing...")
    if force_update:
        print("Force update mode - ignoring previous stats")
    
    results = []
    for m3u_file in tqdm(m3u_files, desc="Processing M3U files"):
        try:
            result = process_m3u_file(m3u_file, force_update)
            results.append(result)
        except Exception as e:
            print(f"Error processing {m3u_file}: {str(e)}")
    
    # 打印汇总信息
    print("\nSummary of changes:")
    for result in results:
        change_str = f"{result['change']:+}" if result['change'] is not None else "N/A"
        print(f"{result['filename']}: {result['current_count']} (Change: {change_str})")

if __name__ == "__main__":
    main()
