import sys
import os
import csv
import asyncio
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from scripts.google_tiktok_tag_search import google_search_tiktok_tags
from main import geturls, check_environment_variables

# Helper to deduplicate and merge URLs with date info
def merge_url_dicts(dict1, dict2):
    merged = dict(dict1)
    for url, date in dict2.items():
        if url not in merged or (date and date > merged.get(url, "")):
            merged[url] = date
    return merged

def save_merged_csv(filename, url_dict):
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['url', 'date'])
        for url, date in url_dict.items():
            writer.writerow([url, date])

def load_history_csv(filename):
    history = {}
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 2:
                    history[parts[0]] = parts[1]
    return history

async def get_archive_urls(platform, domain, api_token, account_id, database_id, timeframe):
    # Patch: Instead of writing to DB, collect URLs
    archive_urls = {}
    async def fake_write_to_cloudflare_d1(platform, session, data, api_token, account_id, database_id):
        tag = data.get('tag') or data.get('url')
        date = data.get('date')
        if tag:
            archive_urls[tag] = date
    # Monkeypatch main.write_to_cloudflare_d1
    import main
    main.write_to_cloudflare_d1 = fake_write_to_cloudflare_d1
    await geturls(platform, domain, api_token, account_id, database_id, timeframe)
    return archive_urls

def main():
    today = datetime.now().strftime('%Y-%m-%d')
    out_csv = f"merged_tiktok_tag_urls_{today}.csv"
    # 检查历史数据文件是否存在
    if os.path.exists(out_csv):
        # 检查文件大小，若超过90MB则归档
        file_size = os.path.getsize(out_csv)
        if file_size > 90 * 1024 * 1024:
            archive_name = f"{out_csv}.archive_{today}_{int(datetime.now().timestamp())}"
            os.rename(out_csv, archive_name)
            print(f"历史数据文件超过90MB，已归档为: {archive_name}")
    if not os.path.exists(out_csv):
        print("首次运行，抓取历史数据（archive）和最新数据...")
        google_urls = google_search_tiktok_tags('day', max_pages=3)
        google_url_dict = {url: today for url in google_urls}
        env = check_environment_variables()
        platform = 'tiktok'
        domain = 'tiktok.com/tag/'
        api_token = env['CLOUDFLARE_API_TOKEN']
        account_id = env['CLOUDFLARE_ACCOUNT_ID']
        database_id = env['CLOUDFLARE_D1_DATABASE_ID']
        timeframe = env['TIME_FRAME']
        archive_url_dict = asyncio.run(get_archive_urls(platform, domain, api_token, account_id, database_id, timeframe))
        merged = merge_url_dicts(google_url_dict, archive_url_dict)
        print(f"Total unique URLs: {len(merged)}")
        save_merged_csv(out_csv, merged)
    else:
        print("检测到历史数据，仅抓取最新数据...")
        google_urls = google_search_tiktok_tags('day', max_pages=3)
        today = datetime.now().strftime('%Y-%m-%d')
        google_url_dict = {url: today for url in google_urls}
        # 读取历史数据
        history = load_history_csv(out_csv)
        merged = merge_url_dicts(history, google_url_dict)
        print(f"Total unique URLs: {len(merged)}")
        save_merged_csv(out_csv, merged)
        # 计算本次新增的hashtag
        new_hashtags = set(google_url_dict.keys()) - set(archive_url_dict.keys())
        new_hashtag_file = f"new_tiktok_tags_{today}.csv"
        with open(new_hashtag_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['url', 'date'])
            for url in new_hashtags:
                writer.writerow([url, today])
    print(f"Merged URLs saved to {out_csv}")
    # 自动提交到仓库
    os.system(f'git add {out_csv}')
    os.system(f'git commit -m "update hashtag data {today}" || echo "No changes to commit"')
    os.system('git push || echo "No changes to push"')

if __name__ == "__main__":
    main()