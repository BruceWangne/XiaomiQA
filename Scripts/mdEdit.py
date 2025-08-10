import re
import os
import sys


def replace_in_md(input_file, output_file, replacements):
    """
    读取 Markdown 文件，应用正则表达式替换，并保存到新文件。

    Args:
        input_file (str): 输入的 Markdown 文件路径。
        output_file (str): 输出的 Markdown 文件路径。
        replacements (list of tuples): 替换规则列表，每个元素是 (pattern, replacement) 元组。
    """

    # 检查输入文件是否存在
    if not os.path.exists(input_file):
        print(f"错误：输入文件 '{input_file}' 不存在。")
        return

    try:
        # 读取输入文件
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"成功读取文件：{input_file}")

        # 应用所有替换规则
        modified_content = content
        for pattern, replacement in replacements:
            # 使用 re.sub 进行正则替换
            # re.MULTILINE 使 ^ 和 $ 匹配每行的开始和结束
            # re.DOTALL 使 . 匹配包括换行符在内的所有字符
            modified_content, count = re.subn(pattern, replacement, modified_content, flags=re.MULTILINE | re.DOTALL)
            if count > 0:
                print(f"已替换 '{pattern}' -> '{replacement}'，共 {count} 处。")

        # 写入输出文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        print(f"修改后的内容已保存到：{output_file}")

    except Exception as e:
        print(f"处理文件时发生错误：{e}")


def main():
    # === 配置区域 ===
    # 请根据你的需求修改以下变量

    # 输入和输出文件路径
    input_md_file = r"D:\Source\Repos\XiaomiQA\QA\小米汽车答网友问(第001集)\小米汽车答网友问(第001集).md"  # 替换为你的输入文件名
    output_md_file = r"D:\Source\Repos\XiaomiQA\QA\小米汽车答网友问(第001集)\小米汽车答网友问(第001集)_edit.md"  # 替换为你的输出文件名

    # 定义替换规则：列表中的每个元组包含 (正则表达式模式, 替换字符串)
    # 注意：正则表达式需要正确转义特殊字符
    replacements = [
        # 示例 1: 将所有 **粗体** 标记替换为 __粗体__
        (r'\r\n\#', r'\r\n\#\#\#'),


    ]

    # === 执行 ===
    replace_in_md(input_md_file, output_md_file, replacements)


if __name__ == "__main__":
    main()