#!/usr/bin/env python3
import sys
import re
import argparse
from datetime import datetime
from pathlib import Path
import json
from tqdm import tqdm

STATS_DIR = Path("stats")
STATS_DIR.mkdir(exist_ok=True)

def count_media_entries(content):
    """统计.m3u8和.mp4链接数量"""
    stats = {"m3u8": 0, "mp4": 0, "other": 0}
    
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        # 检测媒体类型
        if re.search(r'\.m3u8(\?|$|/)', line, re.IGNORECASE):
            stats["m3u8"] += 1
        elif re.search(r'\.mp4(\?|$|/)', line, re.IGNORECASE):
            stats["mp4"] += 1
        else:
            stats["other"] += 1
            
    return stats

def get_previous_stats(file_path):
    """读取历史统计"""
    stats_file = STATS_DIR / f"{file_path.name}.json"
    try:
        return json.loads(stats_file.read_text(encoding='utf-8')) if stats_file.exists() else None
    except:
        return None

def update_file_header(file_path, current_stats, prev_stats):
    """更新文件头部统计信息"""
    content = file_path.read_text(encoding='utf-8')
    
    # 移除旧统计行
    lines = [line for line in content.splitlines() 
            if not line.strip().startswith("# STATS:")]
    
    # 计算变化量
    changes = {}
    if prev_stats:
        for k in current_stats:
            if k in prev_stats:
                changes[k] = current_stats[k] - prev_stats[k]
    
    # 生成统计行
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    stats_lines = [
        "# STATS: Media Links Summary",
        f"# Updated: {timestamp}",
        f"# M3U8: {current_stats['m3u8']} (Change: {changes.get('m3u8', 'N/A')})",
        f"# MP4: {current_stats['mp4']} (Change: {changes.get('mp4', 'N/A')})",
        "#" + "=" * 50
    ]
    
    # 保留原文件的换行符
    new_content = "\n".join(stats_lines) + "\n" + "\n".join(lines)
    if "\r\n" in content:  # Windows换行符
        new_content = new_content.replace("\n", "\r\n")
    
    file_path.write_text(new_content, encoding='utf-8')

def process_file(file_path, force_update):
    """处理单个文件"""
    try:
        content = file_path.read_text(encoding='utf-8')
        current_stats = count_media_entries(content)
        prev_stats = None if force_update else get_previous_stats(file_path)
        
        update_file_header(file_path, current_stats, prev_stats)
        
        # 保存完整统计
        stats_data = {
            **current_stats,
            "timestamp": datetime.now().isoformat(),
            "file_path": str(file_path),
            "sample_m3u8": [
                line for line in content.splitlines() 
                if re.search(r'\.m3u8', line, re.IGNORECASE)
            ][:3],
            "sample_mp4": [
                line for line in content.splitlines() 
                if re.search(r'\.mp4', line, re.IGNORECASE)
            ][:3]
        }
        
        (STATS_DIR / f"{file_path.name}.json").write_text(
            json.dumps(stats_data, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        
        return {"status": "success", "file": str(file_path), **current_stats}
    except Exception as e:
        return {"status": "failed", "file": str(file_path), "error": str(e)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-update", type=str, default="false")
    args = parser.parse_args()
    force_update = args.force_update.lower() == "true"
    
    m3u_files = list(set(Path(".").glob("**/*.m3u")))
    print(f"Found {len(m3u_files)} M3U files to process")
    
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
    
    # 打印错误报告
    failed_files = [r for r in results if r["status"] == "failed"]
    if failed_files:
        print("\nFailed to process:")
        for f in failed_files:
            print(f"  {f['file']}: {f['error']}")

if __name__ == "__main__":
    main()
