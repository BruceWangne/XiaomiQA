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
            src = img.get('src')
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
        "https://mp.weixin.qq.com/s?__biz=MzkyNzU3MDI3Nw==&mid=2247486958&idx=1&sn=fa1835ddd2eee3bdafefcad5b74d2d94&chksm=c2274de4f550c4f28c7b9e54f1a6a8bcacc3459e88bbe256c362a899a36ca32c80be4f87c45a&scene=21#wechat_redirect",
        "https://mp.weixin.qq.com/s/8hz4n5SO6B6wFJY3x7iheQ",
        "https://mp.weixin.qq.com/s/q08xpnd-LzNea_y6kX77sA",
        "https://mp.weixin.qq.com/s/JC5aGDFDRvgpQ3FesjaS2A",
        "https://mp.weixin.qq.com/s/g4Xr3MWllPqd5hZD-_ibcQ",
        "https://mp.weixin.qq.com/s/xCidpA4jPrS9697uzNqvwg",
        "https://mp.weixin.qq.com/s/vmTpchQ6_yICyxZtwHViXQ",
        "https://mp.weixin.qq.com/s/_snL5Odhyw0FOimn46yA7A",
        "https://mp.weixin.qq.com/s/0jbh30HwXsHSx3Oz9bZ1xg",
        "https://mp.weixin.qq.com/s/ELPH13xkpUGLUj9FgAcq_A",
        "https://mp.weixin.qq.com/s/uxzKFtcmVS1VrhvXMIfaJA",
        "https://mp.weixin.qq.com/s/_FOl9pXnbQxX4Czc1pUsZQ",
        "https://mp.weixin.qq.com/s/HKn0rdn23qTID1eu1SfiXw",
        "https://mp.weixin.qq.com/s/FZj6VzIFMdr2Vut-wI8Jsg",
        "https://mp.weixin.qq.com/s/U7WEZB52mO3-G9C7fRnqEg",
        "https://mp.weixin.qq.com/s/nBoe4PvhUVH6ybpxw1Qg4w",
        "https://mp.weixin.qq.com/s/QSuLnmBFMm6mYJV26HB4Fw",
        "https://mp.weixin.qq.com/s/WLrgiFpO7PLZApqqQ1hRbg",
        "https://mp.weixin.qq.com/s/-hrmZ9NUoPT5MntmD2ri1g",
        "https://mp.weixin.qq.com/s/iDB0KfwHSndAwandVQQEzw",
        "https://mp.weixin.qq.com/s/IgEQ8lE93se983lv6wAL-w",
        "https://mp.weixin.qq.com/s/OR8sC6_KXorq4NC4UohyAQ",
        "https://mp.weixin.qq.com/s/1yCjQsfYuNssWnKdowRRng",
        "https://mp.weixin.qq.com/s/AQOcrMncAUTLmH36MWyEag",
        "https://mp.weixin.qq.com/s/wOGz_pKOlVXZ92S7Tv5njQ",
        "https://mp.weixin.qq.com/s/YeanZCIM4w8VL7XaRh0GaA",
        "https://mp.weixin.qq.com/s/fGVruFB8BFdxudfRyBLzug",
        "https://mp.weixin.qq.com/s/_reyYbhucrdEZuITTA97XA",
        "https://mp.weixin.qq.com/s/icbKGC5ATLqq6drdli5zDg",
        "https://mp.weixin.qq.com/s/7lKSDDyOeDiezhoY2t6vcA",
        "https://mp.weixin.qq.com/s/BNjnfcAZYhd9i0VzKrDTyg",
        "https://mp.weixin.qq.com/s/2vuQZcBvtvBFkjVfv4pu7g",
        "https://mp.weixin.qq.com/s/t0fXnjJBnISud4W_h28LJw",
        "https://mp.weixin.qq.com/s/2GCNkAgifXQx1HaMFtTOJA",
        "https://mp.weixin.qq.com/s/ih95BPWHfmV0NR4-j5wrqg",
        "https://mp.weixin.qq.com/s/UC2u2g1-3G-jPAIvNO1x0w",
        "https://mp.weixin.qq.com/s/82p3fm4PIo7wt9e414nPmA",
        "https://mp.weixin.qq.com/s/gfhT1LR_ReXlo-9_QWeV-A",
        "https://mp.weixin.qq.com/s/ECt6gggOQ3lZGeihXXmw_g",
        "https://mp.weixin.qq.com/s/qMJgCoNvYoMViaDNjsDQEw",
        "https://mp.weixin.qq.com/s/XU-AYWo8JNDWKkwVC9cZqA",
        "https://mp.weixin.qq.com/s/XTXm0nvbo3yphpcVjXw46g",
        "https://mp.weixin.qq.com/s/lxhm-Y5eXQJFasSEWUPKyw",
        "https://mp.weixin.qq.com/s/roRgGuyEp2rRubds6TV43w",
        "https://mp.weixin.qq.com/s/ahfWAgpi_vjlCr-ld0-4aw",
        "https://mp.weixin.qq.com/s/VYmQxJ3uhva1i-gs7pGh1Q",
        "https://mp.weixin.qq.com/s/2O3DeLHmw1B0F39KFKMrxw",
        "https://mp.weixin.qq.com/s/nrDchn0y7lIhAv3I_yLP1w",
        "https://mp.weixin.qq.com/s/RMF1VZYesSAQJeJqEHLYow",
        "https://mp.weixin.qq.com/s/aAwQCZlRiFWHJHR86hi5pQ",
        "https://mp.weixin.qq.com/s/qEvIFq4E5HCGPGx_TPBFKw",
        "https://mp.weixin.qq.com/s/D-YOAGDVmnYIktC19iwzYQ",
        "https://mp.weixin.qq.com/s/1FmVSvZvHvSMIvYrLEzUPQ",
        "https://mp.weixin.qq.com/s/Fy94MZVSYorVXJCkVDLsUg",
        "https://mp.weixin.qq.com/s/CveAZfA7pZU861PhHnykxg",
        "https://mp.weixin.qq.com/s/fVCm3hTMoLnScxAsDKsdtQ",
        "https://mp.weixin.qq.com/s/piH31-GXMIcxeaD9ylmMxg",
        "https://mp.weixin.qq.com/s/91SFiNPcp8zrj3KH6wXAcw",
        "https://mp.weixin.qq.com/s/Btja5clLxdchPXiAL4sgtQ",
        "https://mp.weixin.qq.com/s/fyt5Io4mh8TT5gjmkzBocg",
        "https://mp.weixin.qq.com/s/8-wAZMDo3sZ4sZFb6LnsNQ",
        "https://mp.weixin.qq.com/s/NfOVgI7wPn8wGh3_ePm5cw",
        "https://mp.weixin.qq.com/s/NwZHH-IvQJdB7VfUWBcBmg",
        "https://mp.weixin.qq.com/s/GtfeeE06I7lsXmdhKipsKw",
        "https://mp.weixin.qq.com/s/KAnSsotma2OlsddKpAuYBQ",
        "https://mp.weixin.qq.com/s/qMwZ9nA3rF5hlDUGam-ztA",
        "https://mp.weixin.qq.com/s/JC7lp7V59YPcZEnEg6-dVQ",
        "https://mp.weixin.qq.com/s/JEd15_3vQGJZonWOjqWhOA",
        "https://mp.weixin.qq.com/s/cgaETwdNCQjoUmn7rAGLdw",
        "https://mp.weixin.qq.com/s/WU5eDKlp2kmex4azucB4Tg",
        "https://mp.weixin.qq.com/s/SAdV1saad8vas0LzjhcicQ",
        "https://mp.weixin.qq.com/s/EUvJAkTAt3LaXFq6GR_EQQ",
        "https://mp.weixin.qq.com/s/7CLvre24l3Kn_sALfBIyGw",
        "https://mp.weixin.qq.com/s/apbTTPzR5IHlax_YPfH1dw",
        "https://mp.weixin.qq.com/s/iGO7Wu4OBLJQWvJmru3J2Q",
        "https://mp.weixin.qq.com/s/sYNuIlP_rI4pQgqkrkoDPQ",
        "https://mp.weixin.qq.com/s/1MU0jJXMOiv3OZ_efztwng",
        "https://mp.weixin.qq.com/s/HakbeNOcYV7H4o6raoAuVg",
        "https://mp.weixin.qq.com/s/ru_iltRxGH56lO8Om0bCbQ",
        "https://mp.weixin.qq.com/s/65GMR_cp0Tu7NG0A_8w_oQ",
        "https://mp.weixin.qq.com/s/w2kipy29JFYD_lMuDRfQvw",
        "https://mp.weixin.qq.com/s/IZI-EMHL7B0XlQtRkpUOaQ",
        "https://mp.weixin.qq.com/s/rJkob2OX6EYcNm2TuCIRYQ",
        "https://mp.weixin.qq.com/s/VW5ml7iId0kJmazy8hT94g",
        "https://mp.weixin.qq.com/s/LefGHb9xgf7txXQQH7vsDw",
        "https://mp.weixin.qq.com/s/Dp9PK4ebi8s52D-30mc3mw",
        "https://mp.weixin.qq.com/s/bXWPXPT2oEmIw8IDE9HKtA",
        "https://mp.weixin.qq.com/s/b4jsYV01MWZK2Zt5ZXkeyA",
        "https://mp.weixin.qq.com/s/K3iriBeC3xJK3ave_TC6Ww",
        "https://mp.weixin.qq.com/s/eCewtWkn4_5K5kvL3a1P2A",
        "https://mp.weixin.qq.com/s/zRNa5BYVpccRnA6OjZ8hmQ",
        "https://mp.weixin.qq.com/s/SnPgHuvsc5n8ajofu8LmGg",
        "https://mp.weixin.qq.com/s/Ah-e5FhUgkmAbUHiVAlDqA",
        "https://mp.weixin.qq.com/s/4ouGj8BRgjLTXHNCZeWlSw",
        "https://mp.weixin.qq.com/s/nbLXVoFra0oG4qASDdTINA",
        "https://mp.weixin.qq.com/s/2BAAb9ECr-xJUBgKe1V7xQ",
        "https://mp.weixin.qq.com/s/ASC3bgWdWluTAKZ6WpGxMg",
        "https://mp.weixin.qq.com/s/hcNAGlKVT59cFRSaubKqDQ",
        "https://mp.weixin.qq.com/s/u8-0wdND5pJddXbV1BKcLw",
        "https://mp.weixin.qq.com/s/k12K7ygl23dLgqxNFQtlyg",
        "https://mp.weixin.qq.com/s/S61Z3oM7sPnAGaCYfcZ_sQ",
        "https://mp.weixin.qq.com/s/uoLvQ38s4-W9a8J28mpr4w",
        "https://mp.weixin.qq.com/s/dRYiCgV4iduV22UMhSpQDw",
        "https://mp.weixin.qq.com/s/rPZrKkPHQpwFs4SOAp-rMQ",
        "https://mp.weixin.qq.com/s/FixZZlA-MGWkpPsUkwWucg",
        "https://mp.weixin.qq.com/s/5dixSZfSSZMcTpblO68Hsg",
        "https://mp.weixin.qq.com/s/OLRh7n4J08FJug-T5IWplw",
        "https://mp.weixin.qq.com/s/rylIvH3kRt5miQawvFZhxw",
        "https://mp.weixin.qq.com/s/YKfhKjp3jG6-6JyGKnvQ8w",
        "https://mp.weixin.qq.com/s/_2TGgQ2ugo8LD4JeU29eEA",
        "https://mp.weixin.qq.com/s/CxPKtLRxYdyEQlKfpJc_CA",
        "https://mp.weixin.qq.com/s/fNWL6gyD06vlC2q4ZJ8WGQ",
        "https://mp.weixin.qq.com/s/RLO4ffXkeMB2RqV7xOpbQA",
        "https://mp.weixin.qq.com/s/5b3HqpCQeG_5PnqhtGebow",
        "https://mp.weixin.qq.com/s/ai9AqjM_RujbdI0o4HtsHw",
        "https://mp.weixin.qq.com/s/6yvl7H9UNY7Pr6EB1Aksmw",
        "https://mp.weixin.qq.com/s/zz-citwdxNZV9_XIBCuVfw",
        "https://mp.weixin.qq.com/s/kfmbItUXErX1IYnF3PxQxw",
        "https://mp.weixin.qq.com/s/d_gBeQ-vhKuwDE8liFB9Iw",
        "https://mp.weixin.qq.com/s/CBT6rChORsqQ83qV_LZnrg",
        "https://mp.weixin.qq.com/s/S0GtA5cAoOVCl4OsWKrU7w",
        "https://mp.weixin.qq.com/s/zBJOv1xRluXEdYtgJagmJw",
        "https://mp.weixin.qq.com/s/RaVVEFXk8FIxVOSaKIdMLg",
        "https://mp.weixin.qq.com/s/TpIlMNWUGGU3zyTy6IdPcw",
        "https://mp.weixin.qq.com/s/ywqyQ-lQWvyx5tV1PUYgrg",
        "https://mp.weixin.qq.com/s/GFAXkOq1BPdg5xV00HlY7w",
        "https://mp.weixin.qq.com/s/EidU-qBzRSYMPQAYBxm1LA",
        "https://mp.weixin.qq.com/s/SFXufmvuN-YOrQG07gODWg",
        "https://mp.weixin.qq.com/s/3w-qrU8nZV0u4XzHi1pAZw",
        "https://mp.weixin.qq.com/s/uq2w4bhEpG3meg29gCg8hw",
        "https://mp.weixin.qq.com/s/doX9FP3zR0GrBtwB_o5b9A",
        "https://mp.weixin.qq.com/s/zqtSF7ZJchVXjkAsnNYLAw",
        "https://mp.weixin.qq.com/s/7Gsw2bl6YofsEjsgp6bhAg",
        "https://mp.weixin.qq.com/s/k5Eg5gpSD8dkKY4v2UNYMA",
        "https://mp.weixin.qq.com/s/Z0gl0uHwh79pnaB7jR0elA",
        "https://mp.weixin.qq.com/s/EjjZkuRX2FOTnJtIaO2zsQ",
        "https://mp.weixin.qq.com/s/6mjsaXN68T9bB_CfIjacZw",
        "https://mp.weixin.qq.com/s/KOAW5MrGHE5bIokrZ7wuow",
        "https://mp.weixin.qq.com/s/jeUI_cQNriOw30ZWL2lR2g",
        "https://mp.weixin.qq.com/s/Ci2wNni6o4qESxJg0IQQdg",
        "https://mp.weixin.qq.com/s/KKfPRla5kHPv8VahguIczQ",
        "https://mp.weixin.qq.com/s/sZ55-Gm5zU5UGHhH7m24CQ",
        "https://mp.weixin.qq.com/s/0owzwdGc-IZO0-p8rZnCxQ",
        "https://mp.weixin.qq.com/s/zrO7Za7DVCEc43JhWZRzZQ",
        "https://mp.weixin.qq.com/s/olWxNjvs34NfT7jdEVBB3g",
        "https://mp.weixin.qq.com/s/OQwlRH-SS0rcYTo5KoKg5w",
        "https://mp.weixin.qq.com/s/lgF8YfvhGBOnW-OzdLFS6g",
        "https://mp.weixin.qq.com/s/jJS-WPimMyiiYpoYUQ_UtQ",
        "https://mp.weixin.qq.com/s/rXS4lBJKE08Qr2W9gf_z0w",
        "https://mp.weixin.qq.com/s/idcv3FB-fQJLY1iMDBMCHA",
        "https://mp.weixin.qq.com/s/6SF3i8N5IYZ6mEdYkHyVuA",
        "https://mp.weixin.qq.com/s/2O50oYDI2BNulXG0Z31Zxg",
        "https://mp.weixin.qq.com/s/b9j0KPVkXPPiNlv6v97DKQ",
        "https://mp.weixin.qq.com/s/-KA_k0ynCtE0w8Lho0W_5Q",
        "https://mp.weixin.qq.com/s/qToqFjbzNG_5g7qDtA9nvg",
        "https://mp.weixin.qq.com/s/wVaHrOytZdTnWrCeuawYkQ",
        "https://mp.weixin.qq.com/s/FP7qXBy_qiBghdlLRB8sDQ",
        "https://mp.weixin.qq.com/s/b1bFFs37dj4udxNkbPnl9Q",
        "https://mp.weixin.qq.com/s/XlWMNp3PFo8juCzxQOo12A",
        "https://mp.weixin.qq.com/s/g5mvME3DCvO4-yjkI67LWg",
        "https://mp.weixin.qq.com/s/myxpf-lFz3OQZVBNBIPx5A",
        "https://mp.weixin.qq.com/s/fFV6_a9L4r4cA_zUvbo4KQ",
        "https://mp.weixin.qq.com/s/o1ikhRptiBjDzPUzZHdMCw",
        "https://mp.weixin.qq.com/s/AiXdTrtKL7rzqMND_ad-7w",
        "https://mp.weixin.qq.com/s/dGz-y8f5hVvRBZTfslpQJQ",
        "https://mp.weixin.qq.com/s/1LjRG7zNnofsAdA0pRSDAQ",
        "https://mp.weixin.qq.com/s/fRryxkEa9pEJScZ8Rkp9qQ",
        "https://mp.weixin.qq.com/s/HjHwXW7fqsH9kQnmRxhtHA",
        "https://mp.weixin.qq.com/s/TWUR-cBAEDV5FboAVLo55g",
        "https://mp.weixin.qq.com/s/013k9CwmyzktXspMOC8AaA",
        "https://mp.weixin.qq.com/s/OS2iqgFQfs05lwbv4iVGUw",
        "https://mp.weixin.qq.com/s/7aH5Jg7HGUexkUlF-W3Tww",
        "https://mp.weixin.qq.com/s/WGPkXrLf6kiCv11JuKEawA",
        "https://mp.weixin.qq.com/s/9EWWhq24PzDZmFrFDhZwag",
        "https://mp.weixin.qq.com/s/7hjETRfI6o8nkRfNZhRxlQ",
        "https://mp.weixin.qq.com/s/h64PywOZ8-TIj0UyTv2Vuw",
        "https://mp.weixin.qq.com/s/Hk4hJF0rO6sequq38vl9vQ",
        "https://mp.weixin.qq.com/s/RQGCWFjQt9NWMdQgy9tXTA",
        "https://mp.weixin.qq.com/s/EY1ZgdxF3jA6kUdrsPFVzQ",
        "https://mp.weixin.qq.com/s/_Kr-y-IJze9IzevWtbIakw",
        "https://mp.weixin.qq.com/s/iyVfb8LTt1te5MFdGu7Kww",
        "https://mp.weixin.qq.com/s/zb1JcJvN1Qk40YSCzqr7Kw",
        "https://mp.weixin.qq.com/s/2wmVR-5ZzUM7mEFOJGbX5w",
        "https://mp.weixin.qq.com/s/53ErmKqDA6lpd3VH6mQF7A",
        "https://mp.weixin.qq.com/s/FhQB-k6uFuEnhmZxNlTO5Q",
        "https://mp.weixin.qq.com/s/OYVCGNYtHbV07uZY1pk7Ew",
        "https://mp.weixin.qq.com/s/fEuklOXqfwrBwMCRzi0qKw",
        "https://mp.weixin.qq.com/s/RgAUCMeUrceYqB9JLSSUMA",
        "https://mp.weixin.qq.com/s/-DB5u_IB_PjBpvlcSoF9_Q",
        "https://mp.weixin.qq.com/s/s8bm4zwUwN02flynjw_QiQ",
        "https://mp.weixin.qq.com/s/_2u2svPy58yRI3bNUVS-CQ",
        "https://mp.weixin.qq.com/s/pN4nEhkBCDbjglH4Q7Lbyg",
        "https://mp.weixin.qq.com/s/Vfu63VKr2OJRa3370xp2Xw",
        "https://mp.weixin.qq.com/s/v2uUK3gDj_rIkFe75EupmQ",
        "https://mp.weixin.qq.com/s/4aSWHogeFnW0QdJ_vt6BzQ",
        "https://mp.weixin.qq.com/s/4VDBMMHoSIUI8C-qfmQQtw",
    ]
    output_lst = [
        "小米汽车答网友问(第0集)",
        "小米汽车答网友问(第1集)",
        "小米汽车答网友问(第2集)",
        "小米汽车答网友问(第3集)",
        "小米汽车答网友问(第4集)",
        "小米汽车答网友问(第5集)",
        "小米汽车答网友问(第6集)",
        "小米汽车答网友问(第7集)",
        "小米汽车答网友问(第8集)",
        "小米汽车答网友问(第9集)",
        "小米汽车答网友问(第10集)",
        "小米汽车答网友问(第11集)",
        "小米汽车答网友问(第12集)",
        "小米汽车答网友问(第13集)",
        "小米汽车答网友问(第14集)",
        "小米汽车答网友问(第15集)",
        "小米汽车答网友问(第16集)",
        "小米汽车答网友问(第17集)",
        "小米汽车答网友问(第18集)",
        "小米汽车答网友问(第19集)",
        "小米汽车答网友问(第20集)",
        "小米汽车答网友问(第21集)",
        "小米汽车答网友问(第22集)",
        "小米汽车答网友问(第23集)",
        "小米汽车答网友问(第24集)",
        "小米汽车答网友问(第25集)",
        "小米汽车答网友问(第26集)",
        "小米汽车答网友问(第27集)",
        "小米汽车答网友问(第28集)",
        "小米汽车答网友问(第29集)",
        "小米汽车答网友问(第30集)",
        "小米汽车答网友问(第31集)",
        "小米汽车答网友问(第32集)",
        "小米汽车答网友问(第33集)",
        "小米汽车答网友问(第34集)",
        "小米汽车答网友问(第35集)",
        "小米汽车答网友问(第36集)",
        "小米汽车答网友问(第37集)",
        "小米汽车答网友问(第38集)",
        "小米汽车答网友问(第39集)",
        "小米SU7答网友问：总集篇（上）",
        "小米SU7答网友问：总集篇（中）",
        "小米SU7答网友问：总集篇（下）",
        "小米汽车答网友问(第40集)",
        "小米汽车答网友问(第41集)",
        "小米汽车答网友问(第42集)",
        "小米汽车答网友问(第43集)",
        "小米汽车答网友问(第44集)",
        "小米汽车答网友问(第45集)",
        "小米汽车答网友问(第46集)",
        "小米汽车答网友问(第47集)",
        "小米汽车答网友问(第48集)",
        "小米汽车答网友问(第49集)",
        "小米汽车答网友问(第50集)",
        "小米汽车答网友问(第51集)",
        "小米汽车答网友问(第52集)",
        "小米汽车答网友问(第53集)",
        "小米汽车答网友问(第54集)",
        "小米汽车答网友问(第55集)",
        "小米汽车答网友问(第56集)",
        "小米汽车答网友问(第57集)",
        "小米汽车答网友问(第58集)",
        "小米汽车答网友问(第59集)",
        "小米汽车答网友问(第60集)",
        "小米汽车答网友问(第61集)",
        "小米汽车答网友问(第62集)",
        "小米汽车答网友问(第63集)",
        "小米汽车答网友问(第64集)",
        "小米汽车答网友问(第65集)",
        "小米汽车答网友问(第66集)",
        "小米汽车答网友问(第67集)",
        "小米汽车答网友问(第68集)",
        "小米汽车答网友问(第69集)",
        "小米汽车答网友问(第70集)",
        "小米汽车答网友问(第71集)",
        "小米汽车答网友问(第72集)",
        "小米汽车答网友问(第73集)",
        "小米汽车答网友问(第74集)",
        "小米汽车答网友问(第75集)",
        "小米汽车答网友问(第76集)",
        "小米汽车答网友问(第77集)",
        "小米汽车答网友问(第78集)",
        "小米汽车答网友问(第79集)",
        "小米汽车答网友问(第80集)",
        "小米汽车答网友问(第81集)",
        "小米汽车答网友问(第82集)",
        "小米汽车答网友问(第83集)",
        "小米汽车答网友问(第84集)",
        "小米汽车答网友问(第85集)",
        "小米汽车答网友问(第86集)",
        "小米汽车答网友问(第87集)",
        "小米汽车答网友问(第88集)",
        "小米汽车答网友问(第89集)",
        "小米汽车答网友问(第90集)",
        "小米汽车答网友问(第91集)",
        "小米汽车答网友问(第92集)",
        "小米汽车答网友问(第93集)",
        "小米汽车答网友问(第94集)",
        "小米汽车答网友问(第95集)",
        "小米汽车答网友问(第96集)",
        "小米汽车答网友问(第97集)",
        "小米汽车答网友问(第98集)",
        "小米汽车答网友问(第99集)",
        "小米汽车答网友问(第100集)",
        "小米汽车答网友问(第101集)",
        "小米汽车答网友问(第102集)",
        "小米汽车答网友问(第103集)",
        "小米汽车答网友问(第104集)",
        "小米汽车答网友问(第105集)",
        "小米汽车答网友问(第106集)",
        "小米汽车答网友问(第107集)",
        "小米汽车答网友问(第108集)",
        "小米汽车答网友问(第109集)",
        "小米汽车答网友问(第110集)",
        "小米汽车答网友问(第111集)",
        "小米汽车答网友问(第112集)",
        "小米汽车答网友问(第113集)",
        "小米汽车答网友问(第114集)",
        "小米汽车答网友问(第115集)",
        "小米汽车答网友问(第116集)",
        "小米汽车答网友问(第117集)",
        "小米汽车答网友问(第118集)",
        "小米汽车答网友问(第119集)",
        "小米汽车答网友问(第120集)",
        "小米汽车答网友问(第121集)",
        "小米汽车答网友问(第122集)",
        "小米汽车答网友问(第123集)",
        "小米汽车答网友问(第124集)",
        "小米汽车答网友问(第125集)",
        "小米汽车答网友问(第126集)",
        "小米汽车答网友问(第127集)",
        "小米汽车答网友问(第128集)",
        "小米汽车答网友问(第129集)",
        "小米汽车答网友问(第130集)",
        "小米汽车答网友问(第131集)",
        "小米汽车答网友问(第132集)",
        "小米汽车答网友问(第133集)",
        "小米汽车答网友问(第134集)",
        "小米汽车答网友问(第135集)",
        "小米汽车答网友问(第136集)",
        "小米汽车答网友问(第137集)",
        "关于大家关心问题的回答1",
        "关于大家关心问题的回答2",
        "关于大家关心问题的回答3",
        "小米汽车答网友问(第138集)",
        "小米汽车答网友问(第139集)",
        "小米汽车答网友问(第140集)",
        "小米汽车答网友问(第141集)",
        "小米汽车答网友问(第142集)",
        "小米汽车答网友问(第143集)",
        "小米汽车答网友问(第144集)",
        "小米汽车答网友问(第145集)",
        "小米汽车答网友问(第146集)",
        "小米汽车答网友问(第147集)",
        "小米汽车答网友问(第148集)",
        "小米汽车答网友问(第149集)",
        "小米汽车答网友问(第150集)",
        "小米汽车答网友问(第151集)",
        "小米汽车答网友问(第152集)",
        "小米汽车答网友问(第153集)",
        "小米汽车答网友问(第154集)",
        "小米汽车答网友问(第155集)",
        "小米汽车答网友问(第156集)",
        "小米汽车答网友问(第157集)",
        "小米汽车答网友问(第158集)",
        "小米汽车答网友问(第159集)",
        "小米汽车答网友问(第160集)",
        "小米汽车答网友问(第161集)",
        "小米汽车答网友问(第162集)",
        "小米汽车答网友问(第163集)",
        "小米汽车答网友问(第164集)",
        "小米汽车答网友问(第165集)",
        "小米汽车答网友问(第166集)",
        "小米汽车答网友问(第167集)",
        "小米汽车答网友问(第168集)",
        "小米汽车答网友问(第169集)",
        "小米汽车答网友问(第170集)",
        "小米汽车答网友问(第171集)",
        "小米汽车答网友问(第172集)",
        "小米汽车答网友问(第173集)",
        "小米汽车答网友问(第174集)",
        "小米汽车答网友问(第175集)",
        "小米汽车答网友问(第176集)",
        "小米汽车答网友问(第177集)",
        "小米汽车答网友问(第178集)",
        "小米汽车答网友问(第179集)",
        "小米汽车答网友问(第180集)",
        "小米汽车答网友问(第181集)",
        "小米汽车答网友问(第182集)",
        "小米汽车答网友问(第183集)",
        "小米汽车答网友问(第184集)",
        "小米汽车答网友问(第185集)",
        "小米汽车答网友问(第186集)",
        "小米汽车答网友问(第187集)",
        "小米汽车答网友问(第188集)",
        "小米汽车答网友问(第189集)",
        "小米汽车答网友问(第190集)",
        "小米汽车答网友问(第191集)",
        "小米汽车答网友问(第192集)",
        "小米汽车答网友问(第193集)",
        "小米汽车答网友问(第194集)",
        "小米汽车答网友问(第195集)",
        "小米汽车答网友问(第196集)",
        "小米汽车答网友问(第197集)",
        "小米汽车答网友问(第198集)",
    ]
    for url, output in zip(url_list, output_lst):
        WebpageToMarkdown(url, output)
        converter = WebpageToMarkdown(url, output, output)

        converter.convert_to_markdown()
