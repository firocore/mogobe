"""Focused two-window integration check. No six-account suite is run."""
import argparse
import json
import sqlite3
from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
import traceback

import httpx

from verify_desktop import CLIENT, ROOT, DesktopBridge, wait_http

OUT = ROOT / "verification/multiplayer"
AVATARS = "window.player.ruffle().callExternalInterface('getWorldAvatars')"


def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commands',action='store_true',help='Public room/shop commands, privileged give targets, original help and global alerts')
    parser.add_argument('--wardrobe',action='store_true',help='Original inventory wear, multiplayer clothing, reconnect and clipboard photo')
    parser.add_argument('--room-links',action='store_true',help='Terem exhibition, forest tree/cave and port ship doors')
    parser.add_argument('--map-timing',action='store_true',help='First visible map frame, cached graphics and removed birch')
    parser.add_argument('--map-ui',action='store_true',help='Original Bumagland button/island and corrected shop/pool doors')
    parser.add_argument('--rooms',action='store_true',help='Original world map, room transitions and player isolation')
    parser.add_argument('--rooms-all',action='store_true',help='Also enter every imported walkable room once')
    parser.add_argument('--layout',action='store_true',help='First offline hover, profile first frames, left chat input and hidden dance button')
    parser.add_argument('--presence',action='store_true',help='Live server population, friends indicator and online transitions')
    parser.add_argument('--friends-ui',action='store_true',help='Focused hover, optimistic mute and F5 regression check')
    parser.add_argument('--profiles',action='store_true',help='Only verify own/other original profile cards')
    parser.add_argument('--friends-only',action='store_true',help='Friends and mute without repeating magic checks')
    parser.add_argument('--social',action='store_true',help='Emotions, magic, friends and personal mute')
    args = parser.parse_args()
    if args.friends_ui: args.friends_only = True
    if args.rooms_all: args.rooms = True
    scope = 'commands' if args.commands else 'wardrobe' if args.wardrobe else 'room-links' if args.room_links else 'map-timing' if args.map_timing else 'map-ui' if args.map_ui else 'rooms-all' if args.rooms_all else 'rooms' if args.rooms else 'layout' if args.layout else 'friends-ui' if args.friends_ui else 'presence' if args.presence else 'friends' if args.friends_only else 'social' if args.social else 'profiles' if args.profiles else 'multiplayer'
    OUT = ROOT/'verification'/scope
    OUT.mkdir(parents=True, exist_ok=True)
    result = {"suite":scope, "account_count":2, "checks":{}}
    processes = []
    clients = []
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="mogobe-multiplayer-", ignore_cleanup_errors=True) as temporary:
        directory = Path(temporary)
        with (OUT/"backend.log").open("w",encoding="utf-8") as server_log, (OUT/"client.log").open("w",encoding="utf-8") as client_log:
            try:
                env = os.environ.copy()
                env["MOGOBE_BOOTSTRAP_DEFAULTS"]="false"
                if args.presence: env["MOGOBE_SERVER_NAME"] = "Тестовый мир"
                env["MOGOBE_DATABASE_URL"] = "sqlite+aiosqlite:///"+(directory/"world.sqlite3").as_posix()
                env["PYTHONPATH"] = str(ROOT/"server/.venv/Lib/site-packages")
                processes.append(subprocess.Popen([sys._base_executable,"run.py","--port","18080"],cwd=ROOT/"server",env=env,stdout=server_log,stderr=subprocess.STDOUT))
                wait_http("http://127.0.0.1:18080/api/health")
                ids = []
                second_name = "Могоби_2" if args.social or args.friends_only or args.presence or args.layout else "Player_2"
                with httpx.Client(base_url="http://127.0.0.1:18080") as api:
                    for name,color in [("Player_1",3),(second_name,7)]:
                        assert api.post("/api/auth/registration-drafts",json={"username":name,"password":"Player123","color_id":color}).status_code == 201
                        reply = api.post("/api/auth/register",json={"age":12,"chat_mode":"open"})
                        assert reply.status_code == 201
                        ids.append(reply.json()["id"])
                        assert api.post("/api/auth/logout").status_code == 204
                if args.commands:
                    with sqlite3.connect(directory/"world.sqlite3") as db:
                        db.execute("UPDATE auth_account SET is_admin=1 WHERE username='Player_1'")
                        db.execute("INSERT INTO shop_item(id,name,main_type,inventory_category,enabled) VALUES (100,'Рубашка',1,4,1)")
                    with httpx.Client(base_url='http://127.0.0.1:18080') as manager:
                        assert manager.post('/api/admin/login',json={'username':'Player_1','password':'Player123'}).status_code==200
                        for key,private in [('open',False),('private',True)]:
                            assert manager.put('/api/admin/shops/'+key,json={'key':key,'title':key,'admin_only':private}).status_code==200
                if args.wardrobe:
                    with sqlite3.connect(directory/"world.sqlite3") as db:
                        for item in (100,101):
                            db.execute("INSERT INTO shop_item(id,name,main_type,inventory_category,enabled) VALUES (?,?,1,4,1)",(item,str(item)))
                            db.execute("INSERT INTO shop_owned_item(account_id,item_id) VALUES (?,?)",(ids[0],item))
                if args.profiles:
                    with sqlite3.connect(directory/"world.sqlite3") as db:
                        for ident,days in zip(ids,[5,17]):
                            instant = datetime.now(UTC).replace(tzinfo=None)-timedelta(days=days,hours=2)
                            db.execute("UPDATE auth_account SET created_at=? WHERE id=?",(instant.isoformat(" "),ident))
                if args.presence or args.layout:
                    with sqlite3.connect(directory/"world.sqlite3") as db:
                        db.execute("INSERT INTO social_friendship(first_id,second_id) VALUES (?,?)",tuple(sorted(ids)))
                config = directory/"client.json"
                config.write_text(json.dumps({"server_url":"http://127.0.0.1:18080","request_timeout_seconds":5}),encoding="utf-8")

                def start_client(index):
                    client_env = env.copy()
                    client_env["MOGOBE_UI_TEST_SECRET"] = secrets.token_urlsafe(32)
                    client_env["MOGOBE_UI_TEST_PORT"] = str(19225+index)
                    client_env["MOGOBE_UI_TEST_PROFILE"] = str(directory/"profiles")
                    process = subprocess.Popen([str(CLIENT),"--config",str(config)],cwd=directory,env=client_env,stdout=client_log,stderr=subprocess.STDOUT)
                    processes.append(process)
                    time.sleep(2)
                    bridge = DesktopBridge(process,client_env["MOGOBE_UI_TEST_SECRET"],19225+index)
                    clients.append(bridge)
                    bridge.wait("window.mogobeLogin?.view === 'single'",60)
                    if args.friends_ui:
                        bridge.js("window.socialFetches=0;window.countedFetch=window.fetch;window.fetch=(url,options)=>{if(url==='/api/social/me')window.socialFetches++;return window.countedFetch(url,options)}")
                    return process,bridge

                def login(c,name):
                    c.control("txtUserName");c.type_text(name)
                    c.control("txtPassword");c.type_text("Player123")
                    c.control("btnLogin")

                def enter(c):
                    c.wait("window.mogobeLogin?.view === 'servers'")
                    c.stage_click(384,140)
                    c.wait("window.mogobeScene?.state === 'world'",60)
                    # Interaction suites explicitly use the original test room;
                    # the one-account world/spawns suites verify Novograd entry.
                    c.chat_send('/room InfoBoard')
                    c.wait("window.mogobeScene?.state === 'world' && window.mogobeScene?.room === 'infoboard'",45)

                first,a = start_client(0)
                login(a,"Player_1");enter(a)
                second,b = start_client(1)
                a.user32.MoveWindow(a.hwnd,0,20,900,640,True)
                b.user32.MoveWindow(b.hwnd,max(100,b.user32.GetSystemMetrics(0)-900),20,900,640,True)
                login(b,second_name)
                if not (args.presence or args.layout): enter(b)
                for c in () if args.presence or args.layout else (a,b):
                    c.wait(AVATARS+".length === 2")
                    avatars = c.js(AVATARS)
                    assert {v["id"] for v in avatars} == set(ids)
                    assert {v["colorId"] for v in avatars} == {3,7}
                if args.commands:
                    def popup_info(c):return c.js("window.registrationPopupPlayer.ruffle().callExternalInterface('getMessageInfo')")
                    for c,admin in [(a,True),(b,False)]:
                        c.chat_send('/help')
                        c.wait("window.mogobePopup?.state==='open' && window.mogobePopup.original===true",30)
                        message=c.js('window.mogobePopup.message')
                        assert '/room ключ' in message and '/shop ключ' in message
                        assert ('/give coins' in message)==admin and ('/alert текст' in message)==admin
                        panel=popup_info(c)
                        assert panel['textBottom']<panel['buttonTop'] or panel['textRight']<panel['buttonLeft'],panel
                        assert panel['panel']['y']>=0 and panel['panel']['y']+panel['panel']['height']<=480,panel
                        c.capture(scope+('/01-admin-help' if admin else '/02-player-help'))
                        c.popup_confirm()
                    result['checks']['original_help_panel_fits_all_lines_and_shows_commands_for_current_role']=True
                    a.chat_send('/give coins 75 Player_2')
                    b.wait("fetch('/api/inventory').then(r=>r.json()).then(x=>x.coins===75)")
                    a.chat_send('/give exp 1500 Player_2')
                    b.wait("window.player.ruffle().callExternalInterface('getExperienceInfo')?.shown>0")
                    a.wait("fetch('/api/inventory').then(r=>r.json()).then(x=>x.coins===0)")
                    assert a.js("window.player.ruffle().callExternalInterface('getExperienceInfo').shown")==0
                    a.chat_send('/give item 100 Player_2')
                    b.wait("fetch('/api/inventory').then(r=>r.json()).then(x=>x.items.some(i=>i.typeId===100))")
                    a.chat_send('/give coins 10')
                    a.wait("fetch('/api/inventory').then(r=>r.json()).then(x=>x.coins===10)")
                    a.chat_send('/give exp 500')
                    a.wait("window.player.ruffle().callExternalInterface('getExperienceInfo')?.shown>0")
                    a.chat_send('/give item 100')
                    a.wait("fetch('/api/inventory').then(r=>r.json()).then(x=>x.items.some(i=>i.typeId===100))")
                    result['checks']['give_coins_item_and_exp_support_target_or_self_and_score_popup_is_recipient_only']=True
                    b.chat_send('/shop open')
                    b.wait("window.player.ruffle().callExternalInterface('getShopInfo')?.key==='open'",30)
                    b.js("window.player.ruffle().callExternalInterface('closeOriginalShop')")
                    b.chat_send('/shop private')
                    b.wait(AVATARS+f".find(v=>v.id==={ids[1]})?.speech.includes('недоступен')",20)
                    assert b.js("window.player.ruffle().callExternalInterface('getShopInfo')")==None
                    a.chat_send('/shop private')
                    a.wait("window.player.ruffle().callExternalInterface('getShopInfo')?.key==='private'",30)
                    a.js("window.player.ruffle().callExternalInterface('closeOriginalShop')")
                    b.chat_send('/room Novograd')
                    b.wait("window.mogobeScene?.state==='world' && window.mogobeScene?.room==='novograd'",45)
                    result['checks']['room_and_shop_public_commands_respect_private_shop_access']=True
                    b.chat_send('/help');b.wait("window.mogobePopup?.state==='open'",30)
                    a.chat_send('/alert Проверка объявления всем игрокам')
                    a.wait("window.mogobePopup?.state==='open' && window.mogobePopup.original && window.mogobePopup.message.includes('Проверка объявления')",30)
                    assert b.js("window.mogobePopup.message.startsWith('Доступные команды')")
                    b.popup_confirm(next_message='Проверка объявления')
                    b.wait("window.mogobePopup?.state==='open' && window.mogobePopup.original && window.mogobePopup.message.includes('Проверка объявления')",30)
                    b.capture(scope+'/03-alert-in-another-room')
                    a.popup_confirm();b.popup_confirm()
                    result['checks']['global_alert_reaches_both_rooms_and_waits_for_open_help_panel']=True
                elif args.wardrobe:
                    from PIL import ImageGrab
                    info="window.player.ruffle().callExternalInterface('getProfileInfo')"
                    inventory="window.player.ruffle().callExternalInterface('getInventoryInfo')"
                    def profile_button(name):
                        box=a.js("window.player.ruffle().callExternalInterface('getProfileControlBounds',"+json.dumps(name)+")")
                        assert box,name
                        a.stage_click(box['x']+box['width']/2,box['y']+box['height']/2)
                    a.control('btnProfile');a.wait(info+"?.visible===true && "+info+"?.popupId===7")
                    profile_button('btnCamera')
                    a.wait("window.mogobeLastPhoto?.copied===true",30)
                    naked=ImageGrab.grabclipboard();assert naked is not None
                    naked.save(OUT/'01-avatar-before.png')
                    result['checks']['original_camera_copies_image_to_windows_clipboard']=True
                    profile_button('mc_4_8_13_14_21')
                    a.wait(inventory+"?.cells.length===2",30)
                    cells=a.js(inventory)['cells'];cell=next(i for i in cells if i['typeId']==100)
                    a.stage_click(cell['x']+cell['width']/2,cell['y']+cell['height']/2)
                    a.wait("fetch('/api/inventory/equipped').then(r=>r.json()).then(x=>x.items.length===1&&x.items[0].typeId===100)",20)
                    for c in (a,b): c.wait(AVATARS+f".find(v=>v.id==={ids[0]})?.clothing.some(c=>c.type==='mlIconSItem100')",30)
                    a.wait(inventory+"?.clothing.some(c=>c.type==='mlBigItem100')",30)
                    result['checks']['original_inventory_equips_and_both_players_render_clothing']=True
                    a.js('window.mogobeLastPhoto=null');profile_button('btnCamera')
                    a.wait("window.mogobeLastPhoto?.copied===true",30)
                    dressed=ImageGrab.grabclipboard();assert dressed is not None
                    purple=sum(1 for r,g,b in dressed.convert('RGB').getdata() if r>g*1.25 and b>g*1.25 and r>45 and b>45)
                    assert purple>500,('Clothing missing from clipboard image',purple)
                    dressed.save(OUT/'02-avatar-with-shirt.png')
                    result['checks']['clipboard_portrait_includes_original_clothes']=True
                    a.capture(scope+'/03-profile-shirt')
                    profile_button('btnClose');a.wait(info+'===null')
                    a.stage_click(440,392)
                    a.wait(AVATARS+f".find(v=>v.id==={ids[0]})?.x>420",20)
                    b.wait(AVATARS+f".find(v=>v.id==={ids[0]})?.x>420",20)
                    for c in (a,b): assert any(v['type']=='mlIconWItem100' for v in c.js(AVATARS+f".find(v=>v.id==={ids[0]})")['clothing'])
                    result['checks']['original_standing_and_walking_timelines_present_on_both_clients']=True
                    b.capture(scope+'/04-observer-sees-shirt')
                    a.js('window.onMogobeReconnect()');a.wait("window.mogobeScene?.state==='world' && window.mogobeScene?.room==='infoboard'",60)
                    a.wait(AVATARS+f".find(v=>v.id==={ids[0]})?.clothing.some(c=>c.type==='mlIconSItem100')",30)
                    result['checks']['outfit_survives_F5_reconnect_in_same_room']=True
                    a.control('btnProfile');a.wait(info+'?.visible===true')
                    a.wait(inventory+"?.clothing.some(c=>c.type==='mlBigItem100')",30)
                    shirt=next(c for c in a.js(inventory)['clothing'] if c['type']=='mlBigItem100')
                    a.stage_click(shirt['x']+shirt['width']/2,shirt['y']+shirt['height']/2)
                    a.wait("fetch('/api/inventory/equipped').then(r=>r.json()).then(x=>x.items.length===0)",20)
                    for c in (a,b):c.wait(AVATARS+f".find(v=>v.id==={ids[0]})?.clothing.length===0",30)
                    profile_button('mc_4_8_13_14_21');a.wait(inventory+'?.cells.length===2',20)
                    result['checks']['click_on_worn_shirt_unequips_for_everyone_and_returns_inventory']=True
                    profile_button('btnClose')
                elif args.room_links:
                    navigation={r["key"]:r for r in json.loads((ROOT/"server/src/world/rooms.json").read_text(encoding="utf-8"))["rooms"]}
                    def wait_room(name):
                        a.wait("window.mogobeScene?.state==='world' && window.mogobeScene?.room==="+json.dumps(name.lower()),45)
                        a.wait("window.player.ruffle().callExternalInterface('getWorldAvatar')?.visible === true",20)
                        state=a.js("fetch('/api/world/me').then(r=>r.json())")
                        assert state['room']==name.lower(),state
                    def door(token,name):
                        bounds=a.js("window.player.ruffle().callExternalInterface('getLoginControlBounds',"+json.dumps('mcEntryPoint_'+token)+")")
                        assert bounds,(token,name)
                        x=max(8,min(760,bounds['x']+bounds['width']/2))
                        y=max(8,min(440,bounds['y']+bounds['height']/2))
                        assert 0<bounds['y']<480,(token,bounds)
                        # Long edge triggers include rocks and snow. Click a
                        # reachable piece of the original trigger rather than
                        # the middle of its bounding box above the path.
                        key=a.js("window.mogobeScene.room")
                        room=navigation[key]
                        points=[(gx*8+4,gy*8+4) for gy,row in enumerate(room['grid']) for gx,v in enumerate(row)
                            if v=='1' and bounds['x']+4<=gx*8+4<=bounds['x']+bounds['width']-4
                            and bounds['y']+4<=gy*8+4<=min(440,bounds['y']+bounds['height']-4)
                            and 8<=gx*8+4<=760]
                        if points: x,y=min(points,key=lambda p:(p[0]-x)**2+(p[1]-y)**2)
                        a.stage_click(x,y);wait_room(name)
                    a.chat_send('/room JewelryStore');wait_room('JewelryStore')
                    door('82','JewelryExhibition');a.capture(scope+'/01-jewelry-exhibition')
                    door('76','JewelryStore')
                    result['checks']['inner_terem_door_opens_jewelry_exhibition_and_returns']=True
                    a.chat_send('/room MagicForest');wait_room('MagicForest')
                    bounds=a.js("window.player.ruffle().callExternalInterface('getLoginControlBounds','mcEntryPoint_440')")
                    assert 99<bounds['x']<101 and 329<bounds['y']<331,bounds
                    a.capture(scope+'/02-forest-tree-door')
                    door('440','ForestTree');a.capture(scope+'/03-inside-tree')
                    door('74','MagicForest')
                    result['checks']['restored_left_tree_door_works_both_ways']=True
                    door('78','FearCaveGate');a.capture(scope+'/04-fear-cave-gate')
                    door('74','MagicForest')
                    result['checks']['forest_path_opens_fear_cave_gate_and_returns']=True
                    a.chat_send('/room Port');wait_room('Port')
                    door('21','Ship');a.capture(scope+'/05-ship')
                    door('9','Port')
                    result['checks']['port_ship_entrance_works_both_ways']=True
                    a.chat_send('/room InfoBoard');wait_room('InfoBoard')
                    a.wait(AVATARS+'.length === 2');b.wait(AVATARS+'.length === 2')
                    result['checks']['both_players_still_see_each_other_after_travel']=True
                    a.chat_send('/exit');a.wait("window.mogobeLogin?.view === 'saved'",40)
                elif args.map_timing:
                    map_info = "window.player.ruffle().callExternalInterface('getWorldMapInfo')"
                    a.js("window.mapFrames=[];window.mapRecording=true;window.mapTick=()=>{if(!window.mapRecording)return;let m="+map_info+";if(m)window.mapFrames.push(m);requestAnimationFrame(window.mapTick)};requestAnimationFrame(window.mapTick)")
                    for index in range(3):
                        a.wait("window.player.ruffle().callExternalInterface('getLoginControlBounds','btnMap')?.enabled === true",12)
                        a.control('btnMap')
                        a.wait(map_info+"?.visible === true",20)
                        a.wait("window.mapFrames.some(m=>m.visible)",5)
                        info=a.js(map_info)
                        assert info['ready'] and info['assetsReady'] and info['assetsLoads']==1,info
                        assert info['islandVisible'] and not info['spaceshipVisible'],info
                        assert info['birchFound'] and not info['birchVisible'],info
                        assert info['buttonFrames']==19,info
                        if index==0: a.capture(scope+'/01-first-complete-map-without-birch')
                        if index<2:
                            bounds=a.js("window.player.ruffle().callExternalInterface('getProfileControlBounds','btnClose')")
                            a.stage_click(bounds['x']+bounds['width']/2,bounds['y']+bounds['height']/2)
                            a.wait(map_info+" === null")
                    a.js("window.mapRecording=false")
                    frames=a.js("window.mapFrames")
                    visible=[f for f in frames if f['visible']]
                    assert visible and all(f['ready'] and f['islandVisible'] and not f['spaceshipVisible'] and not f['birchVisible'] for f in visible),visible
                    requests=a.js("performance.getEntriesByType('resource').filter(r=>new URL(r.name).pathname==='/compat/WorldMapBumagLand.swf').length")
                    assert requests==1,requests
                    result['checks']['island_and_portal_present_in_every_visible_map_frame']=True
                    result['checks']['birch_hidden_from_first_frame_and_after_reopening']=True
                    result['checks']['one_asset_request_for_three_map_openings']=True
                    result['visible_map_frames_checked']=len(visible)
                    bounds=a.js("window.player.ruffle().callExternalInterface('getProfileControlBounds','mcBumagVale')")
                    a.stage_click(bounds['x']+bounds['width']/2,bounds['y']+bounds['height']/2)
                    a.wait("window.mogobeScene?.state==='world' && window.mogobeScene?.room==='bumagvale'",45)
                    result['checks']['original_portal_still_jumps_to_bumagland']=True
                    a.chat_send('/exit');a.wait("window.mogobeLogin?.view === 'saved'",40)
                elif args.map_ui:
                    popup = "window.player.ruffle().callExternalInterface('getSocialPopupInfo')"
                    map_info = "window.player.ruffle().callExternalInterface('getWorldMapInfo')"
                    def wait_room(name):
                        a.wait("window.mogobeScene?.state==='world' && window.mogobeScene?.room==="+json.dumps(name.lower()),45)
                        a.wait("window.player.ruffle().callExternalInterface('getWorldAvatar')?.visible === true",20)
                    def door(token,name):
                        bounds=a.js("window.player.ruffle().callExternalInterface('getLoginControlBounds',"+json.dumps('mcEntryPoint_'+token)+")")
                        assert bounds,(token,name)
                        x=max(8,min(760,bounds['x']+bounds['width']/2))
                        y=max(8,min(440,bounds['y']+bounds['height']/2))
                        a.stage_click(x,y)
                        wait_room(name)
                    a.chat_send('/room SummerCamp');wait_room('SummerCamp')
                    a.capture(scope+'/04-summer-camp')
                    door('17','Pool');a.capture(scope+'/05-pool')
                    result['checks']['visible_pool_entrance_17_from_summer_camp']=True
                    a.control('btnMap')
                    a.wait(map_info+"?.ready === true",20)
                    info=a.js(map_info)
                    assert info['islandVisible'] and not info['spaceshipVisible'],info
                    assert info['buttonFrames']==19,info
                    a.capture(scope+'/01-original-bumagland-map')
                    bounds=a.js("window.player.ruffle().callExternalInterface('getProfileControlBounds','mcBumagVale')")
                    x=bounds['x']+bounds['width']/2;y=bounds['y']+bounds['height']/2
                    assert 0<x<768 and 0<y<480,bounds
                    a.stage_click(x,y);wait_room('BumagVale')
                    result['checks']['original_russian_button_and_island_replace_spaceship_and_jump_to_bumagland']=True
                    # Reopening loads a fresh original button, without stale handlers.
                    a.control('btnMap');a.wait(map_info+"?.ready === true",20)
                    close=a.js("window.player.ruffle().callExternalInterface('getProfileControlBounds','btnClose')")
                    a.stage_click(close['x']+close['width']/2,close['y']+close['height']/2)
                    a.chat_send('/room Mall');wait_room('Mall')
                    door('11','ClothesStore');a.capture(scope+'/02-stilyagi')
                    door('10','Mall')
                    door('12','FurnitureStore');a.capture(scope+'/03-mogodom')
                    door('10','Mall')
                    result['checks']['stilyagi_and_mogodom_doors_lead_to_correct_interiors_and_return']=True
                    a.chat_send('/exit');a.wait("window.mogobeLogin?.view === 'saved'",40)
                elif args.rooms:
                    popup = "window.player.ruffle().callExternalInterface('getSocialPopupInfo')"
                    catalogue = json.loads((ROOT/'server/src/world/rooms.json').read_text(encoding='utf-8'))['rooms']
                    by_name = {r['swf']:r for r in catalogue}
                    visited = {'InfoBoard'}
                    def wait_room(name):
                        key = by_name[name]['key']
                        a.wait("window.mogobeScene?.state==='world' && window.mogobeScene?.room==="+json.dumps(key),45)
                        a.wait("window.player.ruffle().callExternalInterface('getWorldAvatar')?.visible === true",20)
                        state = a.js("fetch('/api/world/me').then(r=>r.json())")
                        assert state['room']==key,state
                        assert a.js("window.player.ruffle().callExternalInterface('getWorldAvatar').colorId") == 3
                        visited.add(name)
                    def map_jump(name):
                        a.control('btnMap')
                        a.wait(popup+"?.popupId === 3")
                        a.wait("window.player.ruffle().callExternalInterface('getWorldMapInfo')?.ready === true")
                        bounds = a.js("window.player.ruffle().callExternalInterface('getProfileControlBounds',"+json.dumps('mc'+name)+")")
                        assert bounds,name
                        x = bounds['x']+bounds['width']/2
                        y = bounds['y']+bounds['height']/2
                        assert 0 <= x <= 768 and 0 <= y <= 480, (name,bounds)
                        a.stage_click(x,y)
                        wait_room(name)
                    a.control('btnMap');a.wait(popup+"?.popupId === 3")
                    a.capture(f'{scope}/01-original-world-map')
                    close = a.js("window.player.ruffle().callExternalInterface('getProfileControlBounds','btnClose')")
                    a.stage_click(close['x']+close['width']/2,close['y']+close['height']/2)
                    for name in ['Novograd','Severburg','Sunandsea','SummerCamp','KingsRoad','Port','Skazkino','Vugovo','BumagVale','InfoBoard']:
                        map_jump(name)
                        expected = 2 if name=='InfoBoard' else 1
                        a.wait(AVATARS+f'.length === {expected}')
                        b.wait(AVATARS+f'.length === {expected}')
                        a.capture(f'{scope}/map-'+name)
                    result['checks']['all_ten_public_map_destinations_load_original_rooms'] = True
                    result['checks']['room_changes_remove_remote_avatars_and_rejoin_has_fresh_snapshot'] = True
                    # The authored edge clips are invisible hit zones; click
                    # their walking destination through the actual stage.
                    for token,destination in [('3','Novograd'),('6','InfoBoard')]:
                        bounds=a.js("window.player.ruffle().callExternalInterface('getLoginControlBounds',"+json.dumps('mcEntryPoint_'+token)+")")
                        assert bounds
                        x=max(8,min(760,bounds['x']+bounds['width']/2))
                        y=max(8,min(440,bounds['y']+bounds['height']/2))
                        a.stage_click(x,y);wait_room(destination)
                    result['checks']['walk_through_original_infoboard_novograd_exits_both_ways'] = True
                    for name in ['Mall','ClothesStore','BowlingRoom','MagicForest','Pool','ProfyRoom']:
                        a.chat_send('/room '+name);wait_room(name)
                    result['checks']['interiors_stores_and_additional_rooms_load_with_avatar'] = True
                    if args.rooms_all:
                        result['rooms'] = []
                        for room in catalogue:
                            name = room['swf']
                            if name not in visited:
                                a.chat_send('/room '+name);wait_room(name)
                            result['rooms'].append({'name':name,'loaded':True})
                        result['checks']['every_imported_walkable_room_loads_with_original_avatar'] = len(visited)==len(catalogue)
                    a.chat_send('/room InfoBoard');wait_room('InfoBoard')
                    a.wait(AVATARS+'.length === 2');b.wait(AVATARS+'.length === 2')
                    a.chat_send('RoomChatRestored')
                    b.wait(AVATARS+f".some(v=>v.id==={ids[0]} && v.speech.includes('RoomChatRestored'))")
                    result['checks']['chat_and_multiplayer_work_after_returning_to_same_room'] = True
                    a.chat_send('/exit');a.wait("window.mogobeLogin?.view === 'saved'",40)
                elif args.layout:
                    profile = "window.player.ruffle().callExternalInterface('getProfileInfo')"
                    popup = "window.player.ruffle().callExternalInterface('getSocialPopupInfo')"
                    panel = "window.player.ruffle().callExternalInterface('getWorldPanelInfo')"
                    def control(name):
                        bounds = a.js("window.player.ruffle().callExternalInterface('getProfileControlBounds',"+json.dumps(name)+")")
                        assert bounds,name
                        a.stage_click(bounds['x']+bounds['width']/2,bounds['y']+bounds['height']/2)
                    def observe(expression):
                        a.js("window.layoutFrames=[]; window.layoutRecording=true; window.layoutTick=()=>{if(!window.layoutRecording)return;window.layoutFrames.push("+expression+"); requestAnimationFrame(window.layoutTick)}; requestAnimationFrame(window.layoutTick)")
                    def finish():
                        a.js("window.layoutRecording=false")
                        return a.js("window.layoutFrames")
                    a.control('btnBuddy')
                    a.wait(popup+"?.rows.some(v=>v.userName==='Могоби_2' && v.serverName===null)")
                    observe(popup)
                    bounds = a.js("window.player.ruffle().callExternalInterface('getSocialRowControlBounds','Могоби_2','name')")
                    rect = a.js("document.getElementById('stage').getBoundingClientRect().toJSON()")
                    a.user32.SetForegroundWindow(a.hwnd)
                    a.call('Input.dispatchMouseEvent',type='mouseMoved',x=rect['x']+(bounds['x']+bounds['width']/2)*rect['width']/768,y=rect['y']+(bounds['y']+bounds['height']/2)*rect['height']/480)
                    time.sleep(1.2)
                    frames = finish()
                    rows = [row for frame in frames if frame for row in frame['rows']]
                    assert len(rows)>10,rows
                    assert all(row['userName'] in row['text'] and 'Ааааа' not in row['text'] and 'Aaaaa' not in row['text'] for row in rows),rows
                    a.capture('layout/01-first-offline-hover')
                    result['checks']['first_offline_hover_has_real_nickname_in_every_sampled_frame'] = True
                    control('btnClose')
                    observe(profile)
                    a.control('btnProfile')
                    a.wait(profile+"?.popupId === 7 && "+profile+"?.userName === 'Player_1'")
                    time.sleep(.6)
                    frames = [frame for frame in finish() if frame and frame['popupId']==7]
                    assert len(frames)>10,frames
                    assert all(not frame['luxuryVisible'] and not frame['luxuryIconVisible'] for frame in frames),[frame for frame in frames if frame['luxuryVisible'] or frame['luxuryIconVisible']]
                    assert any(frame['visible'] for frame in frames),"Profile never became visible"
                    counters = a.js(profile+'.counters')
                    expected = dict(zip(['txtNewMsgs','txtFriends','txtAge','txtAmount_1'],[182.125,218.125,254.125,290.125]))
                    assert len(counters)==4,counters
                    assert all(abs(v['center']-expected[v['name']])<.2 and v['align']=='center' for v in counters),counters
                    a.capture('layout/02-profile-centered-counters')
                    result['checks']['no_luxury_text_or_icon_in_first_profile_frames'] = True
                    result['checks']['four_counters_centered_under_original_icons'] = True
                    control('btnClose')
                    assert a.js(panel+".text === '' && "+panel+".defaultAlign === 'left' && "+panel+".danceVisible === false")
                    result['checks']['empty_chat_starts_left_and_blue_dance_button_hidden'] = True
                    for text in ['/','123','Привет могоби']:
                        a.control('txtSpeak');a.type_text(text)
                        a.wait(panel+'.text === '+json.dumps(text))
                        assert a.js(panel+".defaultAlign === 'left' && "+panel+".align === 'left'")
                    a.capture('layout/03-left-aligned-chat')
                    result['checks']['slash_digits_and_russian_chat_are_left_aligned'] = True
                    a.chat_send('/online')
                    a.wait(AVATARS+".some(v=>v.me && v.speech.includes('Сейчас в игре: 1'))")
                    a.chat_send('/exit');a.wait("window.mogobeLogin?.view === 'saved'",40)
                    result['checks']['chat_commands_still_work'] = True
                elif args.presence:
                    friend_room = json.dumps(a.js("fetch('/api/world/rooms').then(r=>r.json()).then(x=>x.rooms.find(r=>r.key==='infoboard').title)"))
                    popup = "window.player.ruffle().callExternalInterface('getSocialPopupInfo')"
                    server = "window.player.ruffle().callExternalInterface('getServerInfo')[0]"
                    def control(c,name):
                        bounds = c.js("window.player.ruffle().callExternalInterface('getProfileControlBounds',"+json.dumps(name)+")")
                        assert bounds,name
                        c.stage_click(bounds['x']+bounds['width']/2,bounds['y']+bounds['height']/2)
                    def wait_server(online,friends):
                        b.wait(server+f"?.online === {online} && "+server+f"?.friends === {friends} && "+server+"?.friendIcon === "+json.dumps('YES' if friends else 'NO'),20)
                        assert b.js(server+".text") == ""
                        assert b.js(server+".fill") == (1 if online else 0)
                    b.wait("window.mogobeLogin?.view === 'servers'")
                    wait_server(1,1)
                    b.capture('presence/01-friend-on-server')
                    result['checks']['original_friend_icon_and_population_meter_without_text'] = True
                    a.control('btnBuddy')
                    a.wait(popup+"?.popupId === 24 && "+popup+"?.rows.some(v=>v.userName==='Могоби_2' && v.serverName===null)")
                    a.capture('presence/02-friend-offline-in-server-picker')
                    result['checks']['server_picker_does_not_count_as_online'] = True
                    control(a,'btnClose')
                    a.chat_send('/exit');a.wait("window.mogobeLogin?.view === 'saved'",40)
                    wait_server(0,0)
                    b.capture('presence/03-server-empty-friend-icon-off')
                    result['checks']['server_population_and_friend_icon_update_without_reopening'] = True
                    a.control('txtMultiLoginPassword');a.type_text('Player123');a.control('btnLoginMultiInst')
                    enter(a)
                    wait_server(1,1)
                    result['checks']['friend_icon_returns_when_friend_rejoins'] = True
                    a.control('btnBuddy')
                    a.wait(popup+"?.popupId === 24 && "+popup+"?.rows.some(v=>v.userName==='Могоби_2' && v.serverName===null)")
                    enter(b)
                    a.wait(popup+"?.rows.some(v=>v.userName==='Могоби_2' && v.serverName==="+friend_room+" && v.text.includes("+friend_room+"))",20)
                    a.capture('presence/04-friend-goes-online')
                    result['checks']['open_friends_list_updates_when_friend_joins'] = True
                    b.chat_send('/online')
                    b.wait(AVATARS+".some(v=>v.me && v.speech.includes('Сейчас в игре: 2'))")
                    assert a.js(AVATARS+".every(v=>!v.speech.includes('Сейчас в игре'))")
                    b.capture('presence/06-private-online-command')
                    result['checks']['online_command_reports_two_players_only_to_sender'] = True
                    b.chat_send('/exit');b.wait("window.mogobeLogin?.view === 'saved'",40)
                    a.wait(popup+"?.rows.some(v=>v.userName==='Могоби_2' && v.serverName===null && !v.text.includes("+friend_room+"))",20)
                    a.capture('presence/05-friend-goes-offline')
                    result['checks']['open_friends_list_updates_when_friend_exits'] = True
                    control(a,'btnClose')
                    a.chat_send('/online')
                    a.wait(AVATARS+".some(v=>v.me && v.speech.includes('Сейчас в игре: 1'))")
                    result['checks']['online_command_updates_after_player_leaves'] = True
                    a.chat_send('/exit');a.wait("window.mogobeLogin?.view === 'saved'",40)
                elif args.social or args.friends_only:
                    profile = "window.player.ruffle().callExternalInterface('getProfileInfo')"
                    popup = "window.player.ruffle().callExternalInterface('getSocialPopupInfo')"
                    def control(c,name):
                        bounds = c.js("window.player.ruffle().callExternalInterface('getProfileControlBounds',"+json.dumps(name)+")")
                        assert bounds,name
                        c.stage_click(bounds['x']+bounds['width']/2,bounds['y']+bounds['height']/2)
                    def row_control(c,name,action):
                        bounds = c.js("window.player.ruffle().callExternalInterface('getSocialRowControlBounds',"+json.dumps(name)+","+json.dumps(action)+")")
                        assert bounds,(name,action)
                        c.stage_click(bounds['x']+bounds['width']/2,bounds['y']+bounds['height']/2)
                    tooltip = "window.player.ruffle().callExternalInterface('getFriendsTooltipInfo')"
                    def hover(c,bounds):
                        rect = c.js("document.getElementById('stage').getBoundingClientRect().toJSON()")
                        c.user32.SetForegroundWindow(c.hwnd)
                        time.sleep(.05)
                        c.call('Input.dispatchMouseEvent',type='mouseMoved',x=rect['x']+(bounds['x']+bounds['width']/2)*rect['width']/768,y=rect['y']+(bounds['y']+bounds['height']/2)*rect['height']/480)
                    def away(c):
                        hover(c,{'x':20,'y':20,'width':0,'height':0})
                        c.wait(tooltip+"?.visible === false",5)
                    def hover_row(c,name):
                        bounds = c.js("window.player.ruffle().callExternalInterface('getSocialRowControlBounds',"+json.dumps(name)+",'name')")
                        assert bounds
                        hover(c,bounds)
                        c.wait(tooltip+"?.visible === true",5)
                        assert c.js(popup+".rows.every(v=>!/[AaАа]{5}/.test(v.text))")
                        assert c.js(popup+".rows.some(v=>v.userName==="+json.dumps(name)+" && v.text.includes("+json.dumps(name)+"))")
                        away(c)
                        time.sleep(.25)
                        assert c.js(tooltip+".visible === false")
                    def reconnect(c):
                        before = c.js("fetch('/client/accounts').then(r=>r.json())")
                        c.js("window.beforeF5 = true")
                        c.user32.SetForegroundWindow(c.hwnd)
                        c.user32.keybd_event(0x74,0,0,0)
                        c.user32.keybd_event(0x74,0,2,0)
                        time.sleep(1)
                        c.wait("window.beforeF5 === undefined && window.mogobeScene?.state === 'world' && window.mogobeScene?.user?.username === 'Player_1'",60)
                        c.wait(AVATARS+".length === 2")
                        assert c.js("fetch('/client/accounts').then(r=>r.json())") == before
                        assert c.js(popup+" === null && "+tooltip+".visible === false")
                        assert not c.js("window.mogobePopup?.state === 'open'")
                    def card_of_b():
                        other = a.js(AVATARS+f".find(v=>v.id==={ids[1]})")
                        a.stage_click(other['x'],other['y']-30)
                        a.wait(profile+"?.popupId === 8 && "+profile+"?.userName === 'Могоби_2'")
                    b.stage_click(440,392)
                    a.wait(AVATARS+f".some(v=>v.id==={ids[1]} && v.x>420 && v.action===0)")
                    if not args.friends_only:
                        a.control('btnEmoticons');a.control('Ico_wink')
                        b.wait(AVATARS+f".some(v=>v.id==={ids[0]} && v.balloonChildren.includes('mlIco_wink'))",10)
                        for emotion in ['Ico_mad','Ico_sad','Ico_stupid','Ico_laughing']:
                            time.sleep(.6)
                            a.control('btnEmoticons');a.control(emotion)
                            b.wait(AVATARS+f".some(v=>v.id==={ids[0]} && v.balloonChildren.includes('ml{emotion}'))",10)
                        result['checks']['all_five_original_emotions_visible_to_other_player'] = True
                        b.capture(f'{scope}/01-emotion')
                        time.sleep(.6)
                        a.control('btnEEffects');a.control('Ico_rain')
                        other = a.js(AVATARS+f".find(v=>v.id==={ids[1]})")
                        a.stage_click(other['x'],other['y']-30)
                        b.wait(AVATARS+f".some(v=>v.id==={ids[1]} && v.balloonLabel==='Ico_rain')",10)
                        for magic in ['Ico_bubbles','Ico_hearts','Ico_heart','Ico_snow','Ico_Snowball','Ico_Flowers']:
                            time.sleep(.6)
                            a.control('btnEEffects');a.control(magic)
                            a.stage_click(other['x'],other['y']-30)
                            b.wait(AVATARS+f".some(v=>v.id==={ids[1]} && v.balloonLabel==='{magic}')",10)
                        result['checks']['all_seven_visible_original_magic_effects_on_other_player'] = True
                        b.capture(f'{scope}/02-magic')
                    if args.friends_ui:
                        time.sleep(1.5)
                        before = [c.js("window.socialFetches") for c in [a,b]]
                        time.sleep(3)
                        assert [c.js("window.socialFetches") for c in [a,b]] == before
                        result['checks']['no_social_http_polling_while_idle'] = True
                        menu = "window.player.ruffle().callExternalInterface('getChatMenuItems')"
                        for path,phrase in [(['Приветствия','Привет!'],'Привет!'),(['Приветствия','Время суток','Добрый вечер!'],'Добрый вечер!'),(['Прощания','Пока-пока!'],'Пока-пока!')]:
                            a.control('btnCloseChat')
                            for text in path:
                                a.wait(menu+".some(v=>v.text==="+json.dumps(text)+")")
                                bounds = a.js(menu+".find(v=>v.text==="+json.dumps(text)+")")
                                if text != path[-1]: hover(a,bounds)
                                else: a.stage_click(bounds['x']+bounds['width']/2,bounds['y']+bounds['height']/2)
                            for c in [a,b]: c.wait(AVATARS+f".some(v=>v.id==={ids[0]} && v.speech.includes("+json.dumps(phrase)+"))")
                        b.capture(f'{scope}/08-original-ready-phrase')
                        result['checks']['original_ready_phrases_and_nested_menu_reach_both_players'] = True
                        offers_before = b.js("window.socialFetches")
                    card_of_b();control(a,'btnAddFriend');control(a,'btnClose')
                    b.control('btnBuddy')
                    b.wait(popup+"?.popupId === 24")
                    control(b,'btnRequestTab')
                    b.wait(popup+"?.rows.some(v=>v.userName==='Player_1' && v.status===1)")
                    b.capture(f'{scope}/03-friend-request')
                    if args.friends_ui:
                        b.wait("window.socialFetches > "+str(offers_before))
                        result['checks']['incoming_friend_event_refreshes_social_state_without_polling'] = True
                        hover_row(b,'Player_1')
                        for button,text in [('btnBuddyTab','Друзья'),('btnIgnorTab','Чёрный список'),('btnRequestTab','Мы хотим с тобой дружить!')]:
                            bounds = b.js("window.player.ruffle().callExternalInterface('getProfileControlBounds',"+json.dumps(button)+")")
                            hover(b,bounds)
                            b.wait(tooltip+"?.visible === true",5)
                            assert b.js(tooltip+".text") == text
                            away(b)
                        result['checks']['request_nick_and_all_tab_tooltips_clear_on_mouse_leave'] = True
                    row_control(b,'Player_1','primary')
                    b.wait(popup+"?.popupId === 15")
                    control(b,'mcOK')
                    b.wait(popup+"?.popupId === 24")
                    control(b,'btnBuddyTab')
                    b.wait(popup+"?.rows.some(v=>v.userName==='Player_1' && v.status===2)")
                    result['checks']['request_and_accept_in_original_friends_list'] = True
                    control(b,'btnClose')
                    a.control('btnProfile')
                    a.wait(profile+"?.popupId === 7 && "+profile+"?.friends === '1' && "+profile+"?.luxuryVisible === false")
                    a.capture(f'{scope}/04-profile-without-luxury')
                    result['checks']['friend_counter_and_luxury_currency_removed'] = True
                    control(a,'btnClose')
                    card_of_b()
                    if args.friends_ui:
                        # Hold only this mutation; normal state polling continues
                        # and must not overwrite the local button state.
                        a.js("window.savedFetch = window.fetch; window.fetch = (url,options)=>url === '/api/social/mute' ? new Promise((resolve,reject)=>{window.releaseMute=()=>window.savedFetch(url,options).then(resolve,reject)}) : window.savedFetch(url,options)")
                        control(a,'btnBend')
                        assert a.js(profile+".muted === true && "+profile+".mutePending === true && "+profile+".muteFrame === 'CHEKED'")
                        time.sleep(1.2)
                        assert a.js(profile+".muted === true && "+profile+".mutePending === true")
                        control(a,'btnBend')
                        assert a.js(profile+".muted === false && "+profile+".mutePending === true && "+profile+".muteFrame === 'UNCHECKED'")
                        a.js("window.fetch=window.savedFetch;window.releaseMute()")
                        a.wait(profile+"?.muted === false && "+profile+"?.mutePending === false")
                        result['checks']['mute_changes_immediately_and_rapid_clicks_preserve_last_choice'] = True
                    control(a,'btnBend')
                    a.wait(profile+"?.muted === true && "+profile+"?.mutePending === false")
                    if args.friends_ui:
                        a.js("window.fetch=(url,options)=>url === '/api/social/mute' ? Promise.resolve(new Response('{}',{status:503,headers:{'Content-Type':'application/json'}})) : window.savedFetch(url,options)")
                        control(a,'btnBend')
                        a.wait(profile+"?.muted === true && "+profile+"?.mutePending === false")
                        a.popup_confirm()
                        a.js("window.fetch=window.savedFetch")
                        result['checks']['rejected_mute_change_rolls_back_and_shows_original_popup'] = True
                    a.capture(f'{scope}/05-muted-profile')
                    control(a,'btnClose')
                    b.chat_send('MutedMessage')
                    b.wait(AVATARS+f".some(v=>v.me && v.speech.includes('MutedMessage'))")
                    assert a.js(AVATARS+".every(v=>!v.speech.includes('MutedMessage'))")
                    result['checks']['profile_mute_hides_only_selected_players_messages'] = True
                    a.control('btnBuddy');a.wait(popup+"?.popupId === 24")
                    control(a,'btnIgnorTab')
                    a.wait(popup+"?.rows.some(v=>v.userName==='Могоби_2' && v.status===3)")
                    a.capture(f'{scope}/06-ignore-list')
                    row_control(a,'Могоби_2','secondary')
                    a.wait(popup+"?.popupId === 15");control(a,'mcOK')
                    a.wait(popup+"?.popupId === 24 && "+popup+"?.rows.length === 0")
                    result['checks']['ignore_tab_unmutes_player'] = True
                    control(a,'btnClose')
                    b.chat_send('VisibleAgain')
                    a.wait(AVATARS+f".some(v=>v.id==={ids[1]} && v.speech.includes('VisibleAgain'))")
                    result['checks']['unmute_restores_chat'] = True
                    card_of_b()
                    a.wait(profile+"?.muted === false && "+profile+"?.friends === '1'")
                    control(a,'btnClose')
                    a.control('btnBuddy');a.wait(popup+"?.popupId === 24")
                    control(a,'btnBuddyTab')
                    a.wait(popup+"?.rows.some(v=>v.userName==='Могоби_2' && v.status===2 && v.text.includes('Могоби_2'))")
                    if args.friends_ui:
                        hover_row(a,'Могоби_2')
                        result['checks']['cyrillic_friend_name_survives_hover_frames'] = True
                        reconnect(a)
                        card_of_b()
                        reconnect(a)
                        b.wait(AVATARS+".length === 2")
                        result['checks']['F5_from_friends_and_profile_rejoins_world_with_same_login'] = True
                        a.control('btnBuddy');a.wait(popup+"?.popupId === 24 && "+popup+"?.rows.some(v=>v.userName==='Могоби_2')")
                    row_control(a,'Могоби_2','primary')
                    a.wait(popup+"?.popupId === 15");control(a,'mcOK')
                    a.wait(popup+"?.popupId === 24 && "+popup+"?.rows.some(v=>v.status===4)")
                    a.capture(f'{scope}/07-best-friends')
                    result['checks']['best_friend_and_cyrillic_name_in_original_list'] = True
                    row_control(a,'Могоби_2','secondary')
                    a.wait(popup+"?.popupId === 15");control(a,'mcOK')
                    a.wait(popup+"?.popupId === 24 && "+popup+"?.rows.length === 0")
                    control(a,'btnClose')
                    a.control('btnProfile');a.wait(profile+"?.popupId === 7 && "+profile+"?.friends === '0'")
                    result['checks']['unfriend_updates_profile_counter'] = True
                    control(a,'btnClose')
                    a.chat_send('/exit');a.wait("window.mogobeLogin?.view === 'saved'",40)
                elif args.profiles:
                    # Store an accepted pair after both clients logged in. Card
                    # opening must refresh their initially zero friend counters.
                    with sqlite3.connect(directory/"world.sqlite3") as db:
                        db.execute("INSERT INTO social_friendship(first_id,second_id) VALUES (?,?)",tuple(sorted(ids)))
                    info = "window.player.ruffle().callExternalInterface('getProfileInfo')"
                    def profile_control(c,name):
                        bounds = c.js("window.player.ruffle().callExternalInterface('getProfileControlBounds',"+json.dumps(name)+")")
                        assert bounds,name
                        c.stage_click(bounds['x']+bounds['width']/2,bounds['y']+bounds['height']/2)
                    a.control("btnProfile")
                    a.wait(info+"?.popupId === 7",30)
                    a.wait(info+"?.userName === 'Player_1' && "+info+"?.days === '5' && "+info+"?.friends === '1'",30)
                    result['checks']['original_own_profile_name_days_and_real_friend_count'] = True
                    a.capture('profiles/01-my-card')
                    for button,label in [('btnBeads','lblBeads'),('btnTrophy','lblTrophy'),('btnPetsItems','lblPetItems'),('btnVehicles','lblVehicle'),('btnClothing','lblCloth')]:
                        profile_control(a,button)
                        a.wait(info+"?.inventory === "+json.dumps(label),10)
                    result['checks']['own_profile_inventory_tabs_with_empty_inventory'] = True
                    profile_control(a,'btnClose')
                    a.wait(info+" === null")
                    b.stage_click(440,392)
                    a.wait(AVATARS+f".some(v=>v.id==={ids[1]} && v.x>420 && v.action===0)")
                    other = a.js(AVATARS+f".find(v=>v.id==={ids[1]})")
                    a.stage_click(other['x'],other['y']-30)
                    a.wait(info+"?.popupId === 8",30)
                    a.wait(info+"?.userName === 'Player_2' && "+info+"?.days === '17' && "+info+"?.friends === '1'",30)
                    result['checks']['original_other_profile_name_days_and_real_friend_count'] = True
                    a.capture('profiles/02-other-card')
                    profile_control(a,'btnClose')
                    a.wait(info+" === null")
                    a.control('btnProfile')
                    a.wait(info+"?.popupId === 7 && "+info+"?.userName === 'Player_1'",30)
                    profile_control(a,'btnClose')
                    a.wait(info+" === null")
                    a.chat_send('/exit')
                    a.wait("window.mogobeLogin?.view === 'saved'",40)
                    result['checks']['cards_close_reopen_and_return_to_picker'] = True
                else:
                    result["checks"]["both_original_clients_see_both_mogobes"] = True
                    profiles = list((directory/"profiles/Mogobe").glob("accounts-*.dat"))
                    assert len(profiles) == 2
                    result["checks"]["concurrent_windows_use_separate_persistent_profiles"] = True
                    a.capture("multiplayer/01-two-players")
                    a.stage_click(400,392)
                    b.wait(AVATARS+f".some(v=>v.id==={ids[0]} && v.action===1)",10)
                    b.wait(AVATARS+f".some(v=>v.id==={ids[0]} && v.x>350)")
                    result["checks"]["remote_avatar_walks_and_moves"] = True
                    a.chat_send("Привет могоби")
                    b.wait(AVATARS+f".some(v=>v.id==={ids[0]} && v.speech.includes('Привет могоби'))",10)
                    b.capture("multiplayer/02-chat")
                    result["checks"]["original_chat_bubble_visible_to_other_player"] = True
                    b.chat_send("/exit")
                    b.wait("window.mogobeLogin?.view === 'saved'",40)
                    a.wait(AVATARS+".length === 1")
                    result["checks"]["exit_removes_remote_mogobe"] = True
                    b.control("btnOtherUserI")
                    b.wait("window.mogobeLogin?.view === 'single'")
                    login(b,"Player_1")
                    b.wait("document.getElementById('notice').textContent.includes('уже')")
                    b.wait("window.player.ruffle().callExternalInterface('getLoginControlBounds','btnConfirm') !== null")
                    assert a.js("window.mogobeScene?.state === 'world'")
                    a.stage_click(500,392)
                    a.wait(AVATARS+".some(v=>v.me && v.x>450)")
                    result["checks"]["duplicate_login_rejected_first_player_stays_online"] = True
                    b.capture("multiplayer/03-duplicate-login")
                    b.control("btnConfirm")
                    login(b,second_name);enter(b)
                    a.wait(AVATARS+".length === 2")
                    b.wait(AVATARS+".length === 2")
                    result["checks"]["second_account_can_rejoin_after_denial"] = True
                    subprocess.run(["taskkill","/PID",str(second.pid),"/T","/F"],capture_output=True)
                    second.wait(timeout=5)
                    a.wait(AVATARS+".length === 1",30)
                    result["checks"]["window_close_removes_remote_mogobe"] = True
            except Exception:
                result["error"] = traceback.format_exc()
                for index,c in enumerate(clients):
                    try:
                        result[f"client_{index}"] = c.js("JSON.stringify({scene:window.mogobeScene,login:window.mogobeLogin,notice:document.getElementById('notice')?.textContent,servers:window.player?.ruffle().callExternalInterface('getServerInfo'),map:window.player?.ruffle().callExternalInterface('getWorldMapInfo'),profile:window.player?.ruffle().callExternalInterface('getProfileInfo'),popup:window.player?.ruffle().callExternalInterface('getSocialPopupInfo'),avatars:window.player?.ruffle().callExternalInterface('getWorldAvatars')})")
                        c.capture(f"{scope}/failure-{index}")
                    except Exception:
                        pass
            finally:
                for process in reversed(processes):
                    subprocess.run(["taskkill","/PID",str(process.pid),"/T","/F"],capture_output=True)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
    result["elapsed_seconds"] = round(time.monotonic()-started,1)
    result["passed"] = not result.get("error") and all(result["checks"].values())
    (OUT/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=True,indent=2),flush=True)
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
