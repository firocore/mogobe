"""One muted headless account: chat editing, blank sends and local commands."""
import argparse
import json
import os
import re
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


def check_chat_layout(c,result,scope):
    EI="window.player.ruffle().callExternalInterface"
    HISTORY=EI+"('getChatHistoryInfo')"
    PANEL=EI+"('getWorldPanelInfo')"

    def inspect():
        info=c.js(HISTORY)
        body,bar=info['body'],info['bar']
        assert abs(body['x']+body['width']/2-384)<.2,info
        assert 0<=body['y']+body['height']-bar['y']<=2,info
        assert '\n\n' not in info['text'],info
        if info['open']:
            assert info['lowerButtonVisible'] and not info['upperButtonVisible'],info
            assert info['buttonFrame']==17,info
            assert abs(info['y']-(body['y']+body['height']))<1.5,info
            assert 0<info['y']+info['height']-c.js(PANEL)['y']<6,info
        else:
            assert info['upperButtonVisible'] and not info['lowerButtonVisible'],info
            assert info['buttonFrame'] in [1,5],info
        return info

    def toggle():
        info=c.js(HISTORY)
        x,y=info['x']+info['width']/2,info['y']+info['height']/2
        frame=c.js("(()=>{if(document.fullscreenElement!==window.player)return null;const e=player.shadowRoot.querySelector('#container'),r=e.getBoundingClientRect(),b=parseFloat(getComputedStyle(e).borderLeftWidth);return {x:r.x+b,y:r.y+b,width:r.width-2*b,height:r.height-2*b}})()")
        if frame:c.click(frame['x']+x*frame['width']/768,frame['y']+y*frame['height']/480)
        else:c.stage_click(x,y)
        c.wait(HISTORY+'.open==='+str(not info['open']).lower())
        return inspect()

    def leave_button():
        stage=c.js("document.getElementById('stage').getBoundingClientRect().toJSON()")
        c.call('Input.dispatchMouseEvent',type='mouseMoved',x=stage['x']+20*stage['width']/768,y=stage['y']+20*stage['height']/480)
        time.sleep(.15)
        return inspect()

    info=inspect()
    assert len(info['lines'])==4 and all(row['text'] for row in info['lines']),info
    for row,line in zip(info['rows'],info['lines']):
        stamp=row['received_at']
        local=time.localtime(stamp/1000)
        expected=time.strftime('[%H:%M]',local)+' '+row['sender']+': '+row['text']
        assert line['text']==expected,line
        assert re.match(r'^\[\d{2}:\d{2}\] ',line['text']),line
        assert line['timeColor']==0xbfc8b8 and line['nameColor']==0xd8efa7,line
    result['checks']['receive_times_use_local_hh_mm_and_separate_time_and_name_colours']=True
    assert all(0<info['lines'][i+1]['y']-info['lines'][i]['y']<18 for i in range(3)),info
    result['checks']['short_messages_have_compact_spacing_without_empty_rows']=True
    c.capture(scope+'/04-open-docked-history')
    for _ in range(3):
        opened=leave_button()
        closed=toggle()
        assert opened['y']>closed['y']+5,(opened,closed)
        leave_button()
        toggle()
    result['checks']['original_upper_and_lower_buttons_alternate_and_stay_correct_after_hover']=True
    toggle();c.capture(scope+'/05-upper-button-when-closed');toggle()
    result['checks']['history_joins_bar_and_lower_button_attaches_to_pane_edge']=True
    for i in range(5):
        text='Сообщение '+str(i)+': '+('проверка переноса текста в истории. '*5)
        before=c.js(HISTORY)['count']
        c.control('txtSpeak');c.type_text(text)
        c.wait(PANEL+'.text==='+json.dumps(text))
        c.control('btnSend')
        c.wait(HISTORY+'.count==='+str(before+1))
        time.sleep(.6)
    info=inspect()
    assert len(info['lines'])==8 and info['lines'][-1]['end']==len(info['text']),info
    for line in info['lines']:
        assert line['text'] and line['textWidth']<=line['width']-3.5,line
        assert line['textHeight']+3.5<=line['height'],line
        assert line['text']==info['text'][line['start']:line['end']],line
    c.capture(scope+'/06-compact-wrapped-history')
    stage=c.js("document.getElementById('stage').getBoundingClientRect().toJSON()")
    c.call('Input.dispatchMouseEvent',type='mouseMoved',x=stage['x']+384*stage['width']/768,y=stage['y']+350*stage['height']/480)
    c.call('Input.dispatchMouseEvent',type='mouseWheel',x=stage['x']+384*stage['width']/768,y=stage['y']+350*stage['height']/480,deltaX=0,deltaY=-500)
    c.wait(HISTORY+'.scroll<'+HISTORY+'.maxScroll')
    saved=c.js(HISTORY)['scroll']
    c.control('txtSpeak');c.type_text('Новое сообщение при чтении истории')
    c.wait(PANEL+".text==='Новое сообщение при чтении истории'")
    c.control('btnSend')
    c.wait(HISTORY+".rows.at(-1).text==='Новое сообщение при чтении истории'")
    assert c.js(HISTORY)['scroll']==saved
    inspect()
    result['checks']['compact_wrapping_scrolling_and_reading_position_preserved']=True
    response=c.call('Runtime.evaluate',expression="Element.prototype.requestFullscreen.call(window.player)",awaitPromise=True,userGesture=True,returnByValue=True)
    assert 'exceptionDetails' not in response,response
    c.wait('document.fullscreenElement===window.player')
    inspect();c.capture(scope+'/07-docked-history-fullscreen')
    toggle();leave_button();toggle();inspect()
    c.js('document.exitFullscreen()');c.wait('document.fullscreenElement===null')
    inspect()
    result['checks']['docking_and_button_visibility_preserved_in_fullscreen']=True
    retained=c.js(HISTORY)['rows']
    c.js('window.chatTimeGeneration=true;window.onMogobeReconnect()')
    c.wait("window.chatTimeGeneration===undefined && window.mogobeScene?.state==='world'",60)
    c.wait(HISTORY+'.count==='+str(len(retained)),30)
    assert c.js(HISTORY)['rows']==retained
    info=c.js(HISTORY)
    last=retained[-1]
    expected=time.strftime('[%H:%M]',time.localtime(last['received_at']/1000))+' '+last['sender']+': '+last['text']
    assert info['text'].endswith(expected),info
    result['checks']['receive_times_survive_f5_without_being_recreated']=True


