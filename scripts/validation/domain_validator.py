#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
JSON 配置验证模块

此模块提供了验证域名注册 JSON 文件的功能。
"""

import json
import os
import re
import sys
import glob
from typing import Dict, List, Any, Optional, Tuple
from scripts.utils.common import load_json_file

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


def load_config(config_path: str = None) -> Dict[str, Any]:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径 (可选，默认为项目根目录下的 config/domains.json)
    
    Returns:
        配置信息字典
    """
    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), '../../config/domains.json')
    
    data, error = load_json_file(config_path)
    if error:
        raise Exception(f"加载配置文件失败: {error}")
    return data


def is_valid_domain_name(domain_name: str) -> bool:
    """
    检查子域名是否合法
    
    Args:
        domain_name: 子域名名称
    
    Returns:
        子域名是否合法
    """
    # 子域名规则：只允许字母、数字和连字符，不能以连字符开头或结尾
    # 特殊情况：@ 表示根域名
    if domain_name == '@':
        return True
    
    # 修复：使用更严格的验证，确保大小写一致性，最少3个字符
    if len(domain_name) < 3:
        return False
    pattern = r'^[a-z0-9]([a-z0-9\-]{1,61}[a-z0-9])$'
    return bool(re.match(pattern, domain_name.lower()))


def is_valid_ip(ip: str) -> bool:
    """
    检查 IP 地址是否合法
    
    Args:
        ip: IP 地址
    
    Returns:
        IP 地址是否合法
    """
    # IPv4 地址
    ipv4_pattern = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    
    # IPv6 地址
    ipv6_pattern = r'^([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])$'
    
    return bool(re.match(ipv4_pattern, ip)) or bool(re.match(ipv6_pattern, ip))


def is_valid_github_username(username: str) -> bool:
    """
    检查 GitHub 用户名是否合法
    
    Args:
        username: GitHub 用户名
    
    Returns:
        GitHub 用户名是否合法
    """
    pattern = r'^[a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38}$'
    return bool(re.match(pattern, username))


def is_domain_available(domain: str, subdomain: str, domains_dir: str = None) -> bool:
    """
    检查子域名是否可用
    
    Args:
        domain: 主域名
        subdomain: 子域名
        domains_dir: 域名目录路径 (可选，默认为项目根目录下的 domains/)
    
    Returns:
        子域名是否可用
    """
    if domains_dir is None:
        domains_dir = os.path.join(os.path.dirname(__file__), '../../domains')
    
    domain_dir = os.path.join(domains_dir, domain)
    
    # 检查子域名文件是否存在
    return not os.path.exists(os.path.join(domain_dir, f"{subdomain}.json"))


def is_reserved_subdomain(subdomain: str, config: Dict[str, Any]) -> bool:
    """
    检查子域名是否为保留子域名
    
    Args:
        subdomain: 子域名名称
        config: 项目配置信息
    
    Returns:
        是否为保留子域名
    """
    reserved_subdomains = config.get('reserved_subdomains', [])
    return subdomain.lower() in [r.lower() for r in reserved_subdomains]


