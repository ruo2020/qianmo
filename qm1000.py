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
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 配置
BASE_URL = "https://www.1000qm.vip"
TASK_ID = "1"

# 北京时间时区 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))

def get_beijing_time():
    """获取北京时间"""
    return datetime.now(BEIJING_TZ)

def create_session_with_retry():
    """创建带重试机制的session"""
    session = requests.Session()
    retry = Retry(
        total=3,
        read=3,
        connect=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

class QM1000Sign:
    def __init__(self):
        self.session = create_session_with_retry()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
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
        """检查登录状态 - 增加重试"""
        urls = [
            f"{BASE_URL}/home.php?mod=spacecp",
            f"{BASE_URL}/forum.php",
            f"{BASE_URL}/"
        ]
        
        for i, url in enumerate(urls):
            try:
                self.log(f"尝试连接 ({i+1}/{len(urls)}): {url}")
                resp = self.session.get(url, timeout=30)
                if resp.status_code == 200:
                    if '退出' in resp.text or 'logout' in resp.text or '个人资料' in resp.text:
                        self.log("登录状态有效")
                        return True
                    else:
                        self.log("返回页面未检测到登录状态，继续尝试...")
                else:
                    self.log(f"HTTP状态码: {resp.status_code}")
            except requests.exceptions.Timeout:
                self.log(f"连接超时: {url}", "WARN")
            except requests.exceptions.ConnectionError as e:
                self.log(f"连接错误: {e}", "WARN")
            except Exception as e:
                self.log(f"检查失败: {e}", "WARN")
            
            if i < len(urls) - 1:
                time.sleep(2)
        
        self.log("所有连接尝试均失败，请检查网络或Cookie配置", "ERROR")
        return False
    
    def get_formhash(self, url=None):
        """从页面获取formhash - 增加重试"""
        if url is None:
            url = f"{BASE_URL}/home.php?mod=task"
        
        for attempt in range(3):
            try:
                self.log(f"获取formhash (尝试 {attempt+1}/3)")
                resp = self.session.get(url, timeout=30)
                match = re.search(r'name="formhash" value="([a-f0-9]+)"', resp.text)
                if match:
                    return match.group(1)
            except Exception as e:
                self.log(f"获取formhash失败 (尝试 {attempt+1}): {e}", "WARN")
                if attempt < 2:
                    time.sleep(3)
        return None
    
    def sign(self):
        """签到 - 增加重试"""
        self.log("开始签到流程...")
        
        for attempt in range(3):
            try:
                sign_url = f"{BASE_URL}/plugin.php?id=dsu_paulsign:sign"
                resp = self.session.get(sign_url, timeout=30)
                
                formhash = self.get_formhash(sign_url)
                if not formhash:
                    if attempt < 2:
                        time.sleep(3)
                        continue
                    return "❌ 获取formhash失败"
                
                post_url = f"{BASE_URL}/plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1&sign_as=1&inajax=1"
                data = {
                    'formhash': formhash,
                    'qdxq': 'kx',
                    'qdmode': '2',
                    'todaysay': '',
                    'fastreply': '0'
                }
                headers = {'X-Requested-With': 'XMLHttpRequest'}
                
                resp = self.session.post(post_url, data=data, headers=headers, timeout=30)
                
                if '成功' in resp.text:
                    credit_match = re.search(r'获得(\d+)点(\w+)', resp.text)
                    if credit_match:
                        return f"✅ 签到成功 +{credit_match.group(1)}{credit_match.group(2)}"
                    return "✅ 签到成功"
                elif '已经签到' in resp.text:
                    return "ℹ️ 今日已签到"
                else:
                    if attempt < 2:
                        time.sleep(3)
                        continue
                    return "❌ 签到失败"
                    
            except Exception as e:
                self.log(f"签到异常 (尝试 {attempt+1}/3): {e}", "WARN")
                if attempt < 2:
                    time.sleep(3)
        
        return "❌ 签到异常"
    
    def packet(self):
        """领取威望红包 - 先申请后领取"""
        self.log("开始领取威望红包...")
        
        # 获取formhash
        formhash = self.get_formhash()
        if not formhash:
            return "❌ 获取formhash失败"
        self.log(f"获取到formhash: {formhash[:8]}...")
        
        try:
            # 第一步：访问任务页面，检查状态
            task_url = f"{BASE_URL}/home.php?mod=task&do=view&id={TASK_ID}"
            task_resp = self.session.get(task_url, timeout=30)
            task_text = task_resp.text
            
            # 检查是否已经完成（已领取过）
            if '已完成' in task_text or '完成于' in task_text:
                self.log("检测到任务已完成，今日红包已领取")
                return "ℹ️ 今日红包已领取"
            
            # 第二步：查找并点击"立即申请"
            self.log("查找'立即申请'按钮...")
            
            apply_url = None
            
            # 方式1：匹配完整的a标签
            apply_match = re.search(r'<a href="([^"]+do=apply[^"]+id=' + TASK_ID + r'[^"]*)"[^>]*>立即申请', task_text)
            if apply_match:
                apply_url_part = apply_match.group(1)
                apply_url_part = apply_url_part.replace('&amp;', '&')
                apply_url = f"{BASE_URL}/{apply_url_part}" if not apply_url_part.startswith('http') else apply_url_part
            
            # 方式2：如果没找到，尝试匹配链接片段
            if not apply_url:
                apply_match = re.search(r'do=apply&amp;id=' + TASK_ID + r'&amp;formhash=([a-f0-9]+)', task_text)
                if apply_match:
                    formhash_from_url = apply_match.group(1)
                    apply_url = f"{BASE_URL}/home.php?mod=task&do=apply&id={TASK_ID}&formhash={formhash_from_url}"
            
            # 方式3：使用formhash构建申请URL
            if not apply_url:
                apply_url = f"{BASE_URL}/home.php?mod=task&do=apply&id={TASK_ID}&formhash={formhash}"
            
            self.log(f"申请URL: {apply_url}")
            
            # 第三步：执行申请
            self.log("点击'立即申请'...")
            apply_resp = self.session.get(apply_url, timeout=30)
            
            # 检查申请结果
            if '申请成功' in apply_resp.text or 'success' in apply_resp.text.lower():
                self.log("✅ 申请成功！")
            elif '已申请' in apply_resp.text or '任务已申请' in apply_resp.text:
                self.log("任务已经申请过")
            else:
                if '已完成' in apply_resp.text or '已领取' in apply_resp.text:
                    return "ℹ️ 今日红包已领取"
                self.log(f"申请响应: {apply_resp.text[:200]}")
                return "❌ 申请失败"
            
            # 第四步：等待后领取奖励
            self.log("等待2秒后领取奖励...")
            time.sleep(2)
            
            # 查找领取链接
            self.log("查找'领取奖励'按钮...")
            
            task_resp2 = self.session.get(task_url, timeout=30)
            task_text2 = task_resp2.text
            
            draw_url = None
            
            draw_match = re.search(r'<a href="([^"]+do=draw[^"]+id=' + TASK_ID + r'[^"]*)"[^>]*>领取奖励', task_text2)
            if draw_match:
                draw_url_part = draw_match.group(1)
                draw_url_part = draw_url_part.replace('&amp;', '&')
                draw_url = f"{BASE_URL}/{draw_url_part}" if not draw_url_part.startswith('http') else draw_url_part
            
            if not draw_url:
                draw_url = f"{BASE_URL}/home.php?mod=task&do=draw&id={TASK_ID}&formhash={formhash}"
            
            self.log(f"领取URL: {draw_url}")
            
            # 第五步：执行领取
            self.log("点击'领取奖励'...")
            draw_resp = self.session.get(draw_url, timeout=30)
            
            if '成功' in draw_resp.text:
                point_match = re.search(r'威望\s*([+-]?\d+)', draw_resp.text)
                if point_match:
                    return f"✅ 领取成功 +{point_match.group(1)}威望"
                return "✅ 领取成功"
            elif '已完成' in draw_resp.text or '已领取' in draw_resp.text:
                return "ℹ️ 今日红包已领取"
            else:
                self.log(f"领取响应: {draw_resp.text[:200]}")
                return "❌ 领取失败"
                
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
        
        if not self.check_login():
            error_msg = "登录失败，请检查网络连接或Cookie配置"
            self.log(error_msg, "ERROR")
            self.send_telegram(f"❌ {error_msg}\n可能是网站无法访问或IP被限制")
            sys.exit(1)
        
        sign_result = self.sign()
        self.log(f"签到结果: {sign_result}")
        
        time.sleep(2)
        
        packet_result = self.packet()
        self.log(f"红包结果: {packet_result}")
        
        summary = f"签到: {sign_result}\n红包: {packet_result}"
        self.log(f"\n最终结果:\n{summary}")
        self.log("=" * 50)
        
        self.send_telegram(summary)
        
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
