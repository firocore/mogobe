"""One muted headless account: chat editing, blank sends and local commands."""
import argparse
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

import httpx
from verify_desktop import CLIENT, ROOT, wait_http
from verify_room_audio import IsolatedBrowser


def check_bubbles(c,result,peer_token,peer_id,scope):
    from websockets.sync.client import connect
    EI="window.player.ruffle().callExternalInterface"
    AVATARS=EI+"('getWorldAvatars')"
    ME=AVATARS+".find(v=>v.me)"

    def send_ui(text):
        c.control('txtSpeak');c.type_text(text)
        c.wait(EI+"('getWorldPanelInfo').text==="+json.dumps(text))
        c.control('btnSend')
        c.wait(ME+"?.speech==="+json.dumps(text)+" && "+ME+".speechLayout!==null")
        return c.js(ME)

    def fits(avatar):
        box=avatar['speechLayout']
        assert box and box['maxScrollV']==1,avatar
        assert box['localWidth']<=220,box
        assert box['seamAlpha']>=250 and box['transparentCorners'],box
        if box['lines']>1 and box['localWidth']>128:
            assert box['fieldWidth']-box['longestLine']<=6,box
        assert box['fieldHeight']>=box['contentHeight']+3,box
        assert box['textX']>=box['x']-.5 and box['textX']+box['textWidth']<=box['x']+box['width']+.5,box
        assert box['textY']>=box['y']-.5 and box['textY']+box['textHeight']<=box['y']+box['height']+.5,box
        assert box['x']>=7.5 and box['x']+box['width']<=760.5 and box['y']>=7.5,box

    short=send_ui('Привет!');fits(short)
    assert short['speechLayout']['duration']==4000,short
    c.capture(scope+'/04-original-short-bubble')
    c.wait(ME+".speech===''",8)
    result['checks']['short_speech_expires_after_original_four_seconds']=True

    wrapped=send_ui('Короткая фраза переносится на новую строку.');fits(wrapped)
    assert wrapped['speechLayout']['lines']>=2,wrapped
    c.capture(scope+'/04b-compact-wrapped-bubble')
    result['checks']['wrapped_bubble_is_compact_and_background_has_no_transparent_joins']=True
    time.sleep(.6)

    long_text=('Это длинное сообщение: весь текст должен помещаться в облачке, чтобы его можно было прочитать. '*6)[:239].rstrip()+'!'
    large=send_ui(long_text);fits(large)
    assert large['speechLayout']['height']>short['speechLayout']['height'],(short,large)
    assert large['speechLayout']['width']>short['speechLayout']['width'],(short,large)
    assert large['speechLayout']['duration']>short['speechLayout']['duration'],large
    result['compact_bubble']=large['speechLayout']
    c.capture(scope+'/05-original-long-bubble')
    time.sleep(4.3)
    assert c.js(ME)['speech']==long_text
    result['checks']['long_speech_grows_and_survives_original_timer']=True

    c.stage_click(650,380)
    c.wait(ME+".x>610 && "+ME+".action===0",15)
    edge=c.js(ME);fits(edge)
    assert edge['speech']==long_text,edge
    c.capture(scope+'/06-bubble-near-right-edge')
    result['checks']['bubble_stays_inside_stage_while_avatar_walks']=True

    replacement=send_ui('Новое сообщение');fits(replacement)
    assert replacement['balloonCount']==1,replacement
    time.sleep(.6)
    c.control('btnEmoticons');c.control('Ico_wink')
    c.wait(ME+".balloonType==='mlEmoticonsBallon'")
    emotion=c.js(ME)
    assert emotion['balloonCount']==1 and emotion['speechLayout'] is None,emotion
    c.wait(ME+".balloonType===''",8)
    result['checks']['new_message_and_emotion_replace_speech_without_duplicates']=True

    with connect('ws://127.0.0.1:18080/legacy/socket',additional_headers={'Authorization':'Bearer '+peer_token}) as peer:
        def send(text):peer.send(text.encode()+b'\0')
        def receive():return peer.recv(timeout=15).decode().removesuffix('\0')
        send('<msg t="sys"><body action="verChk"/></msg>');receive()
        send('<msg t="sys"><body action="login"><login><nick>ChatPeer</nick><pword>__MOGOBE_CURRENT_SESSION__</pword></login></body></msg>')
        receive();receive()
        send(json.dumps({'t':'xt','b':{'c':'user__joinFirstRoom','p':{}}}))
        for _ in range(30):
            if 'action="joinOK"' in receive():break
        REMOTE=AVATARS+'.find(v=>v.id==='+str(peer_id)+')'
        c.wait(REMOTE+'!==undefined')
        unbroken='Ш'*240
        send('<msg t="sys"><body action="pubMsg"><txt>speak__'+unbroken+'</txt></body></msg>')
        c.wait(REMOTE+"?.speech==="+json.dumps(unbroken)+" && "+REMOTE+".speechLayout!==null")
        remote=c.js(REMOTE);fits(remote)
        result['long_bubble_duration_ms']=remote['speechLayout']['duration']
        c.capture(scope+'/07-remote-unbroken-message')
        time.sleep(4.3)
        assert c.js(REMOTE)['speech']==unbroken
        c.wait(REMOTE+".speech===''",18)
    result['checks']['remote_240_character_unbroken_speech_fits_and_expires']=True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bubbles',action='store_true',help='Also verify adaptive speech and another avatar')
    args=parser.parse_args()
    scope='chat-bubbles' if args.bubbles else 'chat'
    out=ROOT/'verification'/scope
    out.mkdir(parents=True,exist_ok=True)
    result={'suite':scope,'account_count':2 if args.bubbles else 1,'checks':{}}
    processes=[]
    bridge=None
    with tempfile.TemporaryDirectory(prefix='mogobe-chat-',ignore_cleanup_errors=True) as temporary:
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
                backend=subprocess.Popen([sys._base_executable,'run.py','--port','18080'],cwd=ROOT/'server',env=env,stdout=blog,stderr=subprocess.STDOUT)
                processes.append(backend)
                wait_http('http://127.0.0.1:18080/api/health')
                with httpx.Client(base_url='http://127.0.0.1:18080') as api:
                    assert api.post('/api/auth/registration-drafts',json={'username':'ChatNative','password':'Fish1234','color_id':7}).status_code==201
                    assert api.post('/api/auth/register',json={'age':12,'chat_mode':'open'}).status_code==201
                    if args.bubbles:
                        with httpx.Client(base_url='http://127.0.0.1:18080') as peer_api:
                            assert peer_api.post('/api/auth/registration-drafts',json={'username':'ChatPeer','password':'Fish1234','color_id':3}).status_code==201
                            response=peer_api.post('/api/auth/register',json={'age':12,'chat_mode':'open'})
                            assert response.status_code==201
                            peer_id=response.json()['id']
                            peer_token=peer_api.cookies.get('mogobe_session')
                    assert api.post('/api/auth/logout').status_code==204
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
                c.call('Page.addScriptToEvaluateOnNewDocument',source="""
                  window.publicChatPackets=0;
                  const originalSend=WebSocket.prototype.send;
                  WebSocket.prototype.send=function(data){
                    let text='';
                    if(typeof data==='string') text=data;
                    else if(data instanceof ArrayBuffer) text=new TextDecoder().decode(data);
                    else if(ArrayBuffer.isView(data)) text=new TextDecoder().decode(data);
                    if(data instanceof Blob) {
                      data.text().then(text=>{if(text.includes('pubMsg')) window.publicChatPackets++;});
                    } else if(text.includes('pubMsg')) window.publicChatPackets++;
                    return originalSend.apply(this,arguments);
                  };
                """)
                c.call('Page.navigate',url='http://127.0.0.1:18089/')
                c.wait("window.mogobeLogin?.view==='single'",60)
                c.control('txtUserName');c.type_text('ChatNative')
                c.control('txtPassword');c.type_text('Fish1234')
                c.control('btnLogin')
                c.wait("window.mogobeLogin?.view==='servers'",40)
                c.stage_click(384,140)
                c.wait("window.mogobeScene?.state==='world'",60)
                EI="window.player.ruffle().callExternalInterface"
                PANEL=EI+"('getWorldPanelInfo')"
                AVATARS=EI+"('getWorldAvatars')"
                POPUP=EI+"('getSocialPopupInfo')"

                def enter():
                    c.call('Input.dispatchKeyEvent',type='keyDown',key='Enter',code='Enter',windowsVirtualKeyCode=13)
                    c.call('Input.dispatchKeyEvent',type='keyUp',key='Enter',code='Enter',windowsVirtualKeyCode=13)

                c.control('txtSpeak');c.type_text('Привет, могоби!')
                c.wait(PANEL+".text==='Привет, могоби!'")
                time.sleep(.15)
                c.capture(scope+'/01-text-in-original-input')
                short=c.js(PANEL)
                result['input_bounds']={key:short[key] for key in ['x','y','width','height']}
                assert short['y']+short['height']<480,short
                long_text=('Длинное сообщение '+('абвгдежз ')*30)[:230]
                c.type_text(long_text)
                c.wait(PANEL+'.scrollH>0')
                assert c.js(PANEL)['text']==long_text
                c.wait(PANEL+'.caretRightGap>=3 && '+PANEL+'.caretRightGap<=6')
                c.capture(scope+'/02-long-input-scrolls')
                result['long_input']=c.js(PANEL)
                for key,code in [('Home',36),('End',35)]:
                    c.call('Input.dispatchKeyEvent',type='keyDown',key=key,code=key,windowsVirtualKeyCode=code)
                    c.call('Input.dispatchKeyEvent',type='keyUp',key=key,code=key,windowsVirtualKeyCode=code)
                    if key=='Home':c.wait(PANEL+'.scrollH===0')
                    else:c.wait(PANEL+'.caretRightGap>=3 && '+PANEL+'.caretRightGap<=6')
                result['checks']['long_input_and_cursor_scroll_preserved']=True

                before=c.js('window.publicChatPackets')
                for method in ['button','enter']:
                    for blank in ['', ' ', '    ']:
                        c.control('txtSpeak');c.type_text(blank)
                        if not blank:
                            c.call('Input.dispatchKeyEvent',type='keyDown',key='Backspace',code='Backspace',windowsVirtualKeyCode=8)
                            c.call('Input.dispatchKeyEvent',type='keyUp',key='Backspace',code='Backspace',windowsVirtualKeyCode=8)
                        c.wait(PANEL+'.text==='+json.dumps(blank))
                        if method=='button':c.control('btnSend')
                        else:enter()
                        c.wait(PANEL+".text===''")
                        time.sleep(.2)
                        assert c.js(POPUP+'===null'),(method,repr(blank),c.js(POPUP))
                        assert not c.js("window.mogobePopup?.state==='open'")
                        assert c.js('window.publicChatPackets')==before,(method,repr(blank))
                result['checks']['empty_and_spaces_are_ignored_for_button_and_enter_without_popup_or_packet']=True
                c.capture(scope+'/03-after-empty-sends')

                for message,method in [('Привет, могоби!','button'),('Сообщение через Enter','enter')]:
                    c.control('txtSpeak');c.type_text(message)
                    c.wait(PANEL+'.text==='+json.dumps(message))
                    if method=='button':c.control('btnSend')
                    else:enter()
                    c.wait(AVATARS+".some(v=>v.me && v.speech.includes("+json.dumps(message)+"))")
                    c.wait(PANEL+".text===''")
                    time.sleep(.6)
                assert c.js('window.publicChatPackets')==before+2
                result['checks']['real_messages_still_send_with_both_controls']=True
                if args.bubbles:check_bubbles(c,result,peer_token,peer_id,scope)
                c.chat_send('/help')
                c.wait("window.mogobePopup?.state==='open' && window.mogobePopup.original===true")
                assert '/room' in c.js('window.mogobePopup.message')
                c.popup_confirm()
                c.chat_send('/exit')
                c.wait("window.mogobeScene?.state==='lobby'",40)
                result['checks']['help_and_exit_commands_preserved']=True
            except Exception:
                result['error']=traceback.format_exc()
                if bridge:
                    try:
                        result['state']=bridge.js("JSON.stringify({scene:window.mogobeScene,panel:window.player?.ruffle().callExternalInterface('getWorldPanelInfo'),avatars:window.player?.ruffle().callExternalInterface('getWorldAvatars'),originalPopup:window.player?.ruffle().callExternalInterface('getSocialPopupInfo'),popup:window.mogobePopup,publicChatPackets:window.publicChatPackets})")
                        bridge.capture(scope+'/failure')
                    except Exception:pass
            finally:
                for process in reversed(processes):
                    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True)
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:process.kill()
    result['passed']=not result.get('error') and all(result['checks'].values())
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True,indent=2),flush=True)
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
