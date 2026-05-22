#!/usr/bin/env python3
"""
阡陌居自动签到脚本 - GitHub Actions 版本
支持签到和领取每日威望红包
"""

import requests
import re
import time
import os
import sys
from datetime import datetime, timezone, timedelta

# 配置
BASE_URL = "https://www.1000qm.vip"
TASK_ID = "1"  # 如果领取失败，可以尝试改为 "2" 或 "3"

# 北京时间时区 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))

def get_beijing_time():
    """获取北京时间"""
    return datetime.now(BEIJING_TZ)

class QM1000Sign:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        })
        self.set_cookies()
    
    def set_cookies(self):
        """从环境变量设置Cookie"""
        cookie_str = os.environ.get('QM1000_COOKIE', '')
        if not cookie_str:
            print("❌ 未设置 QM1000_COOKIE 环境变量")
            return
        
        for cookie in cookie_str.split(';'):
            cookie = cookie.strip()
            if '=' in cookie:
                key, value = cookie.split('=', 1)
                self.session.cookies.set(key, value, domain='.1000qm.vip')
        
        print("✅ Cookie 已加载")
    
    def log(self, msg, level="INFO"):
        """打印带时间戳的日志（使用北京时间）"""
        timestamp = get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] [{level}] {msg}")
        sys.stdout.flush()
    
    def send_telegram(self, message):
        """发送Telegram通知（使用北京时间）"""
        token = os.environ.get('TG_BOT_TOKEN')
        user_id = os.environ.get('TG_USER_ID')
        
        if not token or not user_id:
            self.log("未配置TG通知，跳过", "WARN")
            return
        
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            # 使用北京时间
            beijing_now = get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')
            data = {
                'chat_id': user_id,
                'text': f"🏮 阡陌居签到\n{message}\n{beijing_now} (北京时间)",
                'parse_mode': 'HTML'
            }
            resp = requests.post(url, json=data, timeout=10)
            if resp.status_code == 200:
                self.log("TG通知发送成功")
            else:
                self.log(f"TG通知发送失败: {resp.text}", "ERROR")
        except Exception as e:
            self.log(f"TG通知异常: {e}", "ERROR")
    
    def check_login(self):
        """检查登录状态"""
        try:
            resp = self.session.get(f"{BASE_URL}/home.php?mod=spacecp", timeout=15)
            if '退出' in resp.text or 'logout' in resp.text:
                self.log("登录状态有效")
                return True
            else:
                self.log("登录状态无效，Cookie可能已过期", "ERROR")
                return False
        except Exception as e:
            self.log(f"登录检查失败: {e}", "ERROR")
            return False
    
    def get_formhash(self, url=None):
        """从页面获取formhash"""
        if url is None:
            url = f"{BASE_URL}/home.php?mod=task"
        try:
            resp = self.session.get(url, timeout=15)
            match = re.search(r'name="formhash" value="([a-f0-9]+)"', resp.text)
            if match:
                return match.group(1)
        except Exception as e:
            self.log(f"获取formhash失败: {e}", "ERROR")
        return None
    
    def sign(self):
        """签到"""
        self.log("开始签到流程...")
        
        try:
            # 获取签到页面
            sign_url = f"{BASE_URL}/plugin.php?id=dsu_paulsign:sign"
            resp = self.session.get(sign_url, timeout=15)
            
            # 获取formhash
            formhash = self.get_formhash(sign_url)
            if not formhash:
                return "❌ 获取formhash失败"
            
            # 提交签到
            post_url = f"{BASE_URL}/plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1&sign_as=1&inajax=1"
            data = {
                'formhash': formhash,
                'qdxq': 'kx',
                'qdmode': '2',
                'todaysay': '',
                'fastreply': '0'
            }
            headers = {'X-Requested-With': 'XMLHttpRequest'}
            
            resp = self.session.post(post_url, data=data, headers=headers, timeout=15)
            
            if '成功' in resp.text:
                credit_match = re.search(r'获得(\d+)点(\w+)', resp.text)
                if credit_match:
                    return f"✅ 签到成功 +{credit_match.group(1)}{credit_match.group(2)}"
                return "✅ 签到成功"
            elif '已经签到' in resp.text:
                return "ℹ️ 今日已签到"
            else:
                self.log(f"签到响应: {resp.text[:200]}", "DEBUG")
                return "❌ 签到失败"
                
        except Exception as e:
            self.log(f"签到异常: {e}", "ERROR")
            return "❌ 签到异常"
    
    def packet(self):
        """领取威望红包 - API直接调用版"""
        self.log("开始领取威望红包...")
        
        # 先获取formhash
        formhash = self.get_formhash()
        if not formhash:
            return "❌ 获取formhash失败"
        self.log(f"获取到formhash: {formhash[:8]}...")
        
        try:
            # 方法1：直接调用apply接口
            self.log("尝试直接申请任务...")
            apply_url = f"{BASE_URL}/home.php?mod=task&do=apply&id={TASK_ID}"
            apply_data = {
                'formhash': formhash,
                'applysubmit': 'yes'
            }
            
            apply_resp = self.session.post(apply_url, data=apply_data, timeout=15)
            self.log(f"申请响应长度: {len(apply_resp.text)}")
            
            # 检查申请结果
            if '申请成功' in apply_resp.text or 'success' in apply_resp.text.lower():
                self.log("✅ 任务申请成功，等待2秒...")
                time.sleep(2)
                
                # 申请成功后立即领取
                draw_url = f"{BASE_URL}/home.php?mod=task&do=draw&id={TASK_ID}"
                draw_data = {
                    'formhash': formhash,
                    'drawsubmit': 'yes'
                }
                draw_resp = self.session.post(draw_url, data=draw_data, timeout=15)
                
                if '成功' in draw_resp.text:
                    # 尝试提取威望数量
                    point_match = re.search(r'威望\s*([+-]?\d+)', draw_resp.text)
                    if point_match:
                        return f"✅ 领取成功 +{point_match.group(1)}威望"
                    return "✅ 领取成功"
                elif '已完成' in draw_resp.text or '已领取' in draw_resp.text:
                    return "ℹ️ 今日红包已领取"
                else:
                    self.log(f"领取响应: {draw_resp.text[:200]}")
                    return "❌ 申请成功但领取失败"
                    
            elif '已申请' in apply_resp.text or '已领取' in apply_resp.text or '已完成' in apply_resp.text:
                self.log("任务已申请过，尝试直接领取...")
                
                # 直接尝试领取
                draw_url = f"{BASE_URL}/home.php?mod=task&do=draw&id={TASK_ID}"
                draw_data = {
                    'formhash': formhash,
                    'drawsubmit': 'yes'
                }
                draw_resp = self.session.post(draw_url, data=draw_data, timeout=15)
                
                if '成功' in draw_resp.text:
                    point_match = re.search(r'威望\s*([+-]?\d+)', draw_resp.text)
                    if point_match:
                        return f"✅ 领取成功 +{point_match.group(1)}威望"
                    return "✅ 领取成功"
                elif '已完成' in draw_resp.text or '已领取' in draw_resp.text:
                    return "ℹ️ 今日红包已领取"
                else:
                    return "❌ 领取失败"
            else:
                # 检查是否已经完成
                check_url = f"{BASE_URL}/home.php?mod=task&do=view&id={TASK_ID}"
                check_resp = self.session.get(check_url, timeout=15)
                if '已完成' in check_resp.text or '完成于' in check_resp.text:
                    return "ℹ️ 今日红包已领取"
                else:
                    self.log(f"申请失败响应: {apply_resp.text[:300]}")
                    return "❌ 申请失败"
                    
        except Exception as e:
            self.log(f"红包处理异常: {e}", "ERROR")
            import traceback
            self.log(traceback.format_exc(), "ERROR")
            return "❌ 处理异常"
    
    def run(self):
        """主运行函数"""
        self.log("=" * 50)
        self.log("阡陌居自动签到脚本启动")
        self.log("=" * 50)
        
        # 检查登录状态
        if not self.check_login():
            error_msg = "登录失败，请检查Cookie配置"
            self.log(error_msg, "ERROR")
            self.send_telegram(f"❌ {error_msg}")
            sys.exit(1)
        
        # 执行签到
        sign_result = self.sign()
        self.log(f"签到结果: {sign_result}")
        
        # 等待2秒
        time.sleep(2)
        
        # 领取红包
        packet_result = self.packet()
        self.log(f"红包结果: {packet_result}")
        
        # 汇总结果
        summary = f"签到: {sign_result}\n红包: {packet_result}"
        self.log(f"\n最终结果:\n{summary}")
        self.log("=" * 50)
        
        # 发送通知
        self.send_telegram(summary)
        
        # 返回状态码 - 接受成功或已领取的情况
        sign_ok = '✅' in sign_result or 'ℹ️' in sign_result
        packet_ok = '✅' in packet_result or 'ℹ️' in packet_result
        
        if sign_ok and packet_ok:
            sys.exit(0)
        else:
            sys.exit(1)


def main():
    signer = QM1000Sign()
    signer.run()


if __name__ == "__main__":
    main()
