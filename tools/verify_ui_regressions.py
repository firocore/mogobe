"""Focused UI regressions: one muted headless client and one protocol friend."""
import json
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

import httpx
from verify_desktop import CLIENT, ROOT, wait_http
from verify_room_audio import IsolatedBrowser
from websockets.sync.client import connect


def main():
    out=ROOT/'verification/ui-regressions'
    out.mkdir(parents=True,exist_ok=True)
    result={'suite':'ui-regressions','account_count':2,'checks':{}}
    processes=[]
    bridge=None
    friend=None
    with tempfile.TemporaryDirectory(prefix='mogobe-ui-regressions-',ignore_cleanup_errors=True) as temporary:
        directory=Path(temporary)
        database=directory/'test.sqlite3'
        with (out/'backend.log').open('w',encoding='utf-8') as blog, (out/'client.log').open('w',encoding='utf-8') as clog:
            try:
                env=os.environ.copy()
                env['MOGOBE_BOOTSTRAP_DEFAULTS']='false'
                env['MOGOBE_DATABASE_URL']='sqlite+aiosqlite:///'+database.as_posix()
                env['PYTHONPATH']=str(ROOT/'server/.venv/Lib/site-packages')
                env['MOGOBE_UI_TEST_SECRET']=secrets.token_urlsafe(32)
                env['MOGOBE_UI_TEST_PROFILE']=str(directory/'webview')
                # Exercise late replies as well as locally cached item art.
                backend_code = """import asyncio
from src.legacy.socket import LegacyConnection
original_command = LegacyConnection.command
async def delayed_inventory(self, command, params):
    if command == 'user__getInventoryItems':
        await asyncio.sleep(.2)
    return await original_command(self, command, params)
LegacyConnection.command = delayed_inventory
from run import main
main()
"""
                backend=subprocess.Popen([sys._base_executable,'-c',backend_code,'--port','18080'],cwd=ROOT/'server',env=env,stdout=blog,stderr=subprocess.STDOUT)
                processes.append(backend)
                wait_http('http://127.0.0.1:18080/api/health')
                with httpx.Client(base_url='http://127.0.0.1:18080') as api:
                    assert api.post('/api/auth/registration-drafts',json={'username':'UiNative','password':'Fish1234','color_id':7}).status_code==201
                    assert api.post('/api/auth/register',json={'age':12,'chat_mode':'open'}).status_code==201
                    owner_id=api.get('/api/auth/me').json()['id']
                    with httpx.Client(base_url='http://127.0.0.1:18080') as peer_api:
                        assert peer_api.post('/api/auth/registration-drafts',json={'username':'UiFriend','password':'Fish1234','color_id':3}).status_code==201
                        assert peer_api.post('/api/auth/register',json={'age':12,'chat_mode':'open'}).status_code==201
                        friend_id=peer_api.get('/api/auth/me').json()['id']
                        friend_token=peer_api.cookies.get('mogobe_session')
                    with sqlite3.connect(database) as db:
                        db.execute('UPDATE auth_account SET is_admin=1 WHERE id=?',(owner_id,))
                        db.execute('INSERT INTO social_friendship(first_id,second_id) VALUES (?,?)',tuple(sorted((owner_id,friend_id))))
                    admin='/api/admin/shops'
                    for ident,main_type,category in [(100,1,4),(70,1,8),(1299,8,0),(1313,9,0),(661,3,0)]:
                        assert api.put(admin+'/items/'+str(ident),json={'id':ident,'name':'Test '+str(ident),'main_type':main_type,'inventory_category':category}).status_code==200
                    assert api.put(admin+'/native',json={'key':'native','title':'Проверка магазина','kind':'clothing'}).status_code==200
                    cat=api.post(admin+'/native/categories',json={'name':'Одежда','icon_id':4}).json()['id']
                    assert api.put(admin+'/native/offers/100',json={'item_id':100,'category_id':cat,'price':0}).status_code==200
                    with sqlite3.connect(database) as db:
                        for ident in [100,70,1299,1313,661]:
                            db.execute('INSERT INTO shop_owned_item(account_id,item_id) VALUES (?,?)',(owner_id,ident))
                    assert api.post('/api/auth/logout').status_code==204
                with sqlite3.connect(database) as db:
                    db.execute("UPDATE auth_account SET is_admin=1 WHERE username='UiNative'")
                config=directory/'client.json'
                config.write_text(json.dumps({'server_url':'http://127.0.0.1:18080','request_timeout_seconds':10}),encoding='utf-8')
                client=subprocess.Popen([str(CLIENT),'--config',str(config),'--preview','127.0.0.1:18089'],cwd=directory,env=env,stdout=clog,stderr=subprocess.STDOUT)
                processes.append(client)
                wait_http('http://127.0.0.1:18089/')
                edge=Path(os.environ['ProgramFiles(x86)'])/'Microsoft/Edge/Application/msedge.exe'
                browser=subprocess.Popen([str(edge),'--headless=new','--mute-audio','--no-first-run','--disable-gpu',
                    '--remote-debugging-port=18090','--user-data-dir='+str(directory/'edge'),'about:blank'],
                    env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                processes.append(browser)
                wait_http('http://127.0.0.1:18090/json/list')
                pages=httpx.get('http://127.0.0.1:18090/json/list').json()
                bridge=IsolatedBrowser(next(p for p in pages if p['type']=='page')['webSocketDebuggerUrl'])
                c=bridge
                c.call('Emulation.setDeviceMetricsOverride',width=1000,height=720,deviceScaleFactor=1,mobile=False)
                c.call('Page.enable')
                c.call('Page.navigate',url='http://127.0.0.1:18089/')
                c.wait("window.mogobeLogin?.view==='single'",60)
                c.control('txtUserName');c.type_text('UiNative')
                c.control('txtPassword');c.type_text('Fish1234')
                time.sleep(5)
                c.control('btnLogin')
                c.wait("window.mogobeLogin?.view==='servers'",40)
                c.stage_click(384,140)
                c.wait("window.mogobeScene?.state==='world'",60)
                EI="window.player.ruffle().callExternalInterface"
                PANEL=EI+"('getWorldPanelInfo')"
                POPUP=EI+"('getSocialPopupInfo')"
                INVENTORY=EI+"('getInventoryInfo')"
                AVATARS=EI+"('getWorldAvatars')"
                def snap(name):c.capture('ui-regressions/'+name)
                def profile_control(name):
                    bounds=c.js(EI+"('getProfileControlBounds',"+json.dumps(name)+")")
                    assert bounds,name
                    c.stage_click(bounds['x']+bounds['width']/2,bounds['y']+bounds['height']/2)
                def hover(x,y):
                    r=c.js("document.getElementById('stage').getBoundingClientRect().toJSON()")
                    c.call('Input.dispatchMouseEvent',type='mouseMoved',x=r['x']+x*r['width']/768,y=r['y']+y*r['height']/480)
                def send(packet):
                    friend.send(packet.encode()+b'\0')
                def ext(cmd,**params):send(json.dumps({'t':'xt','b':{'c':cmd,'p':params}}))
                def received():return friend.recv(timeout=15).decode().removesuffix('\0')
                def packet_until(predicate):
                    for _ in range(50):
                        packet=received()
                        if predicate(packet):return packet
                    raise AssertionError('expected packet missing')
                friend=connect('ws://127.0.0.1:18080/legacy/socket',additional_headers={'Authorization':'Bearer '+friend_token})
                send('<msg t="sys"><body action="verChk"/></msg>');received()
                send('<msg t="sys"><body action="login"><login><nick>UiFriend</nick><pword>__MOGOBE_CURRENT_SESSION__</pword></login></body></msg>')
                received();received();ext('user__joinFirstRoom')
                packet_until(lambda p:'action="joinOK"' in p)
                c.wait(AVATARS+'.length===2')
                c.control('btnBuddy')
                c.wait(POPUP+"?.rows.some(v=>v.userName==='UiFriend' && v.serverName==='Новоград')")
                for state in ['online','changed','offline']:
                    if state=='changed':
                        send('<msg t="sys"><body action="pubMsg"><txt>speak__/room infoboard</txt></body></msg>')
                        packet_until(lambda p:'action="joinOK"' in p)
                        c.wait(POPUP+"?.rows.some(v=>v.userName==='UiFriend' && v.serverName!=='Новоград' && v.serverName!==null)")
                    if state=='offline':
                        friend.close();friend=None
                        c.wait(POPUP+"?.rows.some(v=>v.userName==='UiFriend' && v.serverName===null)")
                    bounds=c.js(EI+"('getSocialRowControlBounds','UiFriend','name')")
                    assert bounds
                    for _ in range(3):
                        hover(20,20);time.sleep(.1)
                        hover(bounds['x']+bounds['width']/2,bounds['y']+bounds['height']/2)
                        time.sleep(.05)
                        rows=c.js(POPUP)['rows']
                        assert all(not re.search('[AaАа]{5}',row['text']) for row in rows),rows
                        assert rows[0]['text'].count('UiFriend')==1,rows
                    snap('friends-'+state)
                result['checks']['friends_location_live_and_hover_online_offline']=True
                profile_control('btnClose')
                c.control('txtSpeak')
                long_text=('Длинное сообщение '+('абвгдежз ')*30)[:230]
                c.type_text(long_text)
                time.sleep(.5)
                panel=c.js(PANEL);result['chat']=panel;snap('chat-long')
                assert panel['text']==long_text,panel
                assert not panel['multiline'] and not panel['wordWrap'],panel
                assert panel['scrollH']>0 and panel['caret']==len(long_text),panel
                assert panel['y']+panel['height']<=480,panel
                for key,code,scroll in [('Home',36,0),('End',35,panel['contentScrollH'])]:
                    c.call('Input.dispatchKeyEvent',type='keyDown',key=key,code=key,windowsVirtualKeyCode=code)
                    c.call('Input.dispatchKeyEvent',type='keyUp',key=key,code=key,windowsVirtualKeyCode=code)
                    time.sleep(.15)
                    assert c.js(PANEL)['scrollH']==scroll,(key,c.js(PANEL))
                c.type_text('Коротко');time.sleep(.3)
                assert c.js(PANEL)['scrollH']==0,c.js(PANEL)
                snap('chat-short')
                result['checks']['long_chat_input_scrolls_to_caret_and_short_input_resets']=True
                friend=connect('ws://127.0.0.1:18080/legacy/socket',additional_headers={'Authorization':'Bearer '+friend_token})
                send('<msg t="sys"><body action="verChk"/></msg>');received()
                send('<msg t="sys"><body action="login"><login><nick>UiFriend</nick><pword>__MOGOBE_CURRENT_SESSION__</pword></login></body></msg>')
                received();received();ext('user__joinFirstRoom')
                packet_until(lambda p:'action="joinOK"' in p)
                c.wait(AVATARS+'.length===2')
                c.chat_send('/shop native')
                SHOP=EI+"('getShopInfo')"
                c.wait(SHOP+"?.key==='native' && "+SHOP+".items.length>0")
                # A shop stays open while both HTTP presence and /online remain active.
                snapshot=c.js("fetch('/api/world/servers').then(r=>r.json())")
                assert snapshot['servers'][0]['online']==2,snapshot
                for _ in range(6):
                    time.sleep(5)
                    assert c.js("fetch('/api/world/servers').then(r=>r.json()).then(x=>x.servers[0].online)")==2
                send('<msg t="sys"><body action="pubMsg"><txt>speak__/online</txt></body></msg>')
                assert 'Сейчас в игре: 2' in packet_until(lambda p:'Сейчас в игре:' in p)
                snap('shop-online')
                c.js(EI+"('closeOriginalShop')")
                friend.close();friend=None
                c.wait(AVATARS+'.length===1')
                c.chat_send('/online')
                c.wait(AVATARS+".some(v=>v.me && v.speech.includes('Сейчас в игре: 1'))")
                result['checks']['shop_player_remains_online']=True
                c.control('btnProfile')
                c.wait(EI+"('getProfileInfo')?.visible===true")
                profile_control('mc_4_8_13_14_21')
                c.wait(INVENTORY+"?.cells.some(v=>v.typeId===100 && v.visible)")
                snap('inventory-clothes')
                for index,tab in enumerate(['btnPetsItems','btnTrophy','btnBeads','btnClothing','btnPetsItems','btnClothing']):
                    c.js("window.inventoryFrames=[];window.inventoryProbe=true;function probeInventory(){if(!window.inventoryProbe)return;window.inventoryFrames.push(window.player.ruffle().callExternalInterface('getInventoryInfo'));requestAnimationFrame(probeInventory)};requestAnimationFrame(probeInventory)")
                    profile_control(tab)
                    # Inspect each painted frame, including the first frame
                    # while the response/art are still loading.
                    for _ in range(8):
                        data=c.js(INVENTORY)
                        if tab in ['btnPetsItems','btnTrophy','btnBeads']:
                            assert not any(v['visible'] and v['mainType']==1 for v in data['cells']),(tab,data)
                        time.sleep(.035)
                    c.js('window.inventoryProbe=false')
                    frames=c.js('window.inventoryFrames')
                    if tab in ['btnPetsItems','btnTrophy','btnBeads']:
                        assert not any(v['visible'] and v['mainType']==1 for f in frames if f and f['tab']=={'btnPetsItems':'lblPetItems','btnTrophy':'lblTrophy','btnBeads':'lblBeads'}[tab] for v in f['cells']),(tab,frames)
                    snap('inventory-'+str(index)+'-'+tab)
                c.js("window.inventoryFrames=[];window.inventoryProbe=true;requestAnimationFrame(probeInventory)")
                for tab in ['btnClothing','btnPetsItems','btnBeads','btnClothing']:
                    profile_control(tab)
                profile_control('mc_4_8_13_14_21')
                time.sleep(1.5)
                c.js('window.inventoryProbe=false')
                frames=c.js('window.inventoryFrames')
                allowed={'lblCloth':[1],'lblPetItems':[8,9,10,11],'lblBeads':[3,4],'lblTrophy':[5]}
                for frame in frames:
                    if frame and frame['tab'] in allowed:
                        assert all(not cell['visible'] or cell['mainType'] in allowed[frame['tab']] for cell in frame['cells']),frame
                c.wait(INVENTORY+"?.cells.some(v=>v.typeId===100 && v.visible)")
                profile_control('btnClose')
                result['checks']['inventory_tabs_do_not_keep_previous_clothes']=True
                result['checks']['rapid_inventory_switching_with_late_replies']=True
                for width,height in [(1600,900),(900,1000),(1000,720)]:
                    c.call('Emulation.setDeviceMetricsOverride',width=width,height=height,deviceScaleFactor=1,mobile=False)
                    time.sleep(.2)
                    box=c.js("document.querySelector('#game-frame').getBoundingClientRect().toJSON()")
                    assert box['x']>=0 and box['y']>=0 and box['right']+10<=width and box['bottom']+10<=height,box
                    assert c.js("getComputedStyle(document.querySelector('#stage')).overflow")== 'hidden'
                    snap('window-'+str(width))
                # Native DOM fullscreen is requested by Ruffle's own element.
                response=c.call('Runtime.evaluate',expression="Element.prototype.requestFullscreen.call(window.player)",awaitPromise=True,userGesture=True,returnByValue=True)
                assert 'exceptionDetails' not in response,response
                c.wait('document.fullscreenElement===window.player')
                fullscreen=c.js("(()=>{const frame=player.shadowRoot.querySelector('#container');const b=frame.getBoundingClientRect();return {border:getComputedStyle(frame).borderTopWidth,width:b.width,height:b.height,overflow:getComputedStyle(frame).overflow}})()")
                assert fullscreen['border']=='10px' and fullscreen['overflow']=='hidden',fullscreen
                assert abs((fullscreen['width']-20)/(fullscreen['height']-20)-1.6)<.01,fullscreen
                assert fullscreen['width']<980 and fullscreen['height']<700,fullscreen
                snap('fullscreen')
                c.js('document.exitFullscreen()')
                result['checks']['resize_and_fullscreen_keep_border_and_clip_stage']=True
            except Exception:
                result['error']=traceback.format_exc()
                if bridge:
                    try:
                        result['state']=bridge.js("JSON.stringify({scene:window.mogobeScene,panel:window.player?.ruffle().callExternalInterface('getWorldPanelInfo'),inventory:window.player?.ruffle().callExternalInterface('getInventoryInfo'),friends:window.player?.ruffle().callExternalInterface('getSocialPopupInfo')})")
                        bridge.capture('ui-regressions/failure')
                    except Exception:pass
            finally:
                if friend:
                    friend.close()
                for process in reversed(processes):
                    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True)
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:process.kill()
    result['passed']=not result.get('error') and all(result['checks'].values())
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True,indent=2),flush=True)
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
