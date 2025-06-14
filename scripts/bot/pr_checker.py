#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GitHub PR 检查机器人

此模块提供了检查 GitHub Pull Request 的功能。
"""

import json
import os
import sys
from typing import Dict, List, Any, Optional, Tuple

# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
sys.path.insert(0, project_root)

try:
    from scripts.validation.domain_validator import validate_pull_request, load_config
except ImportError as e:
    print(f"导入错误: {e}", file=sys.stderr)
    print(f"当前目录: {current_dir}", file=sys.stderr)
    print(f"项目根目录: {project_root}", file=sys.stderr)
    print(f"Python 路径: {sys.path[:3]}", file=sys.stderr)
    sys.exit(1)


def check_domain_ownership(file_path: str, pr_author: str, repo_owner: str, repo_name: str, github_token: Optional[str] = None) -> List[str]:
    """
    检查域名所有权
    
    Args:
        file_path: 域名配置文件路径
        pr_author: PR作者的GitHub用户名
        repo_owner: 仓库所有者
        repo_name: 仓库名称
        github_token: GitHub API token (可选)
    
    Returns:
        错误信息列表，如果为空则表示验证通过
    """
    errors = []
    
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            # 新文件，无需检查所有权
            return errors
        
        # 读取现有文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                domain_config = json.load(f)
            except json.JSONDecodeError:
                # JSON格式错误会由其他验证器处理
                return errors
        
        # 检查配置中的所有者信息
        owner_field = domain_config.get('owner', {})
        if isinstance(owner_field, dict):
            config_owner = owner_field.get('username', '').lower()
        elif isinstance(owner_field, str):
            config_owner = owner_field.lower()
        else:
            errors.append("域名配置中的 'owner' 字段格式不正确")
            return errors
        
        # 检查PR作者是否为配置的所有者
        if config_owner and config_owner != pr_author.lower():
            # 使用GitHub API检查历史提交信息
            original_author = get_original_author(file_path, repo_owner, repo_name, github_token)
            
            if original_author and original_author.lower() != pr_author.lower():
                errors.append(
                    f"权限验证失败: 该域名配置最初由用户 '{original_author}' 创建，"
                    f"当前PR作者 '{pr_author}' 无权修改此配置。\n"
                    f"如果您需要修改此域名配置，请："
                    f"\n  1. 联系原作者 @{original_author} 进行修改"
                    f"\n  2. 或者提供域名所有权证明"
                    f"\n  3. 或者联系项目维护者协助处理"
                )
        
    except Exception as e:
        errors.append(f"所有权验证过程中发生错误: {str(e)}")
    
    return errors


def get_original_author(file_path: str, repo_owner: str, repo_name: str, github_token: Optional[str] = None) -> Optional[str]:
    """
    通过GitHub API获取文件的原始作者
    
    Args:
        file_path: 文件路径
        repo_owner: 仓库所有者
        repo_name: 仓库名称
        github_token: GitHub API token
    
    Returns:
        原始作者的用户名，如果无法获取则返回None
    """
    if not github_token:
        return None
    
    try:
        import requests
        
        # 获取文件的提交历史
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits"
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        params = {
            'path': file_path,
            'per_page': 100
        }
        
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            commits = response.json()
            if commits:
                # 获取最早的提交（最后一个）
                earliest_commit = commits[-1]
                return earliest_commit['author']['login']
    except Exception as e:
        print(f"获取原始作者信息时发生错误: {e}", file=sys.stderr)
    
    return None


def format_validation_result(results: Dict[str, List[str]]) -> str:
    """
    格式化验证结果为 Markdown 格式
    
    Args:
        results: 验证结果字典 {文件路径: 错误信息列表}
    
    Returns:
        Markdown 格式的验证结果
    """
    markdown = []
    markdown.append("# 🤖 域名配置验证结果\n")
    
    # 统计信息
    total_files = len(results)
    error_files = sum(1 for errors in results.values() if errors)
    success_files = total_files - error_files
    
    if error_files == 0:
        markdown.append("## ✅ 验证通过")
        markdown.append(f"所有 {total_files} 个文件验证通过，没有发现问题。\n")
    else:
        markdown.append("## ❌ 验证失败")
        markdown.append(f"共 {total_files} 个文件，其中 {error_files} 个文件有问题，{success_files} 个文件正常。\n")
    
    # 详细结果
    for file_path, errors in results.items():
        if errors:
            markdown.append(f"### ❌ `{file_path}`")
            markdown.append("")
            for i, error in enumerate(errors, 1):
                # 将多行错误信息格式化
                if '\n' in error:
                    lines = error.split('\n')
                    markdown.append(f"**错误 {i}:** {lines[0]}")
                    for line in lines[1:]:
                        if line.strip():
                            if line.strip().startswith('💡'):
                                markdown.append(f"  {line.strip()}")
                            else:
                                markdown.append(f"  - {line.strip()}")
                else:
                    markdown.append(f"**错误 {i}:** {error}")
            markdown.append("")
        else:
            markdown.append(f"### ✅ `{file_path}`")
            markdown.append("")
            markdown.append("验证通过，没有发现问题。")
            markdown.append("")
    
    # 添加帮助提示
    if error_files > 0:
        markdown.append("---")
        markdown.append("## 💡 常见问题解决方法")
        markdown.append("")
        markdown.append("### 文件路径和格式")
        markdown.append("- **文件位置**: 必须放在 `domains/{域名}/` 目录下")
        markdown.append("- **文件命名**: 必须以 `.json` 结尾，如 `myapp.json`")
        markdown.append("- **路径示例**: `domains/ciao.su/myapp.json`")
        markdown.append("")
        markdown.append("### JSON 格式错误")
        markdown.append("- **缺少逗号**: 确保 JSON 对象中的字段用逗号分隔")
        markdown.append("- **缺少冒号**: 确保键值对用冒号分隔")
        markdown.append("- **引号不匹配**: 确保所有字符串用双引号包围")
        markdown.append("- **多余逗号**: 删除最后一个字段后的多余逗号")
        markdown.append("- **属性名**: 所有属性名必须用双引号包围")
        markdown.append("")
        markdown.append("### 子域名规则")
        markdown.append("- **长度限制**: 3-63 个字符")
        markdown.append("- **字符限制**: 只能包含小写字母、数字和连字符")
        markdown.append("- **开头结尾**: 不能以连字符开头或结尾")
        markdown.append("- **保留名称**: 不能使用系统保留的子域名")
        markdown.append("")
        markdown.append("### 权限问题")
        markdown.append("- **域名所有权**: 只有域名配置的原作者才能修改其配置")
        markdown.append("- **协作修改**: 如需修改他人的域名配置，请先联系原作者")
        markdown.append("- **争议处理**: 如有争议，请联系项目维护者")
        markdown.append("")
        markdown.append("### 推荐工具")
        markdown.append("- 使用 [JSONLint](https://jsonlint.com/) 验证 JSON 格式")
        markdown.append("- 使用支持 JSON 语法高亮的编辑器（如 VS Code）")
        markdown.append("- 复制 `domains/{域名}/example.json` 作为模板")
        markdown.append("")
        markdown.append("### 配置示例")
        markdown.append("```json")
        markdown.append("{")
        markdown.append('  "owner": {')
        markdown.append('    "name": "你的名字",')
        markdown.append('    "github": "你的GitHub用户名",')
        markdown.append('    "email": "your@email.com"')
        markdown.append('  },')
        markdown.append('  "records": [')
        markdown.append('    {')
        markdown.append('      "type": "A",')
        markdown.append('      "name": "@",')
        markdown.append('      "content": "185.199.108.153",')
        markdown.append('      "ttl": 3600,')
        markdown.append('      "proxied": false')
        markdown.append('    }')
        markdown.append('  ]')
        markdown.append('}')
        markdown.append("```")
        markdown.append("")
        markdown.append("如需帮助，请查看 [用户指南](https://github.com/bestzwei/LibreDomains/blob/main/docs/user-guide.md)")
    
    return "\n".join(markdown)

def format_validation_result_console(results: Dict[str, List[str]]) -> str:
    """
    格式化验证结果为控制台输出格式
    
    Args:
        results: 验证结果字典 {文件路径: 错误信息列表}
    
    Returns:
        控制台格式的验证结果
    """
    output = []
    
    # 统计信息
    total_files = len(results)
    error_files = sum(1 for errors in results.values() if errors)
    success_files = total_files - error_files
    
    output.append("=" * 60)
    output.append("🤖 域名配置验证结果")
    output.append("=" * 60)
    
    if error_files == 0:
        output.append("✅ 验证通过")
        output.append(f"所有 {total_files} 个文件验证通过，没有发现问题。")
    else:
        output.append("❌ 验证失败")
        output.append(f"共 {total_files} 个文件，其中 {error_files} 个文件有问题，{success_files} 个文件正常。")
    
    output.append("")
    
    # 详细结果
    for file_path, errors in results.items():
        if errors:
            output.append(f"❌ {file_path}")
            output.append("-" * 40)
            for i, error in enumerate(errors, 1):
                # 将多行错误信息格式化
                if '\n' in error:
                    lines = error.split('\n')
                    output.append(f"错误 {i}: {lines[0]}")
                    for line in lines[1:]:
                        if line.strip():
                            output.append(f"  - {line.strip()}")
                else:
                    output.append(f"错误 {i}: {error}")
            output.append("")
        else:
            output.append(f"✅ {file_path}")
            output.append("验证通过，没有发现问题。")
            output.append("")
    
    # 添加帮助提示
    if error_files > 0:
        output.append("=" * 60)
        output.append("💡 常见问题解决方法")
        output.append("=" * 60)
        output.append("")
        output.append("JSON 格式错误:")
        output.append("- 缺少逗号: 确保 JSON 对象中的字段用逗号分隔")
        output.append("- 缺少冒号: 确保键值对用冒号分隔")
        output.append("- 引号不匹配: 确保所有字符串用双引号包围")
        output.append("- 多余逗号: 删除最后一个字段后的多余逗号")
        output.append("")
        output.append("推荐工具:")
        output.append("- 使用 JSONLint (https://jsonlint.com/) 验证 JSON 格式")
        output.append("- 使用支持 JSON 语法高亮的编辑器（如 VS Code）")
        output.append("")
        output.append("如需帮助，请查看用户指南:")
        output.append("https://github.com/bestzwei/LibreDomains/blob/main/docs/user-guide.md")
    
    return "\n".join(output)


def check_pr_files(pr_files: List[str], config: Optional[Dict[str, Any]] = None, console_output: bool = False, 
                   pr_author: Optional[str] = None, repo_owner: Optional[str] = None, 
                   repo_name: Optional[str] = None, github_token: Optional[str] = None) -> Tuple[bool, str]:
    """
    检查 Pull Request 中的文件
    
    Args:
        pr_files: Pull Request 中的文件路径列表
        config: 项目配置信息 (可选)
        console_output: 是否输出控制台格式 (默认为 Markdown 格式)
        pr_author: PR作者的GitHub用户名 (可选)
        repo_owner: 仓库所有者 (可选)
        repo_name: 仓库名称 (可选)
        github_token: GitHub API token (可选)
    
    Returns:
        (是否所有文件有效, 格式化的验证结果)
    """
    # 规范化文件路径
    normalized_files = []
    missing_files = []
    
    for file_path in pr_files:
        # 支持相对路径和绝对路径
        if not os.path.isabs(file_path):
            # 相对路径，从项目根目录开始
            abs_path = os.path.join(project_root, file_path)
        else:
            abs_path = file_path
        
        # 检查文件是否存在
        if os.path.exists(abs_path):
            normalized_files.append(abs_path)
        else:
            # 尝试相对于当前工作目录
            if os.path.exists(file_path):
                normalized_files.append(os.path.abspath(file_path))
            else:
                missing_files.append(file_path)
                print(f"警告: 文件不存在: {file_path} (尝试路径: {abs_path})", file=sys.stderr)
    
    # 调试信息
    print(f"项目根目录: {project_root}", file=sys.stderr)
    print(f"当前工作目录: {os.getcwd()}", file=sys.stderr)
    print(f"原始文件列表: {pr_files}", file=sys.stderr)
    print(f"规范化文件列表: {normalized_files}", file=sys.stderr)
    print(f"缺失文件列表: {missing_files}", file=sys.stderr)
    
    # 如果没有找到任何文件
    if not normalized_files:
        error_msg = "没有找到需要验证的文件。\n\n"
        if missing_files:
            error_msg += "缺失的文件:\n"
            for file_path in missing_files:
                error_msg += f"- {file_path}\n"
        return False, f"## ❌ 验证失败\n\n{error_msg}"
    
    try:
        # 验证文件
        all_valid, results = validate_pull_request(normalized_files, config)
        
        # 如果提供了PR作者信息，则进行所有权验证
        if pr_author and repo_owner and repo_name:
            for file_path in normalized_files:
                ownership_errors = check_domain_ownership(
                    file_path, pr_author, repo_owner, repo_name, github_token
                )
                if ownership_errors:
                    if file_path not in results:
                        results[file_path] = []
                    results[file_path].extend(ownership_errors)
                    all_valid = False
        
        # 如果有缺失文件，添加到结果中
        for file_path in missing_files:
            results[file_path] = [f"文件不存在: {file_path}"]
            all_valid = False
        
        # 格式化结果
        if console_output:
            formatted_result = format_validation_result_console(results)
        else:
            formatted_result = format_validation_result(results)
        
        return all_valid, formatted_result
    except Exception as e:
        import traceback
        error_msg = f"验证过程中发生错误: {str(e)}"
        # 添加详细的错误追踪信息
        traceback_info = traceback.format_exc()
        print(f"详细错误信息:\n{traceback_info}", file=sys.stderr)
        
        # 添加环境调试信息
        print(f"环境调试信息:", file=sys.stderr)
        print(f"- Python 版本: {sys.version}", file=sys.stderr)
        print(f"- 当前目录: {os.getcwd()}", file=sys.stderr)
        print(f"- 脚本路径: {__file__}", file=sys.stderr)
        print(f"- 项目根目录: {project_root}", file=sys.stderr)
        
        if console_output:
            return False, f"验证失败\n\n{error_msg}\n\n详细错误信息请查看 Actions 日志。"
        else:
            return False, f"## ❌ 验证失败\n\n{error_msg}\n\n详细错误信息请查看 Actions 日志。"


def main():
    """命令行入口点"""
    import argparse
    
    parser = argparse.ArgumentParser(description='GitHub PR 检查工具')
    parser.add_argument('--config', help='配置文件路径')
    parser.add_argument('--files', nargs='+', required=True, help='要检查的文件路径')
    parser.add_argument('--output', help='输出文件路径')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    parser.add_argument('--console', action='store_true', help='输出控制台格式（默认为 Markdown 格式）')
    parser.add_argument('--pr-author', help='PR作者的GitHub用户名')
    parser.add_argument('--repo-owner', help='仓库所有者')
    parser.add_argument('--repo-name', help='仓库名称')
    parser.add_argument('--github-token', help='GitHub API token')
    
    args = parser.parse_args()
    
    # 启用调试模式
    if args.debug:
        print("=== 调试模式启用 ===", file=sys.stderr)
        print(f"命令行参数: {args}", file=sys.stderr)
        print(f"当前工作目录: {os.getcwd()}", file=sys.stderr)
        print(f"项目根目录: {project_root}", file=sys.stderr)
    
    try:
        # 加载项目配置
        config = None
        if args.config:
            config = load_config(args.config)
        else:
            try:
                config = load_config()
            except Exception as e:
                print(f"警告: 无法加载默认配置文件: {e}", file=sys.stderr)
        
        # 检查文件，如果没有指定输出文件且没有启用控制台模式，则自动启用控制台模式
        console_mode = args.console or not args.output
        all_valid, result = check_pr_files(
            args.files, config, console_output=console_mode,
            pr_author=args.pr_author, repo_owner=args.repo_owner,
            repo_name=args.repo_name, github_token=args.github_token
        )
        
        # 输出结果
        if args.output:
            output_dir = os.path.dirname(args.output)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"结果已保存到: {args.output}", file=sys.stderr)
        else:
            print(result)
        
        return 0 if all_valid else 1
    except Exception as e:
        import traceback
        error_msg = f"程序执行失败: {str(e)}"
        traceback_info = traceback.format_exc()
        print(error_msg, file=sys.stderr)
        print(f"详细错误信息:\n{traceback_info}", file=sys.stderr)
        
        if args.output:
            try:
                output_dir = os.path.dirname(args.output)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                with open(args.output, 'w', encoding='utf-8') as f:
                    if args.console:
                        f.write(f"执行失败\n\n{error_msg}\n\n{traceback_info}")
                    else:
                        f.write(f"## ❌ 执行失败\n\n{error_msg}\n\n```\n{traceback_info}\n```")
            except Exception as output_error:
                print(f"无法写入输出文件: {output_error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
