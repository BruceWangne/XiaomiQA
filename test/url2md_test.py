#!/usr/bin/env python3
"""
网页转Markdown脚本
功能：输入网页地址，保留内容格式和图片，保存为Markdown文件
"""

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import html2text
import requests
from bs4 import BeautifulSoup


class WebpageToMarkdown:
    def __init__(self, url, output_dir="output", filename=None):
        self.url = url
        self.output_dir = Path(output_dir)
        self.images_dir = self.output_dir / "images"
        self.filename = filename
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

        # 创建输出目录
        self.output_dir.mkdir(exist_ok=True)
        self.images_dir.mkdir(exist_ok=True)

        # 配置html2text
        self.h = html2text.HTML2Text()
        self.h.ignore_links = False
        self.h.ignore_images = False
        self.h.ignore_emphasis = False
        self.h.body_width = 0  # 不自动换行
        self.h.protect_links = True
        self.h.unicode_snob = True  # 使用unicode字符

    def download_image(self, img_url, img_name=None):
        """下载图片并返回本地路径"""
        try:
            # 处理相对URL
            img_url = urljoin(self.url, img_url)

            # 获取图片
            response = self.session.get(img_url, timeout=10)
            response.raise_for_status()

            # 生成文件名
            if not img_name:
                # 从URL生成唯一文件名
                url_hash = hashlib.md5(img_url.encode()).hexdigest()[:8]
                ext = os.path.splitext(urlparse(img_url).path)[1] or '.jpg'
                img_name = f"img_{url_hash}{ext}"

            # 保存图片
            img_path = self.images_dir / img_name
            with open(img_path, 'wb') as f:
                f.write(response.content)

            # 返回相对路径
            return f"images/{img_name}"

        except Exception as e:
            print(f"下载图片失败 {img_url}: {e}")
            return img_url

    def process_images(self, soup):
        """处理HTML中的图片，下载并更新路径"""
        images = soup.find_all('img')

        for img in images:
            # 检查多个可能的图片属性
            src = img.get('src') or img.get('data-src') or img.get('data-actualsrc')
            if not src:
                continue

            # 下载图片
            local_path = self.download_image(src)

            # 更新图片路径
            img['src'] = local_path

            # 如果有alt文本，保留它
            if not img.get('alt'):
                img['alt'] = os.path.basename(local_path)

        return soup

    def clean_html(self, soup):
        """清理HTML，移除不需要的元素"""
        # 移除script和style标签
        for tag in soup(['script', 'style', 'meta', 'link']):
            tag.decompose()

        # 移除注释
        for comment in soup.find_all(text=lambda text: isinstance(text, str) and '<!--' in text):
            comment.extract()

        return soup

    def convert_to_markdown(self):
        """将网页转换为Markdown"""
        print(f"正在获取网页: {self.url}")

        try:
            # 获取网页内容
            response = self.session.get(self.url, timeout=30)
            response.raise_for_status()

            # 强制使用UTF-8编码
            response.encoding = 'utf-8'

            # 解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # 获取标题
            title = soup.find('title')
            title_text = title.text.strip() if title else "webpage"

            # 清理HTML
            soup = self.clean_html(soup)

            # 处理图片
            print("正在下载图片...")
            soup = self.process_images(soup)

            # 获取主要内容
            # 尝试找到主要内容区域
            main_content = None
            for selector in ['main', 'article', '[role="main"]', '.content', '#content', '.post', '.entry-content']:
                main_content = soup.select_one(selector)
                if main_content:
                    break

            # 如果没有找到特定内容区域，使用body
            if not main_content:
                main_content = soup.find('body') or soup

            # 转换为Markdown
            print("正在转换为Markdown...")
            markdown_content = self.h.handle(str(main_content))

            # 后处理Markdown内容
            markdown_content = self.post_process_markdown(markdown_content)

            # 添加元信息
            metadata = f"""---
title: {title_text}
source: {self.url}
date: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

"""

            # 组合最终内容
            final_content = metadata + markdown_content

            # 生成输出文件名（保留中文字符）
            if self.filename:
                safe_title = self.filename
            else:
                safe_title = re.sub(r'[<>:"/\\|?*]', '_', title_text)[:50]
                if not safe_title.strip():
                    safe_title = f"webpage_{hash(self.url) % 10000}"
            output_file = self.output_dir / f"{safe_title}.md"

            # 保存Markdown文件
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(final_content)

            print(f"转换完成！文件保存在: {output_file}")
            print(f"图片保存在: {self.images_dir}")

            return output_file

        except Exception as e:
            print(f"转换失败: {e}")
            raise

    def post_process_markdown(self, content):
        """后处理Markdown内容"""
        # 修复多余的空行
        content = re.sub(r'\n{3,}', '\n\n', content)

        # 修复图片链接格式
        content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'![\1](\2)', content)

        # 确保标题前后有空行
        content = re.sub(r'(\n)?(\#{1,6}\s+[^\n]+)(\n)?', r'\n\n\2\n\n', content)

        # 清理开头和结尾的空白
        content = content.strip()

        return content


def main():
    parser = argparse.ArgumentParser(description='将网页转换为Markdown格式')
    parser.add_argument('url', help='要转换的网页URL')
    parser.add_argument('-o', '--output', default='output', help='输出目录（默认: output）')
    parser.add_argument('-f', '--filename', help='输出文件名（不含扩展名，默认使用网页标题）')
    parser.add_argument('--no-images', action='store_true', help='不下载图片')

    args = parser.parse_args()

    # 验证URL
    if not args.url.startswith(('http://', 'https://')):
        args.url = 'https://' + args.url

    try:
        converter = WebpageToMarkdown(args.url, args.output, args.filename)

        if args.no_images:
            converter.h.ignore_images = True

        converter.convert_to_markdown()

    except KeyboardInterrupt:
        print("\n操作已取消")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    url_list = [
        "https://mp.weixin.qq.com/s/yFMjIGID2q5JdPXlF7iifg",
        # "https://mp.weixin.qq.com/s?__biz=MzkyNzU3MDI3Nw==&mid=2247486958&idx=1&sn=fa1835ddd2eee3bdafefcad5b74d2d94&chksm=c2274de4f550c4f28c7b9e54f1a6a8bcacc3459e88bbe256c362a899a36ca32c80be4f87c45a&scene=21#wechat_redirect",
        "https://mp.weixin.qq.com/s/8hz4n5SO6B6wFJY3x7iheQ",
        # "https://mp.weixin.qq.com/s/q08xpnd-LzNea_y6kX77sA",
    ]
    output_lst = [
        "小米汽车答网友问(第0集)",
        # "小米汽车答网友问(第1集)",
        "小米汽车答网友问(第2集)",
        # "小米汽车答网友问(第3集)",

    ]
    for url, output in zip(url_list, output_lst):
        WebpageToMarkdown(url, output)
        converter = WebpageToMarkdown(url, output, output)

        converter.convert_to_markdown()
