import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import argparse
import re
import time
import csv
import os
from datetime import datetime

def build_google_search_url(prefix_url, time_range, start=0):
    base_url = "https://www.google.com/search"
    tbs = ''
    if time_range == 'day':
        tbs = 'qdr:d'
    elif time_range == 'week':
        tbs = 'qdr:w'
    elif time_range == 'month':
        tbs = 'qdr:m'
    query = f'site:{prefix_url}'
    params = {
        'q': query,
        'tbs': tbs,
        'num': 100,
        'start': start
    }
    query_string = '&'.join([f'{k}={quote(str(v))}' for k, v in params.items() if v])
    return f"{base_url}?{query_string}"

def extract_tiktok_tag_urls(html, prefix):
    soup = BeautifulSoup(html, 'html.parser')
    urls = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        match = re.search(r'(https://www\\.tiktok\\.com/tag/[^&]+)', href)
        if match:
            url = match.group(1)
            if url.startswith(prefix):
                urls.add(url)
    return list(urls)

def load_history_csv(history_file):
    history = {}
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8', newline='') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    url, date = row[0], row[1]
                    history[url] = date
    return history

def save_history_csv(history_file, history):
    with open(history_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for url, date in sorted(history.items()):
            writer.writerow([url, date])

def save_daily_new_csv(daily_file, new_urls, today):
    with open(daily_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for url in sorted(new_urls):
            writer.writerow([url, today])

def google_search_tiktok_tags(time_range, max_pages=3, delay=2):
    import yaml
    with open("scripts/config.yml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    prefix = config.get("prefix", "https://www.tiktok.com/tag/")
    all_urls = set()
    for page in range(max_pages):
        url = build_google_search_url(prefix, time_range, start=page*100)
        print(f"Fetching: {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"Failed to fetch page {page+1}, status: {resp.status_code}")
            break
        urls = extract_tiktok_tag_urls(resp.text, prefix)
        print(f"Found {len(urls)} URLs on page {page+1}")
        all_urls.update(urls)
        time.sleep(delay)
    return sorted(all_urls)

def main():
    parser = argparse.ArgumentParser(description="Google search for TikTok tag URLs by time range.")
    parser.add_argument('--range', choices=['day', 'week', 'month'], default='day', help='Time range for search')
    parser.add_argument('--pages', type=int, default=3, help='Number of Google result pages to fetch')
    parser.add_argument('--output', type=str, default='', help='Output file to save URLs (legacy, plain list)')
    parser.add_argument('--history', type=str, default='tiktok_tag_history.csv', help='CSV file to keep all found URLs with date')
    args = parser.parse_args()

    today = datetime.now().strftime('%Y-%m-%d')
    daily_file = f'new_tiktok_tags_{today}.csv'
    history_file = args.history

    # Load history
    history = load_history_csv(history_file)
    # Search
    urls = google_search_tiktok_tags(args.range, args.pages)
    print(f"\nTotal unique URLs found: {len(urls)}")
    for url in urls:
        print(url)
    # Find new URLs
    new_urls = [url for url in urls if url not in history]
    print(f"\nNew URLs found today: {len(new_urls)}")
    for url in new_urls:
        history[url] = today
    # Save updated history
    save_history_csv(history_file, history)
    print(f"History updated: {history_file}")
    # Save daily new URLs
    save_daily_new_csv(daily_file, new_urls, today)
    print(f"Today's new URLs saved: {daily_file}")
    # Optionally, save plain output if requested
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            for url in urls:
                f.write(url + '\n')
        print(f"Saved to {args.output}")

if __name__ == '__main__':
    main()