#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
域名健康检查模块

此模块提供了检查域名健康状态的功能。
"""

import json
import os
import socket
import sys
import time
import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Any, Optional, Tuple
import ipaddress
import requests

# 添加项目根目录到 Python 路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

try:
    from scripts.utils.common import load_json_file
except ImportError:
    # 如果导入失败，使用内联版本
    def load_json_file(file_path: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f), None
        except json.JSONDecodeError as e:
            error_msg = f"JSON 格式错误: {str(e)}"
            return None, error_msg
        except FileNotFoundError:
            return None, f"文件不存在: {file_path}"
        except Exception as e:
            return None, f"读取文件错误: {str(e)}"


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


def get_domain_files(domain: str, domains_dir: str = None) -> List[str]:
    """
    获取域名目录下的所有 JSON 文件
    
    Args:
        domain: 域名
        domains_dir: 域名目录路径 (可选，默认为项目根目录下的 domains/)
    
    Returns:
        文件路径列表
    """
    if domains_dir is None:
        domains_dir = os.path.join(os.path.dirname(__file__), '../../domains')
    
    domain_dir = os.path.join(domains_dir, domain)
    
    if not os.path.isdir(domain_dir):
        return []
    
    # 排除示例文件和保留文件
    excluded_files = ['example.json', 'template.json', '.example.json']
    return [os.path.join(domain_dir, f) for f in os.listdir(domain_dir) 
            if f.endswith('.json') and f not in excluded_files]


def load_domain_config(file_path: str) -> Optional[Dict[str, Any]]:
    """
    加载域名配置文件
    
    Args:
        file_path: 配置文件路径
    
    Returns:
        配置信息字典，如果加载失败则为 None
    """
    data, error = load_json_file(file_path)
    return data  # 返回 None 如果加载失败


def get_record_fqdn(domain: str, subdomain: str, record: Dict[str, Any]) -> str:
    """
    获取记录的完整域名
    
    Args:
        domain: 主域名
        subdomain: 子域名
        record: 记录信息
    
    Returns:
        完整域名
    """
    name = record.get('name', '@')
    
    if name == '@':
        if subdomain == '@':
            return domain
        return f"{subdomain}.{domain}"
    else:
        if subdomain == '@':
            return f"{name}.{domain}"
        return f"{name}.{subdomain}.{domain}"


# Cloudflare IP 地址范围
CLOUDFLARE_IPV4_RANGES = [
    '103.21.244.0/22',
    '103.22.200.0/22',
    '103.31.4.0/22',
    '104.16.0.0/13',
    '104.24.0.0/14',
    '108.162.192.0/18',
    '131.0.72.0/22',
    '141.101.64.0/18',
    '162.158.0.0/15',
    '172.64.0.0/13',
    '173.245.48.0/20',
    '188.114.96.0/20',
    '190.93.240.0/20',
    '197.234.240.0/22',
    '198.41.128.0/17'
]

CLOUDFLARE_IPV6_RANGES = [
    '2400:cb00::/32',
    '2606:4700::/32',
    '2803:f800::/32',
    '2405:b500::/32',
    '2405:8100::/32',
    '2a06:98c0::/29',
    '2c0f:f248::/32'
]


def is_cloudflare_ip(ip: str) -> bool:
    """
    检查 IP 地址是否属于 Cloudflare
    
    Args:
        ip: IP 地址字符串
    
    Returns:
        如果是 Cloudflare IP 则返回 True
    """
    try:
        ip_obj = ipaddress.ip_address(ip)
        
        # 检查 IPv4 范围
        if ip_obj.version == 4:
            for cidr in CLOUDFLARE_IPV4_RANGES:
                if ip_obj in ipaddress.ip_network(cidr):
                    return True
        
        # 检查 IPv6 范围
        elif ip_obj.version == 6:
            for cidr in CLOUDFLARE_IPV6_RANGES:
                if ip_obj in ipaddress.ip_network(cidr):
                    return True
        
        return False
    except ValueError:
        return False


def resolve_cname_final(domain: str) -> str:
    """
    解析 CNAME 记录的最终目标域名
    
    Args:
        domain: 域名
    
    Returns:
        最终目标域名
    """
    try:
        # 使用 socket.getfqdn 来获取完全限定域名
        fqdn = socket.getfqdn(domain)
        return fqdn
    except Exception:
        return domain


def check_dns_record(domain: str, subdomain: str, record: Dict[str, Any]) -> Dict[str, Any]:
    """
    检查 DNS 记录的健康状态
    
    Args:
        domain: 主域名
        subdomain: 子域名
        record: 记录信息
    
    Returns:
        检查结果
    """
    fqdn = get_record_fqdn(domain, subdomain, record)
    record_type = record.get('type')
    expected_content = record.get('content')
    proxied = record.get('proxied', False)  # 是否使用 Cloudflare 代理
    
    result = {
        'fqdn': fqdn,
        'type': record_type,
        'expected': expected_content,
        'actual': None,
        'status': 'unknown',
        'error': None,
        'latency': None,
        'proxied': proxied
    }
    
    try:
        start_time = time.time()
        
        if record_type == 'A':
            # 检查 A 记录
            try:
                answers = socket.gethostbyname_ex(fqdn)[2]
                result['actual'] = answers
                
                if proxied:
                    # 如果使用了 Cloudflare 代理，检查是否返回 Cloudflare IP
                    cloudflare_ips = [ip for ip in answers if is_cloudflare_ip(ip)]
                    if cloudflare_ips:
                        result['status'] = 'ok'
                        result['actual'] = cloudflare_ips + [f"(代理: {len(cloudflare_ips)} Cloudflare IPs)"]
                    else:
                        # 仍然检查是否匹配预期值
                        if expected_content in answers:
                            result['status'] = 'ok'
                        else:
                            result['status'] = 'mismatch'
                else:
                    # 不使用代理，直接比较
                    if expected_content in answers:
                        result['status'] = 'ok'
                    else:
                        result['status'] = 'mismatch'
            except socket.gaierror as e:
                result['error'] = f"DNS 解析错误: {str(e)}"
                result['status'] = 'error'
        
        elif record_type == 'AAAA':
            # IPv6 记录需要特殊处理
            try:
                # 使用 socket.getaddrinfo 获取 IPv6 地址
                infos = socket.getaddrinfo(fqdn, None, socket.AF_INET6)
                ipv6_addresses = [info[4][0] for info in infos]
                result['actual'] = ipv6_addresses
                
                if proxied:
                    # 如果使用了 Cloudflare 代理，检查是否返回 Cloudflare IPv6
                    cloudflare_ips = [ip for ip in ipv6_addresses if is_cloudflare_ip(ip)]
                    if cloudflare_ips:
                        result['status'] = 'ok'
                        result['actual'] = cloudflare_ips + [f"(代理: {len(cloudflare_ips)} Cloudflare IPv6s)"]
                    else:
                        if expected_content in ipv6_addresses:
                            result['status'] = 'ok'
                        else:
                            result['status'] = 'mismatch'
                else:
                    if expected_content in ipv6_addresses:
                        result['status'] = 'ok'
                    else:
                        result['status'] = 'mismatch'
            except socket.gaierror as e:
                result['error'] = f"DNS 解析错误: {str(e)}"
                result['status'] = 'error'
        
        elif record_type == 'CNAME':
            # 检查 CNAME 记录
            try:
                if proxied:
                    # 如果使用了 Cloudflare 代理，检查最终解析结果
                    final_domain = resolve_cname_final(fqdn)
                    result['actual'] = final_domain
                    
                    # 检查是否能解析到 IP（表示 CNAME 工作正常）
                    try:
                        ips = socket.gethostbyname_ex(fqdn)[2]
                        cloudflare_ips = [ip for ip in ips if is_cloudflare_ip(ip)]
                        if cloudflare_ips:
                            result['status'] = 'ok'
                            result['actual'] = [final_domain, f"(代理: {len(cloudflare_ips)} Cloudflare IPs)"]
                        else:
                            result['status'] = 'ok'  # 能解析就认为是正常的
                    except socket.gaierror:
                        result['status'] = 'mismatch'
                else:
                    # 不使用代理，直接比较 CNAME
                    cname = socket.gethostbyname_ex(fqdn)[0]
                    result['actual'] = cname
                    
                    # 简化比较，不考虑尾部的点
                    expected = expected_content[:-1] if expected_content.endswith('.') else expected_content
                    actual = cname[:-1] if cname.endswith('.') else cname
                    
                    if expected in actual or actual in expected:
                        result['status'] = 'ok'
                    else:
                        result['status'] = 'mismatch'
            except socket.gaierror as e:
                result['error'] = f"DNS 解析错误: {str(e)}"
                result['status'] = 'error'
        
        elif record_type == 'TXT':
            # TXT 记录通常用于验证域名所有权
            try:
                import subprocess
                result_cmd = subprocess.run(['nslookup', '-type=TXT', fqdn], 
                                          capture_output=True, text=True, timeout=10)
                if result_cmd.returncode == 0:
                    output = result_cmd.stdout
                    result['actual'] = ['TXT records found']
                    if expected_content.lower() in output.lower():
                        result['status'] = 'ok'
                    else:
                        result['status'] = 'mismatch'
                        result['actual'] = [f"TXT found but not matching: {expected_content}"]
                else:
                    result['status'] = 'error'
                    result['error'] = f"TXT 记录查询失败: {result_cmd.stderr}"
            except Exception as e:
                result['error'] = f"TXT 记录检查错误: {str(e)}"
                result['status'] = 'error'
        
        elif record_type == 'MX':
            # 检查 MX 记录
            try:
                import subprocess
                result_cmd = subprocess.run(['nslookup', '-type=MX', fqdn], 
                                          capture_output=True, text=True, timeout=10)
                if result_cmd.returncode == 0:
                    output = result_cmd.stdout.lower()
                    if 'mail exchanger' in output or expected_content.lower() in output:
                        result['status'] = 'ok'
                        result['actual'] = ['MX records found']
                    else:
                        result['status'] = 'mismatch'
                        result['actual'] = ['No matching MX records']
                else:
                    result['status'] = 'error'
                    result['error'] = f"MX 记录查询失败: {result_cmd.stderr}"
            except Exception as e:
                result['error'] = f"MX 记录检查错误: {str(e)}"
                result['status'] = 'error'
        
        # 计算延迟
        result['latency'] = round((time.time() - start_time) * 1000)  # 毫秒
        
        # 对于 HTTP(S) 站点进行额外检查
        if record_type in ['A', 'AAAA', 'CNAME'] and result['status'] == 'ok':
            try:
                http_url = f"http://{fqdn}"
                https_url = f"https://{fqdn}"
                
                # 首先尝试 HTTPS
                try:
                    https_response = requests.get(https_url, timeout=5, allow_redirects=True)
                    result['http_status'] = https_response.status_code
                    result['http_latency'] = https_response.elapsed.total_seconds() * 1000
                    result['http_url'] = https_url
                except requests.exceptions.RequestException:
                    # 如果 HTTPS 失败，尝试 HTTP
                    try:
                        http_response = requests.get(http_url, timeout=5, allow_redirects=True)
                        result['http_status'] = http_response.status_code
                        result['http_latency'] = http_response.elapsed.total_seconds() * 1000
                        result['http_url'] = http_url
                    except requests.exceptions.RequestException:
                        # 两者都失败，不添加 HTTP 相关信息
                        pass
            except Exception as e:
                # 忽略 HTTP 检查错误，这不影响 DNS 记录的健康状态
                pass
        
        return result
        
    except Exception as e:
        result['error'] = f"检查错误: {str(e)}"
        result['status'] = 'error'
        return result


def check_domain_health(domain: str, subdomain: str, config: Dict[str, Any], timeout: int = 5) -> Dict[str, Any]:
    """
    检查子域名的健康状态
    
    Args:
        domain: 主域名
        subdomain: 子域名
        config: 子域名配置
        timeout: 超时时间 (秒)
    
    Returns:
        健康状态信息
    """
    result = {
        'domain': domain,
        'subdomain': subdomain,
        'owner': config.get('owner', {}),
        'records': [],
        'status': 'unknown',
        'errors': 0,
        'check_time': datetime.datetime.now().isoformat()
    }
    
    records = config.get('records', [])
    
    # 使用线程池并行检查所有记录
    with ThreadPoolExecutor(max_workers=min(10, len(records) or 1)) as executor:
        check_futures = []
        
        for record in records:
            future = executor.submit(check_dns_record, domain, subdomain, record)
            check_futures.append(future)
        
        # 收集结果
        for future in check_futures:
            try:
                record_result = future.result(timeout=timeout)
                result['records'].append(record_result)
                if record_result['status'] == 'error':
                    result['errors'] += 1
            except Exception as e:
                result['records'].append({
                    'status': 'error',
                    'error': f"检查超时或失败: {str(e)}"
                })
                result['errors'] += 1
    
    # 设置整体状态
    if result['errors'] == 0:
        if all(r['status'] == 'ok' for r in result['records']):
            result['status'] = 'healthy'
        elif any(r['status'] == 'mismatch' for r in result['records']):
            result['status'] = 'mismatch'
        else:
            result['status'] = 'partial'
    else:
        if result['errors'] == len(result['records']):
            result['status'] = 'unhealthy'
        else:
            result['status'] = 'degraded'
    
    return result


def generate_health_report(results: List[Dict[str, Any]], config: Dict[str, Any]) -> str:
    """
    生成健康状态报告
    
    Args:
        results: 健康状态结果列表
        config: 项目配置
    
    Returns:
        Markdown 格式的报告
    """
    # 统计数据
    total_domains = len(results)
    status_counts = {
        'healthy': len([r for r in results if r['status'] == 'healthy']),
        'partial': len([r for r in results if r['status'] == 'partial']),
        'degraded': len([r for r in results if r['status'] == 'degraded']),
        'mismatch': len([r for r in results if r['status'] == 'mismatch']),
        'unhealthy': len([r for r in results if r['status'] == 'unhealthy']),
        'unknown': len([r for r in results if r['status'] == 'unknown']),
    }
    
    # 生成报告
    report = []
    report.append("# 域名健康状态报告")
    report.append("")
    report.append(f"**生成时间**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # 添加统计摘要
    report.append("## 统计摘要")
    report.append("")
    report.append(f"- 总域名数: {total_domains}")
    report.append(f"- 健康: {status_counts['healthy']} ({round(status_counts['healthy']/total_domains*100 if total_domains else 0, 1)}%)")
    report.append(f"- 部分健康: {status_counts['partial']} ({round(status_counts['partial']/total_domains*100 if total_domains else 0, 1)}%)")
    report.append(f"- 性能下降: {status_counts['degraded']} ({round(status_counts['degraded']/total_domains*100 if total_domains else 0, 1)}%)")
    report.append(f"- 配置不匹配: {status_counts['mismatch']} ({round(status_counts['mismatch']/total_domains*100 if total_domains else 0, 1)}%)")
    report.append(f"- 不健康: {status_counts['unhealthy']} ({round(status_counts['unhealthy']/total_domains*100 if total_domains else 0, 1)}%)")
    report.append(f"- 未知: {status_counts['unknown']} ({round(status_counts['unknown']/total_domains*100 if total_domains else 0, 1)}%)")
    report.append("")
    
    # 添加图标说明
    report.append("## 状态图标说明")
    report.append("")
    report.append("- ✅ 健康: 所有记录正常")
    report.append("- ⚠️ 部分健康: 部分记录正常，部分未检查")
    report.append("- 🔸 性能下降: 部分记录出错，但仍有记录正常")
    report.append("- ⚡ 配置不匹配: 记录存在但与预期不符")
    report.append("- ❌ 不健康: 所有记录均有错误")
    report.append("- ❓ 未知: 状态未知")
    report.append("")
    
    # 按域名分组
    domains = {}
    for result in results:
        domain = result['domain']
        if domain not in domains:
            domains[domain] = []
        domains[domain].append(result)
    
    # 遍历域名
    for domain, domain_results in domains.items():
        # 获取域名配置
        domain_config = None
        for d in config.get('domains', []):
            if d.get('name') == domain:
                domain_config = d
                break
        
        report.append(f"## {domain}")
        report.append("")
        if domain_config:
            report.append(f"**描述**: {domain_config.get('description', '无')}")
            report.append(f"**状态**: {'启用' if domain_config.get('enabled') else '禁用'}")
        report.append("")
        
        # 创建子域名表格
        report.append("| 子域名 | 状态 | 所有者 | 记录数 | 错误数 | 检查时间 |")
        report.append("|--------|------|-------|--------|--------|----------|")
        
        # 按状态排序: 不健康优先显示
        domain_results.sort(key=lambda r: {
            'unhealthy': 0,
            'mismatch': 1,
            'degraded': 2,
            'partial': 3,
            'unknown': 4,
            'healthy': 5
        }.get(r['status'], 6))
        
        for result in domain_results:
            subdomain = result['subdomain']
            status = result['status']
            owner = result['owner'].get('name', '未知') if result['owner'] else '未知'
            records_count = len(result['records'])
            errors_count = result['errors']
            check_time = datetime.datetime.fromisoformat(result['check_time']).strftime('%H:%M:%S')
            
            # 状态图标
            status_icon = {
                'healthy': '✅',
                'partial': '⚠️',
                'degraded': '🔸',
                'mismatch': '⚡',
                'unhealthy': '❌',
                'unknown': '❓'
            }.get(status, '❓')
            
            report.append(f"| {subdomain} | {status_icon} {status} | {owner} | {records_count} | {errors_count} | {check_time} |")
        
        report.append("")
        
        # 详细记录信息
        for result in domain_results:
            if result['status'] != 'healthy':  # 只显示有问题的域名的详细信息
                subdomain = result['subdomain']
                report.append(f"### {subdomain}.{domain}")
                report.append("")
                report.append("| 记录 | 类型 | 预期值 | 实际值 | 状态 | 延迟 |")
                report.append("|------|------|--------|--------|------|------|")
                
                for record in result['records']:
                    fqdn = record.get('fqdn', '未知')
                    record_type = record.get('type', '未知')
                    expected = record.get('expected', '未知')
                    actual = record.get('actual')
                    if isinstance(actual, list):
                        actual = ', '.join(str(a) for a in actual) if actual else '无'
                    elif actual is None:
                        actual = '无'
                    status = record.get('status', 'unknown')
                    latency = record.get('latency')
                    latency_str = f"{latency}ms" if latency is not None else '未知'
                    
                    # 状态图标
                    status_icon = {
                        'ok': '✅',
                        'mismatch': '⚡',
                        'error': '❌',
                        'unchecked': '⏳',
                        'unknown': '❓'
                    }.get(status, '❓')
                    
                    report.append(f"| {fqdn} | {record_type} | {expected} | {actual} | {status_icon} | {latency_str} |")
                
                # 添加错误信息
                errors = [r['error'] for r in result['records'] if r.get('error')]
                if errors:
                    report.append("")
                    report.append("**错误信息**:")
                    for error in errors:
                        report.append(f"- {error}")
                
                report.append("")
    
    return "\n".join(report)


def print_health_summary(results: List[Dict[str, Any]], config: Dict[str, Any]):
    """
    在控制台输出健康状态摘要
    
    Args:
        results: 健康状态结果列表
        config: 项目配置
    """
    # 统计数据
    total_domains = len(results)
    if total_domains == 0:
        print("📊 没有找到任何域名配置文件")
        return
    
    status_counts = {
        'healthy': len([r for r in results if r['status'] == 'healthy']),
        'partial': len([r for r in results if r['status'] == 'partial']),
        'degraded': len([r for r in results if r['status'] == 'degraded']),
        'mismatch': len([r for r in results if r['status'] == 'mismatch']),
        'unhealthy': len([r for r in results if r['status'] == 'unhealthy']),
        'unknown': len([r for r in results if r['status'] == 'unknown']),
    }
    
    # 打印统计摘要
    print("\n" + "="*60)
    print("📊 域名健康状态报告")
    print("="*60)
    print(f"⏰ 检查时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📈 总域名数: {total_domains}")
    print()
    
    # 状态统计
    print("📋 状态统计:")
    print(f"  ✅ 健康:        {status_counts['healthy']:3d} ({round(status_counts['healthy']/total_domains*100, 1):5.1f}%)")
    print(f"  ⚠️ 部分健康:    {status_counts['partial']:3d} ({round(status_counts['partial']/total_domains*100, 1):5.1f}%)")
    print(f"  🔸 性能下降:    {status_counts['degraded']:3d} ({round(status_counts['degraded']/total_domains*100, 1):5.1f}%)")
    print(f"  ⚡ 配置不匹配:  {status_counts['mismatch']:3d} ({round(status_counts['mismatch']/total_domains*100, 1):5.1f}%)")
    print(f"  ❌ 不健康:      {status_counts['unhealthy']:3d} ({round(status_counts['unhealthy']/total_domains*100, 1):5.1f}%)")
    print(f"  ❓ 未知:        {status_counts['unknown']:3d} ({round(status_counts['unknown']/total_domains*100, 1):5.1f}%)")
    print()
    
    # 按域名分组显示详细信息
    domains = {}
    for result in results:
        domain = result['domain']
        if domain not in domains:
            domains[domain] = []
        domains[domain].append(result)
    
    # 显示有问题的域名
    problem_results = [r for r in results if r['status'] != 'healthy']
    if problem_results:
        print("⚠️ 需要关注的域名:")
        print("-" * 80)
        
        for result in problem_results:
            domain = result['domain']
            subdomain = result['subdomain']
            status = result['status']
            owner = result['owner'].get('name', '未知') if result['owner'] else '未知'
            errors_count = result['errors']
            
            # 状态图标
            status_icon = {
                'partial': '⚠️',
                'degraded': '🔸',
                'mismatch': '⚡',
                'unhealthy': '❌',
                'unknown': '❓'
            }.get(status, '❓')
            
            fqdn = f"{subdomain}.{domain}" if subdomain != '@' else domain
            print(f"{status_icon} {fqdn:<30} | 状态: {status:<10} | 所有者: {owner:<15} | 错误: {errors_count}")
            
            # 显示错误详情
            for record in result['records']:
                if record.get('error'):
                    print(f"    └─ {record.get('fqdn', 'Unknown')}: {record['error']}")
            
            # 显示不匹配的记录
            mismatched_records = [r for r in result['records'] if r.get('status') == 'mismatch']
            for record in mismatched_records:
                expected = record.get('expected', 'Unknown')
                actual = record.get('actual')
                proxied = record.get('proxied', False)
                
                if isinstance(actual, list):
                    actual = ', '.join(str(a) for a in actual) if actual else '无'
                elif actual is None:
                    actual = '无'
                
                proxy_note = " (Cloudflare 代理)" if proxied else ""
                print(f"    └─ {record.get('fqdn', 'Unknown')}: 预期 {expected}, 实际 {actual}{proxy_note}")
        
        print("-" * 80)
        print("💡 提示: 如果使用了 Cloudflare 代理，请在配置文件中添加 'proxied': true")
        print("💡 Cloudflare 代理会返回 Cloudflare 的 IP 地址，这是正常现象")
    else:
        print("🎉 所有域名状态健康!")
    
    # 显示性能统计
    all_latencies = []
    for result in results:
        for record in result['records']:
            if record.get('latency') is not None:
                all_latencies.append(record['latency'])
    
    if all_latencies:
        avg_latency = sum(all_latencies) / len(all_latencies)
        max_latency = max(all_latencies)
        min_latency = min(all_latencies)
        print(f"\n⏱️ DNS 解析性能:")
        print(f"  平均延迟: {avg_latency:.1f}ms")
        print(f"  最大延迟: {max_latency}ms")
        print(f"  最小延迟: {min_latency}ms")
    
    print("="*60)


def main():
    """命令行入口点"""
    import argparse
    
    parser = argparse.ArgumentParser(description='域名健康检查工具')
    parser.add_argument('--config', help='配置文件路径')
    parser.add_argument('--output', help='输出文件路径 (可选，用于生成 Markdown 报告)')
    parser.add_argument('--timeout', type=int, default=10, help='检查超时时间 (秒)')
    parser.add_argument('--domain', help='指定要检查的域名')
    parser.add_argument('--subdomain', help='指定要检查的子域名')
    parser.add_argument('--summary-only', action='store_true', help='只显示摘要信息')
    
    args = parser.parse_args()
    
    # 加载项目配置
    config = load_config(args.config)
    
    all_results = []
    
    # 遍历所有启用的域名
    for domain_config in config.get('domains', []):
        domain = domain_config.get('name')
        
        # 跳过未启用的域名
        if not domain_config.get('enabled', True):
            continue
            
        # 如果指定了域名但不匹配，跳过
        if args.domain and args.domain != domain:
            continue
        
        if not args.summary_only:
            print(f"🔍 检查域名: {domain}")
        
        # 获取域名目录下的所有 JSON 文件
        domain_files = get_domain_files(domain)
        
        for file_path in domain_files:
            subdomain = os.path.basename(file_path)[:-5]  # 去除 .json 后缀
            
            # 如果指定了子域名但不匹配，跳过
            if args.subdomain and args.subdomain != subdomain:
                continue
                
            if not args.summary_only:
                print(f"  📋 检查子域名: {subdomain}")
            
            # 加载子域名配置
            domain_config = load_domain_config(file_path)
            if domain_config is None:
                print(f"    ❌ 无法加载配置文件: {file_path}")
                continue
            
            # 检查健康状态
            result = check_domain_health(domain, subdomain, domain_config, args.timeout)
            all_results.append(result)
            
            # 打印结果状态
            if not args.summary_only:
                status_icon = {
                    'healthy': '✅',
                    'partial': '⚠️',
                    'degraded': '🔸',
                    'mismatch': '⚡',
                    'unhealthy': '❌',
                    'unknown': '❓'
                }.get(result['status'], '❓')
                print(f"    {status_icon} 状态: {result['status']}")
    
    # 显示摘要
    print_health_summary(all_results, config)
    
    # 如果指定了输出文件，生成 Markdown 报告
    if args.output:
        report = generate_health_report(all_results, config)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n📄 详细报告已保存至: {args.output}")
    
    # 返回码: 如果有任何不健康的域名，返回 1
    unhealthy_count = len([r for r in all_results if r['status'] in ['unhealthy', 'mismatch']])
    return 1 if unhealthy_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
