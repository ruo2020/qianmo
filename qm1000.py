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
from datetime import datetime

# 配置
BASE_URL = "https://www.1000qm.vip"
TASK_ID = "1"

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
        """打印带时间戳的日志"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] [{level}] {msg}")
        sys.stdout.flush()
    
    def send_telegram(self, message):
        """发送Telegram通知"""
        token = os.environ.get('TG_BOT_TOKEN')
        user_id = os.environ.get('TG_USER_ID')
        
        if not token or not user_id:
            self.log("未配置TG通知，跳过", "WARN")
            return
        
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {
                'chat_id': user_id,
                'text': f"🏮 阡陌居签到\n{message}\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
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
    
    def get_formhash(self, url):
        """从页面获取formhash"""
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
        """领取威望红包 - 标准流程版"""
        self.log("开始领取威望红包...")
        
        # 1. 进入任务页面
        task_url = f"{BASE_URL}/home.php?mod=task&do=view&id={TASK_ID}"
        self.log(f"访问任务页面: {task_url}")
        
        try:
            resp = self.session.get(task_url, timeout=15)
            resp.encoding = 'utf-8'
            page_text = resp.text
            
            # 2. 检查是否已完成
            if '已完成' in page_text or '完成于' in page_text:
                self.log("检测到任务已完成")
                # 尝试直接领取奖励
                draw_match = re.search(r'<a href="(home\.php\?mod=task&do=draw&id={TASK_ID}[^"]*)"', page_text)
                if draw_match:
                    draw_url = f"{BASE_URL}/{draw_match.group(1)}"
                    self.log(f"尝试领取奖励: {draw_url}")
                    draw_resp = self.session.get(draw_url, timeout=15)
                    if '成功' in draw_resp.text or '威望' in draw_resp.text:
                        point_match = re.search(r'威望\s*([+-]?\d+)', draw_resp.text)
                        if point_match:
                            return f"✅ 领取成功 +{point_match.group(1)}威望"
                        return "✅ 领取成功"
                return "ℹ️ 今日红包已领取"
            
            # 3. 查找“立即申请”按钮并获取formhash
            apply_match = re.search(r'<a href="(home\.php\?mod=task&do=apply&id={TASK_ID}&formhash=[a-f0-9]+)"', page_text)
            if not apply_match:
                # 尝试另一种正则匹配
                apply_match = re.search(r'apply&id={TASK_ID}&formhash=([a-f0-9]+)', page_text)
            
            if apply_match:
                # 提取申请URL或formhash
                if 'formhash=' in apply_match.group(0):
                    if apply_match.group(1):
                        formhash = apply_match.group(1)
                    else:
                        # 从完整URL中提取formhash
                        url_part = apply_match.group(0)
                        formhash_match = re.search(r'formhash=([a-f0-9]+)', url_part)
                        if formhash_match:
                            formhash = formhash_match.group(1)
                        else:
                            formhash = None
                    
                    if formhash:
                        self.log(f"找到申请链接，formhash: {formhash[:8]}...")
                        # 构建申请URL并访问
                        apply_url = f"{BASE_URL}/home.php?mod=task&do=apply&id={TASK_ID}&formhash={formhash}"
                        self.log(f"点击申请: {apply_url}")
                        apply_resp = self.session.get(apply_url, timeout=15)
                        
                        # 检查申请结果
                        if '申请成功' in apply_resp.text or 'success' in apply_resp.text.lower():
                            self.log("申请成功，等待2秒后领取...")
                            time.sleep(2)
                            
                            # 申请成功后，再次进入任务页面领取奖励
                            final_resp = self.session.get(task_url, timeout=15)
                            draw_match = re.search(r'<a href="(home\.php\?mod=task&do=draw&id={TASK_ID}[^"]*)"', final_resp.text)
                            if draw_match:
                                draw_url = f"{BASE_URL}/{draw_match.group(1)}"
                                draw_resp = self.session.get(draw_url, timeout=15)
                                if '成功' in draw_resp.text:
                                    point_match = re.search(r'威望\s*([+-]?\d+)', draw_resp.text)
                                    if point_match:
                                        return f"✅ 领取成功 +{point_match.group(1)}威望"
                                    return "✅ 领取成功"
                            return "❌ 申请成功但未找到领取链接"
                        else:
                            return "❌ 申请失败，请检查Cookie或任务条件"
                    else:
                        return "❌ 未找到formhash"
                else:
                    return "❌ 申请链接格式异常"
            else:
                # 4. 如果没有找到“立即申请”按钮，检查是否已经申请过
                if '进行中的任务' in page_text:
                    self.log("检测到任务进行中，尝试领取...")
                    draw_match = re.search(r'<a href="(home\.php\?mod=task&do=draw&id={TASK_ID}[^"]*)"', page_text)
                    if draw_match:
                        draw_url = f"{BASE_URL}/{draw_match.group(1)}"
                        draw_resp = self.session.get(draw_url, timeout=15)
                        if '成功' in draw_resp.text:
                            point_match = re.search(r'威望\s*([+-]?\d+)', draw_resp.text)
                            if point_match:
                                return f"✅ 领取成功 +{point_match.group(1)}威望"
                            return "✅ 领取成功"
                    return "ℹ️ 任务进行中但无领取链接"
                else:
                    return "ℹ️ 未找到申请入口，可能今日已领取或无权限"
                    
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
