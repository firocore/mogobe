let profileFetchSequence=0;
async function refreshOriginalProfile(){
  const info=window.player?.ruffle().callExternalInterface('getProfileInfo');
  if(!info || (!(info.userId>0) && !info.userName))return;
  const sequence=++profileFetchSequence;
  try{
    const target=info.userId>0?String(info.userId):'by-name/'+encodeURIComponent(info.userName);
    const response=await fetch('/api/social/profiles/'+target,{cache:'no-store'});
    if(!response.ok)return;
    const data=await response.json();
    if(sequence===profileFetchSequence)window.player?.ruffle().callExternalInterface('setProfileProgress',data);
  }catch{}
}
window.onMogobeAvatarPhoto = async jpeg => {
  try {
    const response = await fetch('/client/clipboard/avatar', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jpeg})});
    if(!response.ok) throw new Error('Не удалось скопировать изображение в буфер обмена.');
    window.mogobeLastPhoto = {copied:true,...await response.json()};
  } catch(error) { window.mogobeLastPhoto = {copied:false};showMogobePopup(error.message); }
};
window.onMogobeProfileShown=()=>{setTimeout(()=>refreshOriginalProfile(),0);};
let shopPointsRoom='',shopPointsSequence=0;
async function refreshWorldShopPoints(){
 const room=window.mogobeScene?.room;
 if(window.mogobeScene?.state!=='world'||!room)return;
 const sequence=++shopPointsSequence;
 try{const response=await fetch('/api/shop-points?room='+encodeURIComponent(room));if(!response.ok)return;const data=await response.json();if(sequence===shopPointsSequence&&room===window.mogobeScene.room){shopPointsRoom=room;window.player?.ruffle().callExternalInterface('setWorldShopPoints',data);}}catch{}
}
window.onMogobeWorldShop=point=>openMogobeShop('',false,point);
let activeShopKey = '', shopOpenSeen = 0, shopRevisionSeen = 0, shopFetchSequence = 0;
let minigameOpenSeen = 0;
window.onMogobeShopClosed = () => { activeShopKey='';shopFetchSequence++; };
async function openMogobeShop(key, refresh=false, point="") {
  const sequence=++shopFetchSequence;
  try {
    const response=await fetch(point?'/api/shop-points/'+encodeURIComponent(point)+'/open':'/api/shops/'+encodeURIComponent(key),{method:point?'POST':'GET',cache:'no-store'});
    const data=await response.json();
    if(!response.ok) throw Error(typeof data.detail==='string'?data.detail:'Магазин недоступен.');
    if(sequence!==shopFetchSequence || leavingWorld) return;
    if(point)data.sourcePoint=point;
    if(refresh) window.player?.ruffle().callExternalInterface('refreshOriginalShop',data);
    else {
      const opened=window.player?.ruffle().callExternalInterface('openOriginalShop',data);
      if(!opened) throw Error('Закройте открытое окно и повторите команду магазина.');
      activeShopKey=data.key;
    }
  } catch(error) {
    if(refresh) window.player?.ruffle().callExternalInterface('closeOriginalShop');
    showMogobePopup(error.message);
  }
}
window.onMogobeShopBuy = async (key,itemId,price) => {
  try {
    const response=await fetch('/api/shops/'+encodeURIComponent(key)+'/buy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({item_id:itemId,expected_price:price})});
    const data=await response.json();
    if(!response.ok) throw Error(typeof data.detail==='string'?data.detail:'Покупка не выполнена.');
    window.player?.ruffle().callExternalInterface('finishShopPurchase',true);
  } catch(error) {
    window.player?.ruffle().callExternalInterface('finishShopPurchase',false);
    showMogobePopup(error.message);
    await openMogobeShop(key,true);
  }
};

window.openRegistWindow = () => location.assign('/Registration2.aspx');
window.setLangAndReload = () => location.reload();
for (const name of ['onPageView', 'onGemiusPageView', 'onSetVar', 'logData', 'onOpenWebWindow']) window[name] = () => {};
window.beMember = () => alert('Этот раздел пока недоступен.');
window.mogobeScene = {state:'loading'};
window.mogobeConnection = 'connecting';
window.originalConnectionLoaderReady = false;
window.mogobeLogin = {view:'loading',visible:[],selected:''};
let rememberedMogobes = [];
let registrationMogobe = '';
window.getRegistrationMogobe = () => registrationMogobe;
let loginAttempt = '';
let reconnectRequested = new URLSearchParams(location.search).get('reconnect') === '1';
let socialRevision = 0;
const muteChains = new Map();
window.getRememberedMogobes = () => rememberedMogobes;
let serversWatchVersion = 0;
window.onMogobeLoginView = (view,visible,selected) => {
  window.mogobeLogin = {view,visible,selected};
  const version = ++serversWatchVersion;
  if(view === 'servers') {
    watchServerPresence(version);
    if(reconnectRequested) enterReconnectedWorld(version);
  }
};
async function enterReconnectedWorld(version) {
  // Select through the original server button and controller after the
  // current session has resumed; never bypass the server's admission check.
  for(let attempt=0; attempt<30 && version === serversWatchVersion; attempt++) {
    if(window.player?.ruffle().callExternalInterface('chooseOriginalServer')) {
      reconnectRequested = false;
      return;
    }
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  reconnectRequested = false;
}

async function watchServerPresence(version) {
  while(version === serversWatchVersion && window.mogobeLogin.view === 'servers') {
    try {
      const response = await fetch('/api/world/servers',{cache:'no-store'});
      if(response.ok && version === serversWatchVersion && window.mogobeLogin.view === 'servers') {
        const data = await response.json();
        window.player?.ruffle().callExternalInterface('setServerPresence',data.servers);
      }
    } catch { /* Keep the original selection screen while a refresh is unavailable. */ }
    await new Promise(resolve=>setTimeout(resolve,1000));
  }
}
window.onMogobeLoginPreferences = (username,rememberName,rememberSession) => {
  loginAttempt = `${Date.now()}-${Math.random()}`;
  if(reconnectRequested) {
    const saved = rememberedMogobes.find(account=>account.username.toLowerCase() === username.toLowerCase());
    rememberName = Boolean(saved);
    rememberSession = Boolean(saved?.has_session);
  }
  const preferences = {username,remember_name:rememberName,remember_session:rememberSession,attempt:loginAttempt};
  document.cookie = `mogobe_login_preferences=${encodeURIComponent(JSON.stringify(preferences))}; Path=/; SameSite=Strict`;
};
window.onMogobeRememberedAccounts = async names => {
  try {
    const response = await fetch('/client/accounts/sync',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({names})});
    if(!response.ok) throw new Error('Не удалось сохранить список могоби.');
    rememberedMogobes = await response.json();
  } catch(error) { showNotice(error.message); }
};
window.onMogobeSceneState = (state,room,panelReady,avatarReady) => {
  window.mogobeScene = {...window.mogobeScene,state,room,panelReady,avatarReady};
  document.getElementById('loading').hidden = state !== 'loading';
  if(state==='world'&&room!==shopPointsRoom)refreshWorldShopPoints();
  if(state === 'lobby') {
    const error = sessionStorage.getItem('mogobe.worldError');
    if(error) { sessionStorage.removeItem('mogobe.worldError'); setTimeout(()=>showMogobePopup(error),0); }
  }
};
const showNotice = message => {
  const note = document.getElementById('notice');
  note.textContent = message; note.hidden = false;
};
let signedIn = false;
let seenSocialVersion = -1;
let socialRetryAt = 0;
let socialRetryDelay = 1000;
async function watchLogin(attempt) {
  const deadline = Date.now()+20000;
  while(Date.now()<deadline && attempt === loginAttempt) {
    try {
      const response = await fetch('/client/login-result',{cache:'no-store'});
      const result = await response.json();
      if(result.attempt === attempt) {
        window.player?.ruffle().callExternalInterface('finishRegistrationLogin',result.status === '1');
        rememberedMogobes = await (await fetch('/client/accounts',{cache:'no-store'})).json();
        setTimeout(()=>window.player?.ruffle().callExternalInterface('refreshRememberedState',rememberedMogobes),100);
        if(result.status !== '1') reconnectRequested = false;
        if(result.message) showNotice(result.message);
        else document.getElementById('notice').hidden = true;
        return;
      }
    } catch { /* A pending local request is retried until the transport timeout. */ }
    await new Promise(resolve=>setTimeout(resolve,150));
  }
}
window.onTrackEvent = async (category,action) => {
  if(category === 'Login' && action === 'TryToLogin') { watchLogin(loginAttempt); return; }
  if(category !== 'Login' || action !== 'SelectServer' || signedIn) return;
  // The AS3 adapter sanitizes the login before the original server handler runs.
  window.onMogobeSceneState('loading','',false,false);
  signedIn = true;
  watchWorld();
  try {
    const response = await fetch('/api/auth/me', {cache:'no-store'});
    if(!response.ok) throw new Error('Сессия завершилась. Войдите снова.');
    const user = await response.json();
    window.mogobeScene = {...window.mogobeScene, user};
  } catch(error) { signedIn = false; showNotice(error.message); }
};
const pendingWorldAlerts=[];
let lastChatID=0;
async function watchWorld() {
  while(signedIn && !leavingWorld) {
    try {
      const status = await (await fetch('/client/world/status?chat_after='+lastChatID,{cache:'no-store'})).json();
      if(status.error) {
        leavingWorld = true;
        sessionStorage.setItem('mogobe.worldError',status.error);
        await fetch('/client/world/leave',{method:'POST'});
        window.player?.remove();
        location.assign('/');
        return;
      }
      if(status.chat?.length) {
        window.player.ruffle().callExternalInterface('addChatHistory',status.chat);
        lastChatID=status.chat.at(-1).id;
      }
      pendingWorldAlerts.push(...(status.notices??[]));
      if(['world','minigame'].includes(window.mogobeScene?.state)) {
        if(pendingWorldAlerts.length && (!window.mogobePopup || window.mogobePopup.state==='closed')) {
          const notice=pendingWorldAlerts.shift();
          showMogobePopup('Объявление от '+notice.sender+'\n'+notice.text);
        }
        if((status.minigame_serial??0)!==minigameOpenSeen && window.mogobeScene?.state==='world') {
          minigameOpenSeen=status.minigame_serial??0;
          if(status.minigame_key) await window.openMogobeMinigame(status.minigame_key);
        }
        if((status.shop_serial??0)!==shopOpenSeen) {
          shopOpenSeen=status.shop_serial??0;
          if(status.shop_key) await openMogobeShop(status.shop_key);
        }
        if((status.shop_revision??0)!==shopRevisionSeen) {
          shopRevisionSeen=status.shop_revision??0;
          if(activeShopKey) await openMogobeShop(activeShopKey,true);
          await refreshOriginalProfile();
          await refreshWorldShopPoints();
        }
      }
      const version = status.social_revision ?? 0;
      if(window.mogobeScene?.state === 'world' && version !== seenSocialVersion && Date.now() >= socialRetryAt) {
        const revision = socialRevision;
        const controller = new AbortController();
        const timeout = setTimeout(()=>controller.abort(),5000);
        try {
          const response = await fetch('/api/social/me',{cache:'no-store',signal:controller.signal});
          if(!response.ok) throw new Error('Social state unavailable');
          const state = await response.json();
          if(revision === socialRevision && signedIn && !leavingWorld) {
            window.player?.ruffle().callExternalInterface('setSocialState',state);
            seenSocialVersion = version;
            socialRetryAt = 0;
            socialRetryDelay = 1000;
          }
        } catch {
          socialRetryAt = Date.now()+socialRetryDelay;
          socialRetryDelay = Math.min(socialRetryDelay*2,30000);
        } finally { clearTimeout(timeout); }
      }
    } catch { /* Retry the local bridge until navigation or a reported error. */ }
    await new Promise(resolve=>setTimeout(resolve,500));
  }
}
let leavingWorld = false;
window.onMogobeMuteChanged = (username, muted, sequence) => {
  socialRevision++;
  const preceding = muteChains.get(username) || Promise.resolve();
  const operation = preceding.catch(()=>{}).then(async()=>{
    const controller = new AbortController();
    const timeout = setTimeout(()=>controller.abort(),5000);
    try {
      const response = await fetch('/api/social/mute',{method:'POST',signal:controller.signal,
        headers:{'Content-Type':'application/json'},body:JSON.stringify({username,muted})});
      if(!response.ok) throw new Error('Не удалось изменить игнор. Состояние кнопки восстановлено.');
      const result = await response.json();
      if(result.username !== username || result.muted !== muted) throw new Error('Сервер не подтвердил изменение игнора.');
      socialRevision++;
      window.player?.ruffle().callExternalInterface('finishMuteChange',username,sequence,true,result.muted);
    } catch(error) {
      socialRevision++;
      window.player?.ruffle().callExternalInterface('finishMuteChange',username,sequence,false,false);
      showMogobePopup(error.name === 'AbortError' ? 'Сервер не ответил. Состояние кнопки игнора восстановлено.' : error.message);
    } finally { clearTimeout(timeout); }
  });
  muteChains.set(username,operation);
  operation.finally(()=>{if(muteChains.get(username) === operation) muteChains.delete(username);});
};

window.onMogobeReconnect = () => {
  if(!['world','minigame'].includes(window.mogobeScene?.state) || leavingWorld) return;
  leavingWorld = true;
  window.player?.ruffle().callExternalInterface('showOriginalLoading',true);
  setTimeout(async()=>{
    try {
      await Promise.allSettled([...muteChains.values()]);
      const prepared = await fetch('/api/world/reconnect',{method:'POST'});
      if(!prepared.ok) throw new Error('Не удалось подготовить переподключение в текущую локацию.');
      const response = await fetch('/client/world/leave?reconnect=1',{method:'POST'});
      if(!response.ok) throw new Error('Не удалось закрыть прежнее игровое соединение.');
      const deadline = Date.now()+10000;
      while(Date.now()<deadline) {
        const state = await fetch('/api/world/me',{cache:'no-store'});
        if(!state.ok) throw new Error('Сессия завершилась. Войдите снова.');
        if(!(await state.json()).entered) {
          window.player?.remove();
          location.replace('/?reconnect=1');
          return;
        }
        await new Promise(resolve=>setTimeout(resolve,100));
      }
      throw new Error('Сервер ещё завершает прежнее подключение. Попробуйте войти снова.');
    } catch(error) {
      sessionStorage.setItem('mogobe.worldError',error.message);
      window.player?.remove();
      location.replace('/');
    }
  },0);
};
document.addEventListener('keydown',event=>{
  if(event.key !== 'F5' || !['world','minigame'].includes(window.mogobeScene?.state)) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  window.onMogobeReconnect();
},true);

window.onMogobePublicChat = text => {
  setTimeout(async()=>{
    try {
      const response=await fetch('/api/world/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});
      if(!response.ok) throw new Error('Не удалось отправить сообщение.');
    } catch(error) { showMogobePopup(error.message); }
  },0);
};

window.onMogobeChatCommand = command => {
  if(command === 'help') {
    setTimeout(async()=>{
      try {
        const response=await fetch('/api/world/commands',{cache:'no-store'});
        if(!response.ok) throw new Error('Не удалось получить список команд.');
        const data=await response.json();
        window.mogobeCommandHelp=data;
        const lines=['Доступные команды'];
        for(const row of [...data.commands,...data.shortcuts]) lines.push(row.syntax+' — '+row.description);
        lines.push('',...data.notes);
        await showMogobePopup(lines.join('\n'),{kind:'commands'});
      } catch(error) { showMogobePopup(error.message); }
    },0);
    return;
  }
  if(command !== 'exit' || leavingWorld) return;
  leavingWorld = true;
  // Leave the current Ruffle callback before unloading its player.
  setTimeout(async () => {
    try {
      const response = await fetch('/client/world/leave', {method:'POST'});
      if(!response.ok) throw new Error('Не удалось вернуться к выбору могоби. Повторите /exit.');
      window.player?.remove();
      location.assign('/');
    } catch(error) { leavingWorld = false; showNotice(error.message); }
  }, 0);
};
async function waitForServer() {
  while(true) {
    const controller = new AbortController();
    const timeout = setTimeout(()=>controller.abort(),5000);
    try {
      const response = await fetch('/api/health',{cache:'no-store',signal:controller.signal});
      const health = response.ok ? await response.json() : null;
      if(health?.ok === true) {
        document.getElementById('notice').hidden = true;
        window.mogobeConnection = 'connected';
        return;
      }
    } catch { /* Keep playing the original loading animation while reconnecting. */ }
    finally { clearTimeout(timeout); }
    showNotice('Ожидаем подключения к серверу. Проверьте client.json. Повторяем подключение…');
    await new Promise(resolve=>setTimeout(resolve,2000));
  }
}
(async () => {
  try {
    const player = RufflePlayer.newest().createPlayer();
    window.player = player;
    document.getElementById('movie').appendChild(player);
    await player.ruffle().load({url:'/compat/OriginalPreloader.swf',base:location.origin+'/'});
    // The browser keeps the fullscreen element at viewport size. Frame the
    // actual render container inside it, preserving Ruffle's fullscreen API
    // and the original 8:5 game area. The runtime's files remain unchanged.
    if(player.shadowRoot) {
      const style = document.createElement('style');
      style.textContent = `:host(:fullscreen) #container {
        box-sizing:content-box;inset:0;margin:auto;
        width:var(--mogobe-stage-width);height:var(--mogobe-stage-height);
        border:10px solid #fff;box-shadow:10px 10px 0 #5c7d08;overflow:hidden;
      }`;
      player.shadowRoot.appendChild(style);
    }
    window.mogobeScene = {state:'connecting'};
    window.originalConnectionLoaderReady = true;
    await waitForServer();
    const saved = await fetch('/client/accounts/refresh',{method:'POST',cache:'no-store'});
    if(!saved.ok) throw new Error('Не удалось загрузить сохранённых могоби.');
    rememberedMogobes = await saved.json();
    if(new URLSearchParams(location.search).get('registered') === '1' || reconnectRequested) {
      history.replaceState(null,'',location.pathname);
      const response = await fetch('/api/auth/me',{cache:'no-store'});
      if(response.ok) registrationMogobe = (await response.json()).username;
      else { reconnectRequested = false; showNotice('Сессия завершилась. Войдите снова.'); }
    }
    const runtime = await (await fetch('/client/runtime',{cache:'no-store'})).json();
    if(!runtime.socket_url) throw new Error('Не удалось создать подключение к миру.');
    await player.ruffle().load({url:'/compat/MogobeHost.swf', base:location.origin+'/',
      socketProxy:[{host:'127.0.0.1',port:9339,proxyUrl:runtime.socket_url}],
      parameters:{Lang:'5',appVer:'20130305',serverList:'true',debug:'false',
        httpPort:location.port || '80',mainDomain:location.host,mediaURL:''}});
    window.mogobeReady = true;
  } catch(error) { showNotice(`Не удалось загрузить игру: ${error.message}`); }
})();