def check_history(c,result,peer_token,peer_id,scope):
    from websockets.sync.client import connect
    EI="window.player.ruffle().callExternalInterface"
    HISTORY=EI+"('getChatHistoryInfo')"
    AVATARS=EI+"('getWorldAvatars')"

    def geometry():
        info=c.js(HISTORY)
        body=info['body']
        assert abs(body['x']+body['width']/2-384)<.2,info
        assert 95<=info['fillAlpha']<=110,info
        assert info['embedded'] and info['font']=='Arial',info
        content=info['text']
        for line in info['lines']:
            t=(line['y']+line['height']-(body['y']+1))/152.75
            left=body['x']+1+14.95*t
            right=body['x']+body['width']-1-13.1*t
            assert line['x']>=left+5 and line['x']+line['width']<=right-5,line
            assert line['textWidth']<=line['width']-3.5,line
            if line['text']:
                assert line['textWidth']>0 and line['textHeight']>0,line
                assert line['textHeight']+3.5<=line['height'],line
            assert line['text']==content[line['start']:line['end']],line
        return info

    def toggle():
        info=c.js(HISTORY)
        c.stage_click(info['x']+info['width']/2,info['y']+info['height']/2)

    # Leave the original quick-phrase menu functional beside the new toggle.
    toggle();c.wait('!'+HISTORY+'.open')
    c.control('btnCloseChat')
    menu=EI+"('getChatMenuItems')"
    for text in ['Приветствия','Привет!']:
        c.wait(menu+'.some(v=>v.text==='+json.dumps(text)+')')
        box=c.js(menu+'.find(v=>v.text==='+json.dumps(text)+')')
        if text=='Приветствия':
            stage=c.js("document.getElementById('stage').getBoundingClientRect().toJSON()")
            c.call('Input.dispatchMouseEvent',type='mouseMoved',x=stage['x']+(box['x']+box['width']/2)*stage['width']/768,y=stage['y']+(box['y']+box['height']/2)*stage['height']/480)
        else:c.stage_click(box['x']+box['width']/2,box['y']+box['height']/2)
    c.wait(HISTORY+".rows.some(r=>r.text==='Привет!')")
    result['checks']['original_quick_phrase_is_recorded_as_text']=True

    with connect('ws://127.0.0.1:18080/legacy/socket',additional_headers={'Authorization':'Bearer '+peer_token}) as peer:
        def send(text):peer.send(text.encode()+b'\0')
        def receive():return peer.recv(timeout=15).decode().removesuffix('\0')
        def speak(text,action='speak'):
            from xml.sax.saxutils import escape
            send('<msg t="sys"><body action="pubMsg"><txt>'+action+'__'+escape(text)+'</txt></body></msg>')
            for _ in range(40):
                packet=receive()
                if 'action="pubMsg"' in packet:break
            time.sleep(.55)
        send('<msg t="sys"><body action="verChk"/></msg>');receive()
        send('<msg t="sys"><body action="login"><login><nick>ChatPeer</nick><pword>__MOGOBE_CURRENT_SESSION__</pword></login></body></msg>')
        receive();receive()
        send(json.dumps({'t':'xt','b':{'c':'user__joinFirstRoom','p':{}}}))
        for _ in range(30):
            if 'action="joinOK"' in receive():break
        c.wait(AVATARS+'.some(v=>v.id==='+str(peer_id)+')')
        literal='<b> & Привет!'
        speak(literal);speak(literal)
        c.wait(HISTORY+'.rows.filter(r=>r.text==='+json.dumps(literal)+').length===2')
        assert c.js(HISTORY)['rows'][-1]['sender']=='ChatPeer'
        result['checks']['remote_names_literal_text_and_repeated_messages_preserved']=True
        before=c.js(HISTORY)['count']
        speak('Ico_wink','emoticons')
        time.sleep(.7)
        assert c.js(HISTORY)['count']==before
        result['checks']['emotions_are_not_added_as_chat_text']=True
        for i in range(14):speak('Запись '+str(i)+': '+('Длинный текст для проверки переноса строк. '*4))
        c.wait(HISTORY+'.count==='+str(before+14))
        toggle();c.wait(HISTORY+'.open && '+HISTORY+'.maxScroll>1')
        c.wait(HISTORY+'.scroll==='+HISTORY+'.maxScroll')
        info=geometry()
        assert len(info['lines'])==8 and info['lines'][0]['slot']==0 and info['lines'][-1]['slot']==7,info
        assert info['lines'][0]['width']>info['lines'][-1]['width']+15,info
        assert info['body']['y']+info['body']['height']-(info['lines'][-1]['y']+info['lines'][-1]['height'])<9,info
        assert '\n\n' not in info['text'],info
        assert all(row['text'] for row in info['lines']),info
        assert any(row['nameColor']==0xd8efa7 for row in info['lines']),info
        result['history_geometry']=info
        result['checks']['history_centred_translucent_and_text_fills_tapered_panel']=True
        c.capture(scope+'/04-original-history-with-two-players')
        response=c.call('Runtime.evaluate',expression="Element.prototype.requestFullscreen.call(window.player)",awaitPromise=True,userGesture=True,returnByValue=True)
        assert 'exceptionDetails' not in response,response
        c.wait('document.fullscreenElement===window.player')
        geometry()
        c.capture(scope+'/04b-centred-history-fullscreen')
        c.js('document.exitFullscreen()')
        c.wait('document.fullscreenElement===null')
        result['checks']['history_keeps_centre_and_contour_in_fullscreen']=True
        stage=c.js("document.getElementById('stage').getBoundingClientRect().toJSON()")
        def wheel(delta):
            c.call('Input.dispatchMouseEvent',type='mouseWheel',x=stage['x']+384*stage['width']/768,y=stage['y']+350*stage['height']/480,deltaX=0,deltaY=delta)
        wheel(-500)
        c.wait(HISTORY+'.scroll<'+HISTORY+'.maxScroll')
        geometry()
        saved=c.js(HISTORY)['scroll']
        speak('После прокрутки')
        c.wait(HISTORY+".rows.some(r=>r.text==='После прокрутки')")
        assert c.js(HISTORY)['scroll']==saved
        geometry()
        c.capture(scope+'/05-history-scrolled-up')
        result['checks']['history_wraps_scrolls_and_does_not_jump_during_reading']=True
        unbroken='Ш'*240
        speak(unbroken)
        c.wait(HISTORY+'.rows.some(r=>r.text==='+json.dumps(unbroken)+')')
        for _ in range(12):
            wheel(500)
            if c.js(HISTORY+'.scroll==='+HISTORY+'.maxScroll'):break
        c.wait(HISTORY+'.scroll==='+HISTORY+'.maxScroll')
        info=geometry()
        assert info['lines'][-1]['end']==len(info['text']),info
        assert all(row['text'] and set(row['text'])=={'Ш'} for row in info['lines']),info
        c.capture(scope+'/05b-unbroken-text-inside-contour')
        result['checks']['unbroken_240_character_message_fits_without_clipping_last_line']=True
        response=c.js("fetch('/api/social/mute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'ChatPeer',muted:true})}).then(r=>r.status)")
        assert response==200,response
        before=c.js(HISTORY)['count']
        speak('Скрытое сообщение')
        time.sleep(1)
        assert c.js(HISTORY)['count']==before
        assert 'Скрытое сообщение' not in c.js(HISTORY)['text']
        result['checks']['muted_speech_does_not_enter_history']=True
    retained=c.js(HISTORY)['rows']
    c.chat_send('/room infoboard')
    c.wait("window.mogobeScene?.state==='world' && window.mogobeScene?.room==='infoboard'",40)
    c.wait(HISTORY+'.ready')
    assert c.js(HISTORY)['rows']==retained
    c.js('window.chatHistoryGeneration=true;window.onMogobeReconnect()')
    c.wait("window.chatHistoryGeneration===undefined && window.mogobeScene?.state==='world' && window.mogobeScene?.room==='infoboard'",60)
    c.wait(HISTORY+'.count==='+str(len(retained)),30)
    assert c.js(HISTORY)['rows']==retained
    c.capture(scope+'/06-history-after-reconnect')
    result['checks']['history_survives_room_change_and_f5']=True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bubbles',action='store_true',help='Also verify adaptive speech and another avatar')
    parser.add_argument('--history',action='store_true',help='Verify original chat history with another player')
    parser.add_argument('--layout',action='store_true',help='One-account compact history, docking and original buttons')
    args=parser.parse_args()
    scope='chat-layout' if args.layout else 'chat-history' if args.history else 'chat-bubbles' if args.bubbles else 'chat'
    out=ROOT/'verification'/scope
    out.mkdir(parents=True,exist_ok=True)
    result={'suite':scope,'account_count':2 if args.bubbles or args.history else 1,'checks':{}}
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
                    if args.bubbles or args.history:
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

                for message,method in [('Привет, могоби!','button'),('Сообщение через Enter','enter'),('Я','button'),('?','enter')]:
                    c.control('txtSpeak');c.type_text(message)
                    c.wait(PANEL+'.text==='+json.dumps(message))
                    if method=='button':c.control('btnSend')
                    else:enter()
                    c.wait(AVATARS+".some(v=>v.me && v.speech.includes("+json.dumps(message)+"))")
                    c.wait(PANEL+".text===''")
                    time.sleep(.6)
                assert c.js('window.publicChatPackets')==before+2
                result['checks']['real_messages_still_send_with_both_controls']=True
                result['checks']['single_character_messages_send_with_both_controls']=True
                HISTORY=EI+"('getChatHistoryInfo')"
                c.wait(HISTORY+'.ready && '+HISTORY+'.count===4')
                info=c.js(HISTORY)
                assert [r['text'] for r in info['rows']][-2:]==['Я','?'],info
                c.stage_click(info['x']+info['width']/2,info['y']+info['height']/2)
                c.wait(HISTORY+'.open')
                c.capture(scope+'/03b-original-history-panel')
                result['checks']['original_history_displays_own_single_character_messages']=True
                if args.layout:check_chat_layout(c,result,scope)
                if args.history:check_history(c,result,peer_token,peer_id,scope)
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
                        result['history']=bridge.js("window.player?.ruffle().callExternalInterface('getChatHistoryInfo')")
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
