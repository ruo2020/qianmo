import requests
import re
import time
import os
import sys
from datetime import datetime

# ======================
# 基础配置
# ======================
URL = "https://www.1000qm.vip/forum.php"
TASK_ID = "1"
BASE = '/'.join(URL.split('/')[:-1])

# Session 初始化
s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': BASE + '/'
})

# Cookie 加载
cookie_str = os.environ.get('QM1000_COOKIE', '')
if not cookie_str:
    print("❌ 未检测到 QM1000_COOKIE 环境变量")
    sys.exit(1)

for c in cookie_str.split(';'):
    if '=' in c:
        k, v = c.strip().split('=', 1)
        s.cookies.set(k, v)

print("✅ Cookie 已加载")

# ======================
# 工具函数
# ======================
def tg_send(msg):
    token = os.environ.get('TG_BOT_TOKEN')
    uid = os.environ.get('TG_USER_ID')
    if not (token and uid):
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={'chat_id': uid, 'text': msg},
            timeout=10
        )
    except Exception:
        pass

def safe_request(method, url, **kwargs):
    """
    带重试机制的请求函数
    """
    # 设置默认超时：连接10秒，读取30秒
    kwargs.setdefault('timeout', (10, 30))
    
    for i in range(3):  # 最多重试3次
        try:
            resp = s.request(method, url, **kwargs)
            return resp
        except requests.exceptions.Timeout:
            print(f"⚠️ 请求超时，正在进行第 {i+1}/3 次重试...")
            time.sleep(5)
        except requests.exceptions.RequestException as e:
            print(f"⚠️ 网络请求异常: {e}")
            time.sleep(5)
    
    # 如果三次都失败了
    raise requests.exceptions.RequestException("多次重试后仍失败")

# ======================
# 核心业务函数
# ======================
def get_formhash():
    try:
        r = safe_request('GET', f"{BASE}/home.php?mod=task")
        match = re.search(r'name="formhash" value="([a-f0-9]+)"', r.text)
        return match.group(1) if match else None
    except Exception as e:
        print(f"❌ 获取 formhash 失败: {e}")
        return None

def check_login_status():
    """
    检测登录状态
    """
    try:
        print("🔍 检查登录状态...")
        r = safe_request('GET', f"{BASE}/home.php?mod=spacecp")
        
        if '退出' not in r.text:
            return False
        return True
    except Exception as e:
        print(f"❌ 登录检查失败: {e}")
        return False

def sign():
    try:
        print("📋 开始签到...")
        r = safe_request('GET', f"{BASE}/plugin.php?id=dsu_paulsign:sign")
        
        f = re.search(r'name="formhash" value="([a-f0-9]+)"', r.text)
        if not f:
            return "❌ 签到失败（未找到 formhash）"

        data = {
            'formhash': f.group(1),
            'qdxq': 'kx',
            'qdmode': '2',
            'todaysay': '',
            'fastreply': '0'
        }

        r = safe_request(
            'POST',
            f"{BASE}/plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1&sign_as=1&inajax=1",
            data=data,
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )

        if '成功' in r.text:
            credit = re.search(r'获得(\d+)点(\w+)', r.text)
            return f"✅ 签到成功 +{credit.group(1)}{credit.group(2)}" if credit else "✅ 签到成功"
        elif '已经签到' in r.text:
            return "ℹ️ 今日已签到"
        else:
            return "❌ 签到失败"
    except Exception as e:
        return f"❌ 签到异常: {e}"

def packet():
    print("📋 开始处理威望红包...")
    h = get_formhash()
    if not h:
        return "❌ 获取 formhash 失败"

    try:
        # 申请任务
        apply_data = {'formhash': h, 'applysubmit': 'yes'}
        r = safe_request('POST', f"{BASE}/home.php?mod=task&do=apply&id={TASK_ID}", data=apply_data)

        if '申请成功' in r.text:
            time.sleep(2)
            draw_data = {'formhash': h, 'drawsubmit': 'yes'}
            r = safe_request('POST', f"{BASE}/home.php?mod=task&do=draw&id={TASK_ID}", data=draw_data)
            if '成功' in r.text:
                p = re.search(r'威望\s*([+-]?\d+)', r.text)
                return f"✅ 领取成功 +{p.group(1)}威望" if p else "✅ 领取成功"
        elif '已申请' in r.text:
            draw_data = {'formhash': h, 'drawsubmit': 'yes'}
            r = safe_request('POST', f"{BASE}/home.php?mod=task&do=draw&id={TASK_ID}", data=draw_data)
            if '成功' in r.text:
                p = re.search(r'威望\s*([+-]?\d+)', r.text)
                return f"✅ 领取成功 +{p.group(1)}威望" if p else "✅ 领取成功"
        
        return "ℹ️ 今日已完成或不可重复领取"
    except Exception as e:
        return f"❌ 红包处理异常: {e}"

# ======================
# 主入口
# ======================
def main():
    现在 = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    header = f"""
==================================================
 阡陌居自动签到脚本启动 ({now})
==================================================
"""
    print(header)

    if not check_login_status():
        msg = "❌ 登录失败，请检查Cookie是否有效或网络连接"
        print(msg)
        tg_send(f"阡陌居 {now}\n{msg}")
        sys.exit(1)

    print("✅ 登录成功")

    sign_res = sign()
    print(f"📌 签到结果: {sign_res}")

    time.sleep(2)

    pkt_res = packet()
    print(f"📌 红包结果: {pkt_res}")

    final_msg = f"🏮 阡陌居 {now}\n签到: {sign_res}\n红包: {pkt_res}"
    tg_send(final_msg)
    print("\n✅ 脚本执行完毕")

if __name__ == "__main__":
    main()
