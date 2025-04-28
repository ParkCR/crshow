#!/usr/bin/env python3
import sys
import re
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
from tqdm import tqdm

STATS_DIR = Path("stats")
STATS_DIR.mkdir(exist_ok=True)

def get_local_time():
    """获取 UTC+8 时间（北京时间）"""
    utc_time = datetime.now(timezone.utc)
    return utc_time.astimezone(timezone(timedelta(hours=8)))

def count_media_entries(content):
    """统计.m3u8和.mp4链接数量"""
    stats = {"m3u8": 0, "mp4": 0, "other": 0}
    
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        # 检测媒体类型（兼容URL参数和路径）
        if re.search(r'\.m3u8(\?|$|/)', line, re.IGNORECASE):
            stats["m3u8"] += 1
        elif re.search(r'\.mp4(\?|$|/)', line, re.IGNORECASE):
            stats["mp4"] += 1
        else:
            stats["other"] += 1
            
    return stats

def get_previous_stats(file_path):
    """读取历史统计（带错误处理）"""
    stats_file = STATS_DIR / f"{file_path.name}.json"
    try:
        if stats_file.exists():
            data = json.loads(stats_file.read_text(encoding='utf-8'))
            # 验证数据格式是否包含必要字段
            if all(k in data for k in ["m3u8", "mp4"]):
                return data
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"Warning: Failed to read {stats_file}: {str(e)}")
    return None

def format_change(change):
    """格式化变化量：+2, -1, 0"""
    if change > 0:
        return f"+{change}"
    elif change < 0:
        return str(change)
    return "0"

def update_file_header(file_path, current_stats, prev_stats):
    """更新文件头部统计信息（修复旧统计未移除问题）"""
    try:
        content = file_path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        content = file_path.read_text(encoding='gbk')  # 尝试GBK编码
    
    # 移除所有旧统计行（匹配以 # STATS: 开头的行及其后续行，直到下一个非注释行）
    lines = []
    skip_until_empty_line = False
    for line in content.splitlines():
        if line.strip().startswith("# STATS:"):
            skip_until_empty_line = True
            continue
        if skip_until_empty_line:
            if not line.strip():  # 遇到空行时停止跳过
                skip_until_empty_line = False
            continue
        lines.append(line)
    
    # 计算变化量（处理prev_stats不存在或格式错误的情况）
    changes = {}
    if prev_stats and isinstance(prev_stats, dict):
        for k in ["m3u8", "mp4"]:
            if k in prev_stats and k in current_stats:
                changes[k] = current_stats[k] - prev_stats[k]
    
    # 使用本地时间（UTC+8）
    timestamp = get_local_time().strftime('%Y-%m-%d %H:%M:%S')
    
    # 生成新的统计行
    stats_lines = [
        "# STATS: Media Links Summary",
        f"# Updated: {timestamp} (UTC+8)",
        f"# M3U8: {current_stats['m3u8']} (Change: {format_change(changes.get('m3u8', 0))})",
        f"# MP4: {current_stats['mp4']} (Change: {format_change(changes.get('mp4', 0))})",
        "#" + "=" * 50,
        ""  # 添加空行分隔
    ]
    
    # 保留原文件的换行符风格
    newline = "\r\n" if "\r\n" in content else "\n"
    new_content = newline.join(stats_lines) + newline + newline.join(lines)
    file_path.write_text(new_content, encoding='utf-8')

def process_file(file_path, force_update):
    """处理单个文件（增强错误处理）"""
    try:
        # 读取内容并统计
        try:
            content = file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            content = file_path.read_text(encoding='gbk')
            
        current_stats = count_media_entries(content)
        prev_stats = None if force_update else get_previous_stats(file_path)
        
        # 更新文件头部
        update_file_header(file_path, current_stats, prev_stats)
        
        # 保存完整统计（包含示例链接）
        stats_data = {
            **current_stats,
            "timestamp": get_local_time().isoformat(),  # 使用本地时间
            "file_path": str(file_path),
            "sample_links": {
                "m3u8": [line for line in content.splitlines() 
                         if re.search(r'\.m3u8', line, re.IGNORECASE)][:3],
                "mp4": [line for line in content.splitlines() 
                        if re.search(r'\.mp4', line, re.IGNORECASE)][:3]
            }
        }
        
        (STATS_DIR / f"{file_path.name}.json").write_text(
            json.dumps(stats_data, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        
        return {"status": "success", "file": str(file_path), **current_stats}
    except Exception as e:
        return {"status": "failed", "file": str(file_path), "error": str(e)}

def main():
    parser = argparse.ArgumentParser(description="M3U/MP4 链接统计工具")
    parser.add_argument("--force-update", 
                        type=str, 
                        default="false",
                        help="强制重新统计（忽略历史数据）")
    args = parser.parse_args()
    force_update = args.force_update.lower() == "true"
    
    # 查找所有.m3u文件（排除stats目录）
    m3u_files = [f for f in Path(".").glob("**/*.m3u") 
                 if "stats" not in str(f)]
    print(f"Found {len(m3u_files)} M3U files to process")
    
    # 处理文件（带进度条）
    results = []
    for file in tqdm(m3u_files, desc="Processing files"):
        results.append(process_file(file, force_update))
    
    # 打印汇总报告
    success_files = [r for r in results if r["status"] == "success"]
    print(f"\nSuccessfully processed {len(success_files)}/{len(results)} files")
    
    print("\nMedia Type Summary:")
    print(f"  Total M3U8 links: {sum(r['m3u8'] for r in success_files)}")
    print(f"  Total MP4 links: {sum(r['mp4'] for r in success_files)}")
    print(f"  Other links: {sum(r['other'] for r in success_files)}")
    
    # 打印错误详情（如果有）
    if len(success_files) != len(results):
        print("\nFailed files:")
        for f in [r for r in results if r["status"] != "success"]:
            print(f"  {f['file']}: {f['error']}")

if __name__ == "__main__":
    main()
