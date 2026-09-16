#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, platform, re, socket, sys, time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152.0 Safari/537.36'
VERIFY=('wappoc_appmsgcaptcha','环境异常','操作频繁','访问过于频繁','完成验证后','去验证','environment anomaly','environment abnormal')
TEXTOOLKIT='https://textoolkit.com/wechat-to-markdown'
MPTEXT='https://down.mptext.top/api/public/v1/download'

class FetchError(RuntimeError): pass
class VerificationRequired(FetchError): pass
@dataclass
class Article:
    source_url:str; final_url:str; method:str; title:str|None; markdown:str

def unwrap(url:str)->str:
    p=urlparse(url)
    if p.netloc.lower()=='mp.weixin.qq.com' and 'wappoc_appmsgcaptcha' in p.path:
        return unquote(parse_qs(p.query).get('target_url',[url])[0])
    return url

def validate(url:str)->str:
    url=unwrap(url); p=urlparse(url)
    if p.scheme not in {'http','https'} or p.netloc.lower()!='mp.weixin.qq.com' or not (p.path=='/s' or p.path.startswith('/s/')):
        raise FetchError('Only public mp.weixin.qq.com/s article URLs are supported.')
    return url

def is_verify(text:str,url:str='')->bool:
    h=(text+'\n'+url).lower(); return any(x.lower() in h for x in VERIFY)

def from_markdown(text:str,url:str,final:str,method:str)->Article:
    text=text.strip()
    if is_verify(text,final): raise VerificationRequired(f'{method}: WeChat verification/rate-limit page')
    if len(re.sub(r'\s+','',text))<80: raise FetchError(f'{method}: implausibly short response')
    m=re.search(r'(?m)^#\s+(.+)$',text); title=m.group(1).strip() if m else None
    return Article(url,final,method,title,text+'\n')

def from_html(html:str,url:str,final:str,method:str)->Article:
    if is_verify(html,final): raise VerificationRequired(f'{method}: WeChat verification/rate-limit page')
    soup=BeautifulSoup(html,'html.parser'); content=soup.select_one('#js_content')
    if not content: raise FetchError(f'{method}: missing #js_content')
    title=(soup.select_one('#activity-name').get_text(' ',strip=True) if soup.select_one('#activity-name') else 'Untitled WeChat article')
    for img in content.find_all('img'):
        src=img.get('data-src') or img.get('data-original') or img.get('src')
        if src: img['src']=urljoin(final,src)
        img['alt']=img.get('alt') or 'image'
    for n in content.select('script,style,noscript,iframe'): n.decompose()
    body=re.sub(r'\n{3,}','\n\n',md(str(content),heading_style='ATX')).strip()
    if len(re.sub(r'\s+','',body))<30: raise FetchError(f'{method}: article body too short')
    return Article(url,final,method,title,f'# {title}\n\n- 原文：{url}\n\n{body}\n')

def get(url:str,timeout:int,**kw):
    h={'User-Agent':UA,'Accept-Language':'zh-CN,zh;q=0.9','Referer':'https://mp.weixin.qq.com/'}
    r=requests.get(url,headers=h,timeout=timeout,allow_redirects=True,**kw); r.raise_for_status(); r.encoding=r.apparent_encoding or r.encoding or 'utf-8'; return r

def direct(url:str,t:int)->Article:
    r=get(url,t); return from_html(r.text,url,r.url,'direct')
def jina(url:str,t:int)->Article:
    r=get('https://r.jina.ai/'+url,t); return from_markdown(r.text,url,r.url,'jina')
def mptext(url:str,t:int)->Article:
    r=get(MPTEXT,t,params={'url':url,'format':'markdown'}); return from_markdown(r.text,url,r.url,'mptext')

def cdp_url()->str|None:
    for p in range(9222,9236):
        with socket.socket() as s:
            s.settimeout(.1)
            if s.connect_ex(('127.0.0.1',p))==0:
                try:
                    if requests.get(f'http://127.0.0.1:{p}/json/version',timeout=.4).ok: return f'http://127.0.0.1:{p}'
                except requests.RequestException: pass
    return None

def headless_default()->bool:
    return platform.system()=='Linux' and not (os.getenv('DISPLAY') or os.getenv('WAYLAND_DISPLAY'))

