import requests, re, time, os
from datetime import datetime

# 配置
URL = "https://www.1000qm.vip/forum.php"
TASK_ID = "1"
base = '/'.join(URL.split('/')[:-1])
TIMEOUT = 30  # 增加超时时间到30秒

# 初始化
s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0'})
for c in os.environ.get('QM1000_COOKIE','').split(';'):
    if '=' in c: k,v = c.strip().split('=',1); s.cookies.set(k,v)

def requests_get(url, timeout=TIMEOUT, retry=2):
    """带重试的GET请求"""
    for i in range(retry):
        try:
            return s.get(url, timeout=timeout)
        except requests.Timeout:
            if i == retry - 1:
                raise
            print(f"⏰ 请求超时，重试 {i+1}/{retry}...")
            time.sleep(3)
    return None

def requests_post(url, data=None, timeout=TIMEOUT, retry=2):
    """带重试的POST请求"""
    for i in range(retry):
        try:
            return s.post(url, data=data, timeout=timeout)
        except requests.Timeout:
            if i == retry - 1:
                raise
            print(f"⏰ 请求超时，重试 {i+1}/{retry}...")
            time.sleep(3)
    return None

def tg_send(msg):
    token = os.environ.get('TG_BOT_TOKEN')
    uid = os.environ.get('TG_USER_ID')
    if token and uid:
        try: 
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                         json={'chat_id': uid, 'text': msg}, timeout=10)
        except: 
            pass

def get_hash():
    """获取formhash"""
    try: 
        text = requests_get(f"{base}/home.php?mod=task").text
        formhash = re.search(r'name="formhash" value="([a-f0-9]+)"', text)
        return formhash.group(1) if formhash else None
    except: 
        return None

def check_status():
    """检测任务状态"""
    try:
        url = f"{base}/home.php?mod=task&do=view&id={TASK_ID}"
        print(f"🔍 检查状态URL: {url}")
        text = requests_get(url).text
        
        if '已完成' in text or '完成于' in text:
            return 'completed'
        elif '进行中的任务' in text or '领取奖励' in text:
            return 'applied'
        elif '立即申请' in text or '申请任务' in text:
            return 'available'
        elif '后可以再次申请' in text:
            return 'available'
        else:
            return 'unknown'
    except Exception as e:
        print(f"❌ 状态检测异常: {e}")
        return 'unknown'

def sign():
    """签到"""
    try:
        print("📋 获取签到页面...")
        r = requests_get(f"{base}/plugin.php?id=dsu_paulsign:sign")
        
        # 获取formhash
        f = re.search(r'name="formhash" value="([a-f0-9]+)"', r.text)
        if not f:
            print("❌ 未找到formhash")
            return "❌ 签到失败"
        
        # 签到
        print("📝 提交签到...")
        data = {
            'formhash': f.group(1),
            'qdxq': 'kx',
            'qdmode': '2',
            'todaysay': '',
            'fastreply': '0'
        }
        
        r = requests_post(
            f"{base}/plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1&sign_as=1&inajax=1",
            data=data
        )
        
        if r and '成功' in r.text:
            credit = re.search(r'获得(\d+)点(\w+)', r.text)
            return f"✅ 签到成功 +{credit.group(1)}{credit.group(2)}" if credit else "✅ 签到成功"
        elif r and '已经签到' in r.text:
            return "ℹ️ 今日已签到"
        else:
            return "❌ 签到失败"
    except Exception as e:
        print(f"❌ 签到异常: {e}")
        return "❌ 签到异常"

def packet():
    """领取威望红包"""
    print("📋 开始处理威望红包...")
    
    h = get_hash()
    if not h:
        return "❌ 获取formhash失败"
    
    try:
        # 申请任务
        print("📌 申请任务...")
        apply_url = f"{base}/home.php?mod=task&do=apply&id={TASK_ID}"
        apply_data = {'formhash': h, 'applysubmit': 'yes'}
        
        apply_resp = requests_post(apply_url, data=apply_data)
        
        if not apply_resp:
            return "❌ 申请任务失败（网络超时）"
        
        # 检查申请结果
        if '申请成功' in apply_resp.text or 'success' in apply_resp.text.lower():
            print("✅ 任务申请成功，等待2秒后领取...")
            time.sleep(2)
            
            # 领取奖励
            draw_url = f"{base}/home.php?mod=task&do=draw&id={TASK_ID}"
            draw_data = {'formhash': h, 'drawsubmit': 'yes'}
            r = requests_post(draw_url, data=draw_data)
            if r and '成功' in r.text:
                p = re.search(r'威望\s*([+-]?\d+)', r.text)
                return f"✅ 申请成功 +{p.group(1)}威望" if p else "✅ 申请成功"
            else:
                return "❌ 申请成功但领取失败"
        elif apply_resp and '已申请' in apply_resp.text:
            print("📌 任务已申请，尝试领取...")
            time.sleep(1)
            draw_url = f"{base}/home.php?mod=task&do=draw&id={TASK_ID}"
            draw_data = {'formhash': h, 'drawsubmit': 'yes'}
            r = requests_post(draw_url, data=draw_data)
            if r and '成功' in r.text:
                p = re.search(r'威望\s*([+-]?\d+)', r.text)
                return f"✅ 领取成功 +{p.group(1)}威望" if p else "✅ 领取成功"
            else:
                return "❌ 已申请但领取失败"
        else:
            # 检查是否已完成
            status = check_status()
            if status == 'completed':
                return "ℹ️ 今日红包已领取"
            else:
                return "❌ 申请失败，可能今日已领或条件不足"
                
    except Exception as e:
        print(f"❌ 红包处理异常: {e}")
        return "❌ 处理异常"

def main():
    try:
        # 检查登录状态
        print("🔍 检查登录状态...")
        login_page = requests_get(f"{base}/home.php?mod=spacecp")
        
        if login_page and '退出' not in login_page.text:
            msg = f"❌ Cookie失效或未登录"
            print(msg)
            tg_send(f"阡陌居 {datetime.now().strftime('%m-%d %H:%M')}\n{msg}")
            return
        
        print("✅ 登录成功")
        
    except requests.Timeout:
        print(f"❌ 登录检查超时，网站响应过慢")
        tg_send(f"阡陌居 {datetime.now().strftime('%m-%d %H:%M')}\n❌ 网络超时，无法连接")
        return
    except Exception as e:
        print(f"❌ 登录检查异常: {e}")
        return
    
    print("="*50)
    print(f"🏮 阡陌居 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
    
    # 执行签到
    print("\n📋 开始执行签到...")
    s_res = sign()
    print(f"📌 签到结果: {s_res}")
    
    time.sleep(2)
    
    # 领取威望红包
    print("\n📋 开始处理威望红包...")
    p_res = packet()
    print(f"📌 红包结果: {p_res}")
    
    print("\n" + "="*50)
    print(f"📊 最终结果")
    print(f"签到: {s_res}")
    print(f"红包: {p_res}")
    print("="*50)
    
    # 发送TG通知
    tg_msg = f"🏮 阡陌居 {datetime.now().strftime('%m-%d %H:%M')}\n签到: {s_res}\n红包: {p_res}"
    tg_send(tg_msg)
    print("📱 TG通知已发送")

if __name__ == "__main__":
    main()
