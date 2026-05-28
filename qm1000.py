import requests, re, time, os
from datetime import datetime

# 配置
URL = "https://www.1000qm.vip/forum.php"
TASK_ID = "1"
base = '/'.join(URL.split('/')[:-1])
TIMEOUT = 30

# 初始化
s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0'})
for c in os.environ.get('QM1000_COOKIE','').split(';'):
    if '=' in c: k,v = c.strip().split('=',1); s.cookies.set(k,v)

def requests_get(url, timeout=TIMEOUT, retry=2):
    for i in range(retry):
        try:
            return s.get(url, timeout=timeout)
        except requests.Timeout:
            if i == retry - 1:
                raise
            time.sleep(3)
    return None

def requests_post(url, data=None, timeout=TIMEOUT, retry=2):
    for i in range(retry):
        try:
            return s.post(url, data=data, timeout=timeout)
        except requests.Timeout:
            if i == retry - 1:
                raise
            time.sleep(3)
    return None

def get_hash():
    try: 
        text = requests_get(f"{base}/home.php?mod=task").text
        formhash = re.search(r'name="formhash" value="([a-f0-9]+)"', text)
        return formhash.group(1) if formhash else None
    except: 
        return None

def check_status():
    try:
        url = f"{base}/home.php?mod=task&do=view&id={TASK_ID}"
        text = requests_get(url).text
        
        if '已完成' in text or '完成于' in text or '领取奖励' not in text:
            return 'completed'
        elif '不是进行中的任务' in text or '没有找到指定任务' in text:
            return 'completed'
        elif '立即申请' in text or '申请任务' in text:
            if '后可以再次申请' in text:
                return 'completed'
            return 'available'
        else:
            return 'unknown'
    except Exception as e:
        return 'unknown'

def sign():
    try:
        r = requests_get(f"{base}/plugin.php?id=dsu_paulsign:sign")
        f = re.search(r'name="formhash" value="([a-f0-9]+)"', r.text)
        if not f:
            return "❌ 签到失败"
        
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
        return "❌ 签到异常"

def packet():
    status = check_status()
    
    if status == 'completed':
        return "ℹ️ 今日威望红包已领取"
    
    h = get_hash()
    if not h:
        return "❌ 获取formhash失败"
    
    try:
        if status == 'available':
            apply_url = f"{base}/home.php?mod=task&do=apply&id={TASK_ID}"
            apply_data = {'formhash': h, 'applysubmit': 'yes'}
            apply_resp = requests_post(apply_url, data=apply_data)
            
            if not apply_resp:
                return "❌ 申请任务失败"
            
            if '申请成功' in apply_resp.text or 'success' in apply_resp.text.lower():
                time.sleep(2)
            elif '已申请' in apply_resp.text:
                pass
            else:
                if '不是进行中的任务' in apply_resp.text:
                    return "ℹ️ 今日威望红包已领取"
                return "❌ 申请失败"
        
        draw_url = f"{base}/home.php?mod=task&do=draw&id={TASK_ID}"
        draw_data = {'formhash': h, 'drawsubmit': 'yes'}
        r = requests_post(draw_url, data=draw_data)
        
        if r:
            if '成功' in r.text:
                p = re.search(r'威望\s*([+-]?\d+)', r.text)
                return f"✅ 领取成功 +{p.group(1)}威望" if p else "✅ 领取成功"
            elif '操作失败' in r.text:
                return "ℹ️ 今日威望红包已领取"
        
        time.sleep(1)
        final_status = check_status()
        if final_status == 'completed':
            return "ℹ️ 今日威望红包已领取"
        
        return "❌ 领取失败"
                
    except Exception as e:
        return "❌ 处理异常"

def main():
    try:
        login_page = requests_get(f"{base}/home.php?mod=spacecp")
        if login_page and '退出' not in login_page.text:
            print(f"❌ Cookie失效或未登录")
            return
    except:
        print(f"❌ 网络连接失败")
        return
    
    print("="*50)
    print(f"🏮 阡陌居 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
    
    s_res = sign()
    print(f"签到: {s_res}")
    
    p_res = packet()
    print(f"红包: {p_res}")
    
    print("="*50)

if __name__ == "__main__":
    main()
