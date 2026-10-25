"""No accounts: reproduce native Ruffle TextField scrolling, then verify shared compatibility."""
import argparse
import json
import os
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from verify_desktop import ROOT, wait_http
from verify_room_audio import IsolatedBrowser

HTML = b'''<!doctype html><meta charset="utf-8"><body style="margin:0;background:#ddd">
<div id="stage" style="width:768px;height:480px"></div>
<script>window.RufflePlayer={config:{autoplay:'on',unmuteOverlay:'hidden',allowScriptAccess:true,warnOnUnsupportedContent:false}};</script>
<script src="/runtime/ruffle.js"></script><script>
window.probeLogs=[];for(const key of ['error','warn']){const old=console[key];console[key]=function(...args){window.probeLogs.push(args.map(String).join(' ').slice(0,2000));return old.apply(this,args)}};
window.player=RufflePlayer.newest().createPlayer();player.style.width='768px';player.style.height='480px';
document.getElementById('stage').appendChild(player);
player.ruffle().load({url:'/probe.swf',parameters:{applyFix:new URL(location).searchParams.get('fix')==='1'?'true':'false'}}).catch(e=>window.probeError=String(e));
</script>'''


class Handler(BaseHTTPRequestHandler):
    paths = []
    def log_message(self, *_):
        pass

    def do_GET(self):
        path = urlsplit(self.path).path
        self.paths.append(path)
        if path == '/':
            data, mime = HTML, 'text/html'
        else:
            if path == '/probe.swf':
                file = ROOT/'verification/input-fields/probe.swf'
            elif path == '/Swf/Login.swf':
                file = ROOT/'assets/original/Swf/Login.swf'
            elif path.startswith('/runtime/') and '/' not in path[len('/runtime/'):]:
                file = ROOT/'assets/ruffle'/path[len('/runtime/'):]
            else:
                self.send_error(404);return
            if not file.is_file():
                self.send_error(404);return
            data = file.read_bytes()
            mime = 'application/wasm' if file.suffix == '.wasm' else 'text/javascript' if file.suffix == '.js' else 'application/x-shockwave-flash'
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers();self.wfile.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-only', action='store_true')
    args = parser.parse_args()
    folder = ROOT/'verification/input-fields'
    folder.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
    url = 'http://127.0.0.1:'+str(server.server_port)
    result = {'account_count':0,'cases':{},'checks':{}}
    process = None
    scratch = ROOT/'verification/windows-temp'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='mogobe-inputs-',dir=scratch,ignore_cleanup_errors=True) as temporary:
        try:
            edge = Path(os.environ['ProgramFiles(x86)'])/'Microsoft/Edge/Application/msedge.exe'
            # Use a random CDP port via Chromium's DevToolsActivePort file.
            profile = Path(temporary)/'edge'
            process = subprocess.Popen([str(edge),'--headless=new','--mute-audio','--no-first-run',
                '--disable-gpu','--remote-debugging-port=0','--user-data-dir='+str(profile),'about:blank'],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            active = profile/'DevToolsActivePort'
            for _ in range(100):
                if active.is_file():break
                time.sleep(.1)
            port = active.read_text().splitlines()[0]
            wait_http('http://127.0.0.1:'+port+'/json/list')
            pages = httpx.get('http://127.0.0.1:'+port+'/json/list').json()
            c = IsolatedBrowser(next(p for p in pages if p['type']=='page')['webSocketDebuggerUrl'])
            c.call('Page.enable')
            c.call('Emulation.setDeviceMetricsOverride',width=1000,height=720,deviceScaleFactor=1,mobile=False)
            EI="window.player.ruffle().callExternalInterface"
            DATA=EI+"('snapshot')"
            for fix in [False] if args.baseline_only else [False,True]:
                mode = 'fixed' if fix else 'native'
                c.call('Page.navigate',url=url+'/?fix='+('1' if fix else '0'))
                c.wait(DATA+'?.ready===true',40)
                observations={}
                for name in ['deviceLeft','deviceRight','embeddedLeft','embeddedRight','password','multiline']:
                    FIELD=DATA+'.fields.find(f=>f.name==='+json.dumps(name)+')'
                    box=c.js(FIELD)
                    c.stage_click(box['x']+box['width']/2,box['y']+box['height']/2)
                    text=('Строка проверки '+('абвгдежз '*40))[:220] if name!='multiline' else '\n'.join('Строка '+str(i)+' для проверки прокрутки' for i in range(18))
                    c.type_text(text)
                    c.wait(FIELD+'.length==='+str(len(text)))
                    time.sleep(.15)
                    observations[name]={'end':c.js(FIELD)}
                    if name!='multiline':
                        for key,code in [('Home',36),('End',35)]:
                            c.call('Input.dispatchKeyEvent',type='keyDown',key=key,code=key,windowsVirtualKeyCode=code)
                            c.call('Input.dispatchKeyEvent',type='keyUp',key=key,code=key,windowsVirtualKeyCode=code)
                            time.sleep(.1)
                            observations[name]['home' if key=='Home' else 'after_end']=c.js(FIELD)
                        if fix:
                            assert 0<=observations[name]['end']['caretGap']<=8,observations[name]
                            assert 0<=observations[name]['home']['firstX']-observations[name]['home']['scrollH']<=6,observations[name]
                            assert 0<=observations[name]['after_end']['caretGap']<=8,observations[name]
                            c.type_text('Мого')
                            c.wait(FIELD+'.length===4')
                            short=c.js(FIELD)
                            assert short['scrollH']==0,short
                            assert short['align']==('right' if name.endswith('Right') else 'left'),short
                    elif fix:
                        row=observations[name]['end']
                        assert row['scrollV']<=row['caretLine']<=row['bottomScrollV'],row
                        before_scroll=row['scrollV']
                        c.call('Input.dispatchMouseEvent',type='mouseMoved',x=box['x']+box['width']/2,y=box['y']+box['height']/2)
                        c.call('Input.dispatchMouseEvent',type='mouseWheel',x=box['x']+box['width']/2,y=box['y']+box['height']/2,deltaX=0,deltaY=-300)
                        c.wait(FIELD+'.scrollV<'+str(before_scroll))
                        manual=c.js(FIELD)
                        time.sleep(.3)
                        assert c.js(FIELD)['scrollV']==manual['scrollV'],manual
                        observations[name]['manual_scroll']=manual
                result['cases'][mode]=observations
                c.capture('input-fields/'+mode)
            native=result['cases']['native']
            assert all(native[name]['end']['caretGap']<0 and native[name]['end']['scrollH']==0 for name in ['deviceLeft','embeddedLeft']),native
            result['checks']['missing_native_caret_scrolling_reproduced_without_game_controllers']=True
            if not args.baseline_only:result['checks']['shared_fix_covers_device_embedded_right_password_and_multiline_inputs']=True
            result['passed']=True
        except Exception:
            try:
                result['debug']=c.js("({error:window.probeError,logs:window.probeLogs,snapshot:window.player?.ruffle().callExternalInterface('snapshot')})")
                c.capture('input-fields/failure')
            except Exception:pass
            result['requests']=Handler.paths
            import traceback
            result['error']=traceback.format_exc();result['passed']=False
        finally:
            if process:
                subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True)
                process.wait(timeout=10)
            server.shutdown();server.server_close()
    (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True,indent=2),flush=True)
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