def validate_record(record: Dict[str, Any], config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    验证 DNS 记录
    
    Args:
        record: 记录信息
        config: 项目配置信息
    
    Returns:
        (是否有效, 错误信息列表)
    """
    errors = []
    
    # 检查必填字段
    required_fields = ['type', 'name', 'content', 'ttl']
    for field in required_fields:
        if field not in record:
            errors.append(f"缺少必填字段 '{field}'")
    
    # 如果缺少必填字段，直接返回
    if errors:
        return False, errors
    
    # 验证记录类型
    if record['type'] not in config.get('record_types', []):
        errors.append(f"不支持的记录类型 '{record['type']}'，支持的类型: {', '.join(config.get('record_types', []))}")
    
    # 验证名称
    if not is_valid_domain_name(record['name']):
        errors.append(f"无效的记录名称 '{record['name']}'")
    
    # 验证 TTL
    if not isinstance(record['ttl'], int) or record['ttl'] < 60 or record['ttl'] > 86400:
        errors.append(f"无效的 TTL 值 '{record['ttl']}'，必须为 60~86400 之间的整数")
    
    # 验证 proxied 字段
    if 'proxied' in record and not isinstance(record['proxied'], bool):
        errors.append(f"无效的 proxied 值 '{record['proxied']}'，必须为布尔值")
    
    # 根据记录类型验证内容
    if record['type'] == 'A':
        if not is_valid_ip(record['content']):
            errors.append(f"无效的 A 记录 IP 地址 '{record['content']}'")
    
    elif record['type'] == 'AAAA':
        if not is_valid_ip(record['content']):
            errors.append(f"无效的 AAAA 记录 IPv6 地址 '{record['content']}'")
    
    elif record['type'] == 'CNAME':
        # CNAME 记录应该是有效的域名或 URL
        if not record['content'].endswith('.') and not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-\.]{0,253}[a-zA-Z0-9])?$', record['content']):
            errors.append(f"无效的 CNAME 记录目标 '{record['content']}'")
    
    elif record['type'] == 'MX':
        # MX 记录需要优先级字段
        if 'priority' not in record:
            errors.append("MX 记录缺少 'priority' 字段")
        elif not isinstance(record['priority'], int) or record['priority'] < 0 or record['priority'] > 65535:
            errors.append(f"无效的 MX 优先级值 '{record['priority']}'，必须为 0~65535 之间的整数")
    
    return len(errors) == 0, errors


def validate_domain_config(file_path: str, config: Optional[Dict[str, Any]] = None) -> Tuple[bool, List[str]]:
    """
    验证域名配置文件
    
    Args:
        file_path: 配置文件路径
        config: 项目配置信息 (可选)
    
    Returns:
        (是否有效, 错误信息列表)
    """
    errors = []
    
    # 加载项目配置
    if config is None:
        try:
            config = load_config()
        except Exception as e:
            return False, [str(e)]
    
    # 加载配置文件
    domain_config, error = load_json_file(file_path)
    if error:
        return False, [error]
    
    # 检查 owner 部分
    if 'owner' not in domain_config:
        errors.append("缺少 'owner' 部分")
    else:
        owner = domain_config['owner']
        
        # 检查必填字段
        owner_required_fields = ['name', 'github', 'email']
        for field in owner_required_fields:
            if field not in owner:
                errors.append(f"缺少所有者必填字段 '{field}'")
        
        # 验证 GitHub 用户名
        if 'github' in owner and not is_valid_github_username(owner['github']):
            errors.append(f"无效的 GitHub 用户名 '{owner['github']}'")
        
        # 验证邮箱
        if 'email' in owner and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', owner['email']):
            errors.append(f"无效的邮箱地址 '{owner['email']}'")
    
    # 检查 records 部分
    if 'records' not in domain_config:
        errors.append("缺少 'records' 部分")
    else:
        records = domain_config['records']
        
        # 检查记录数量
        max_records = config.get('max_records_per_subdomain', 10)
        if len(records) > max_records:
            errors.append(f"记录数量超过限制 ({len(records)} > {max_records})")
        
        # 验证每条记录
        for i, record in enumerate(records):
            valid, record_errors = validate_record(record, config)
            if not valid:
                for error in record_errors:
                    errors.append(f"记录 #{i+1}: {error}")
    
    return len(errors) == 0, errors


def validate_pull_request(pr_files: List[str], config: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, List[str]]]:
    """
    验证 Pull Request 中的文件
    
    Args:
        pr_files: Pull Request 中的文件路径列表
        config: 项目配置信息 (可选)
    
    Returns:
        (是否所有文件有效, {文件路径: 错误信息列表})
    """
    all_valid = True
    results = {}
    
    # 加载项目配置
    if config is None:
        try:
            config = load_config()
        except Exception as e:
            # 如果配置加载失败，为所有文件返回错误
            for file_path in pr_files:
                results[file_path] = [f"无法加载项目配置: {str(e)}"]
            return False, results
    
    # 检查每个文件
    for file_path in pr_files:
        # 获取原始文件路径用于显示
        display_path = file_path
        
        # 1. 检查文件路径格式是否正确
        path_errors = validate_file_path_format(file_path)
        if path_errors:
            results[display_path] = path_errors
            all_valid = False
            continue
        
        # 2. 检查文件是否存在
        if not os.path.exists(file_path):
            results[display_path] = [f"文件不存在: {file_path}"]
            all_valid = False
            continue
        
        # 3. 检查文件是否为空
        try:
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                results[display_path] = ["文件为空，请添加有效的 JSON 配置"]
                all_valid = False
                continue
            elif file_size > 10 * 1024:  # 10KB 限制
                results[display_path] = [f"文件过大 ({file_size} 字节)，域名配置文件应小于 10KB"]
                all_valid = False
                continue
        except Exception as e:
            results[display_path] = [f"无法读取文件信息: {str(e)}"]
            all_valid = False
            continue
        
        # 4. 预检查文件内容是否为有效 JSON
        json_valid, json_error = validate_json_format(file_path)
        if not json_valid:
            results[display_path] = [json_error]
            all_valid = False
            continue
        
        # 规范化路径分隔符
        normalized_path = file_path.replace('\\', '/')
        
        # 检查文件是否在域名目录下 - 修复路径检查逻辑
        if '/domains/' not in normalized_path and '\\domains\\' not in file_path:
            results[display_path] = ["文件必须位于 domains/ 目录下"]
            all_valid = False
            continue
        
        # 提取主域名和子域名 - 修复路径分割逻辑
        try:
            # 尝试不同的路径分割方式
            if '/domains/' in normalized_path:
                parts = normalized_path.split('/domains/')[1].split('/')
            elif '\\domains\\' in file_path:
                parts = file_path.split('\\domains\\')[1].split('\\')
            else:
                # 兜底逻辑：查找 domains 目录
                path_parts = normalized_path.split('/')
                if 'domains' in path_parts:
                    domains_index = path_parts.index('domains')
                    if domains_index + 2 < len(path_parts):
                        parts = path_parts[domains_index + 1:domains_index + 3]
                    else:
                        raise IndexError("路径格式不正确")
                else:
                    raise IndexError("未找到 domains 目录")
            
            if len(parts) != 2:
                results[display_path] = ["无效的文件路径，应为 domains/domain/subdomain.json"]
                all_valid = False
                continue
        except (IndexError, ValueError) as e:
            results[display_path] = [f"无效的文件路径格式: {str(e)}"]
            all_valid = False
            continue
        
        domain, filename = parts
        
        # 检查域名是否在配置中
        domain_config = None
        for d in config.get('domains', []):
            if d.get('name') == domain:
                domain_config = d
                break
        
        if domain_config is None:
            results[display_path] = [f"不支持的域名 '{domain}'"]
            all_valid = False
            continue
        
        # 检查域名是否已启用
        if not domain_config.get('enabled', False):
            results[display_path] = [f"域名 '{domain}' 未开放申请"]
            all_valid = False
            continue
        
        # 检查文件名是否符合规则
        if not filename.endswith('.json'):
            results[display_path] = ["文件必须是 JSON 格式 (.json 扩展名)"]
            all_valid = False
            continue
        
        subdomain = filename[:-5]  # 去除 .json 后缀
        
        # 检查是否为保留子域名
        if is_reserved_subdomain(subdomain, config):
            results[display_path] = [f"子域名 '{subdomain}' 是保留子域名，不允许申请。保留子域名列表: {', '.join(config.get('reserved_subdomains', []))}"]
            all_valid = False
            continue
        
        # 验证子域名
        if not is_valid_domain_name(subdomain):
            results[display_path] = [f"无效的子域名 '{subdomain}'"]
            all_valid = False
            continue
        
        # 验证配置文件内容
        try:
            valid, errors = validate_domain_config(file_path, config)
            if not valid:
                results[display_path] = errors
                all_valid = False
                continue
        except Exception as e:
            results[display_path] = [f"验证配置文件时出错: {str(e)}"]
            all_valid = False
            continue
        
        # 检查子域名是否可用 (仅当文件不是现有文件时)
        # 注意：这里跳过可用性检查，因为 PR 可能是更新现有文件
        
        # 如果没有错误，添加一个空列表
        if display_path not in results:
            results[display_path] = []
    
    return all_valid, results


def validate_file_path_format(file_path: str) -> List[str]:
    """
    验证文件路径格式
    
    Args:
        file_path: 文件路径
    
    Returns:
        错误信息列表，如果为空则表示路径格式正确
    """
    errors = []
    
    # 规范化路径
    normalized_path = file_path.replace('\\', '/')
    
    # 1. 检查是否在 domains 目录下
    if '/domains/' not in normalized_path:
        errors.append("文件必须位于 domains/ 目录下")
        return errors
    
    # 2. 提取路径部分
    try:
        path_after_domains = normalized_path.split('/domains/')[1]
        path_parts = path_after_domains.split('/')
        
        if len(path_parts) != 2:
            errors.append("文件路径格式错误，应为: domains/{domain}/{subdomain}.json")
            return errors
        
        domain_name, filename = path_parts
        
        # 3. 检查域名部分
        if not domain_name:
            errors.append("域名部分不能为空")
        elif not domain_name.replace('.', '').replace('-', '').isalnum():
            errors.append(f"域名 '{domain_name}' 包含无效字符")
        
        # 4. 检查文件名
        if not filename:
            errors.append("文件名不能为空")
        elif not filename.endswith('.json'):
            errors.append("文件必须是 JSON 格式 (.json 扩展名)")
        elif filename == '.json':
            errors.append("文件名不能仅为 .json")
        else:
            # 检查子域名部分
            subdomain = filename[:-5]  # 去除 .json 后缀
            if not subdomain:
                errors.append("子域名不能为空")
            elif len(subdomain) < 3:
                errors.append("子域名长度至少为 3 个字符")
            elif len(subdomain) > 63:
                errors.append("子域名长度不能超过 63 个字符")
            elif not subdomain.replace('-', '').isalnum():
                errors.append(f"子域名 '{subdomain}' 只能包含字母、数字和连字符")
            elif subdomain.startswith('-') or subdomain.endswith('-'):
                errors.append(f"子域名 '{subdomain}' 不能以连字符开头或结尾")
    
    except Exception as e:
        errors.append(f"解析文件路径时出错: {str(e)}")
    
    return errors


def validate_json_format(file_path: str) -> Tuple[bool, str]:
    """
    验证文件是否为有效的 JSON 格式
    
    Args:
        file_path: 文件路径
    
    Returns:
        (是否有效, 错误信息)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        # 检查文件是否为空
        if not content:
            return False, "文件内容为空，请添加有效的 JSON 配置"
        
        # 检查是否以 { 开头和 } 结尾
        if not (content.startswith('{') and content.endswith('}')):
            return False, "JSON 文件必须以 { 开头，以 } 结尾"
        
        # 尝试解析 JSON
        json.loads(content)
        return True, ""
        
    except json.JSONDecodeError as e:
        error_msg = f"JSON 格式错误: {str(e)}"
        if hasattr(e, 'lineno') and hasattr(e, 'colno'):
            error_msg += f" (第 {e.lineno} 行，第 {e.colno} 列)"
        
        # 提供常见错误的修复建议
        if "Expecting ',' delimiter" in str(e):
            error_msg += "\n💡 提示: 可能缺少逗号分隔符，请检查 JSON 对象中的字段是否用逗号正确分隔"
        elif "Expecting ':' delimiter" in str(e):
            error_msg += "\n💡 提示: 可能缺少冒号，请检查键值对格式是否正确"
        elif "Expecting value" in str(e):
            error_msg += "\n💡 提示: 可能有多余的逗号或缺少值"
        elif "Unterminated string" in str(e):
            error_msg += "\n💡 提示: 字符串未正确闭合，请检查引号是否匹配"
        elif "Expecting property name" in str(e):
            error_msg += "\n💡 提示: 属性名必须用双引号包围"
        
        return False, error_msg
        
    except UnicodeDecodeError:
        return False, "文件编码错误，请使用 UTF-8 编码保存文件"
    except Exception as e:
        return False, f"读取文件时出错: {str(e)}"


def main():
    """命令行入口点"""
    import argparse
    
    parser = argparse.ArgumentParser(description='域名配置验证工具')
    parser.add_argument('file', nargs='+', help='要验证的配置文件路径')
    parser.add_argument('--config', help='配置文件路径')
    
    args = parser.parse_args()
    
    # 加载项目配置
    config = load_config(args.config) if args.config else None
    
    # 验证所有文件
    all_valid = True
    for file_path in args.file:
        print(f"验证 {file_path}...")
        valid, errors = validate_domain_config(file_path, config)
        
        if valid:
            print("✓ 验证通过")
        else:
            print("✗ 验证失败:")
            for error in errors:
                print(f"  - {error}")
            all_valid = False
    
    return 0 if all_valid else 1


if __name__ == "__main__":
    sys.exit(main())