def browser(url:str,t:int,headless:bool|None=None,manual_wait:int=0,cdp:str|None=None)->Article:
    try: from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as e: raise FetchError('Playwright required for browser mode') from e
    h=headless_default() if headless is None else headless
    with sync_playwright() as p:
        b=None; ctx=None; owns=False
        try:
            endpoint=cdp or cdp_url()
            if endpoint:
                b=p.chromium.connect_over_cdp(endpoint); ctx=b.contexts[0] if b.contexts else b.new_context(); method='browser-cdp'
            else:
                profile=Path.home()/'.wechat-article-markdown'/'chrome-profile'; profile.mkdir(parents=True,exist_ok=True)
                ctx=p.chromium.launch_persistent_context(str(profile),headless=h,locale='zh-CN'); owns=True; method='browser-persistent'
            page=next((x for x in ctx.pages if 'mp.weixin.qq.com' in (x.url or '')),None) or (ctx.pages[0] if ctx.pages else ctx.new_page())
            if page.url!=url:
                try: page.goto(url,wait_until='domcontentloaded',timeout=t*1000)
                except Exception: pass
            deadline=time.monotonic()+max(5,min(t,15))
            while time.monotonic()<deadline:
                if page.locator('#js_content').count(): return from_html(page.content(),url,page.url,method)
                time.sleep(.5)
            txt=page.locator('body').inner_text(timeout=2000) if page.locator('body').count() else ''
            if is_verify(txt,page.url) and manual_wait>0 and not h:
                deadline=time.monotonic()+manual_wait
                while time.monotonic()<deadline:
                    if page.locator('#js_content').count(): return from_html(page.content(),url,page.url,method+'+manual')
                    time.sleep(.75)
            if is_verify(txt,page.url): raise VerificationRequired('browser: complete verification in visible persistent browser, then retry')
            raise FetchError('browser: article did not render')
        finally:
            if owns and ctx:
                try: ctx.close()
                except Exception: pass
            if b:
                try: b.close()
                except Exception: pass

def textoolkit(url:str,t:int,headless:bool|None=None)->Article:
    try: from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as e: raise FetchError('Playwright required for Textoolkit mode') from e
    h=headless_default() if headless is None else headless
    with sync_playwright() as p:
        b=p.chromium.launch(headless=h); page=b.new_page(locale='zh-CN',user_agent=UA)
        try:
            page.goto(TEXTOOLKIT,wait_until='domcontentloaded',timeout=max(30,t)*1000)
            inp=page.get_by_label(re.compile('WeChat Article URL',re.I)); inp.fill(url)
            page.get_by_role('button',name=re.compile('convert',re.I)).click()
            deadline=time.monotonic()+max(90,t)
            while time.monotonic()<deadline:
                vals=page.locator('textarea, pre, code').all_text_contents()
                candidates=[x.strip() for x in vals if len(re.sub(r'\s+','',x))>=80]
                if candidates: return from_markdown(max(candidates,key=len),url,page.url,'textoolkit')
                time.sleep(.75)
            raise FetchError('textoolkit: no Markdown result before timeout')
        finally: b.close()

def fetch(url:str,t:int=30,mode:str='auto',headless:bool|None=None,manual_wait:int=0,cdp:str|None=None)->Article:
    url=validate(url)
    methods={'browser':lambda:browser(url,t,headless,manual_wait,cdp),'textoolkit':lambda:textoolkit(url,t,headless),'mptext':lambda:mptext(url,t),'direct':lambda:direct(url,t),'jina':lambda:jina(url,t)}
    if mode!='auto': return methods[mode]()
    desktop=bool(cdp or cdp_url()) or not headless_default()
    order=('browser','textoolkit','mptext','direct','jina') if desktop else ('textoolkit','browser','mptext','direct','jina')
    errors=[]; verified=False
    for name in order:
        try: return methods[name]()
        except VerificationRequired as e: verified=True; errors.append(str(e))
        except Exception as e: errors.append(f'{name}: {e}')
    exc=VerificationRequired if verified else FetchError
    raise exc('All retrieval paths failed. '+' | '.join(errors))

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('url'); ap.add_argument('-o','--output'); ap.add_argument('--json',action='store_true'); ap.add_argument('--timeout',type=int,default=30); ap.add_argument('--mode',choices=('auto','browser','textoolkit','mptext','direct','jina'),default='auto'); ap.add_argument('--cdp-url'); ap.add_argument('--manual-wait',type=int,default=0); g=ap.add_mutually_exclusive_group(); g.add_argument('--headless',action='store_true'); g.add_argument('--headful',action='store_true'); a=ap.parse_args(); h=True if a.headless else False if a.headful else None
    try: art=fetch(a.url,a.timeout,a.mode,h,a.manual_wait,a.cdp_url)
    except VerificationRequired as e: print(json.dumps({'ok':False,'error_type':'verification_required','message':str(e)},ensure_ascii=False),file=sys.stderr); return 3
    except Exception as e: print(json.dumps({'ok':False,'error_type':'fetch_failed','message':str(e)},ensure_ascii=False),file=sys.stderr); return 2
    if a.output: Path(a.output).write_text(art.markdown,encoding='utf-8')
    if a.json: print(json.dumps({**asdict(art),'ok':True},ensure_ascii=False,indent=2))
    elif not a.output: print(art.markdown,end='')
    return 0
if __name__=='__main__': raise SystemExit(main())
