/* Original archived HTML and original AvatarRegColor/AvatarDisplay SWFs. */
const step = window.MOGO_REG_STEP;
const storageKey = 'mogobe.registration';
let draft;
try { draft = JSON.parse(sessionStorage.getItem(storageKey) || '{}'); } catch { draft = {}; }
const save = () => sessionStorage.setItem(storageKey, JSON.stringify(draft));
const field = suffix => document.getElementById('ctl00_regHolder_1_'+suffix);
const go = number => location.assign(`/Registration${number}.aspx`);
function note(message) {
  const element = document.createElement('p');
  element.style.cssText = 'font:13px Arial;text-align:center;margin:8px auto;max-width:830px';
  element.textContent = message; document.body.prepend(element); return element;
}
const error = message => {
  window.showMogobePopup(message);
};
async function api(path, body) {
  let response;
  try { response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); }
  catch { throw new Error('Нет связи с сервером. Попробуйте ещё раз.'); }
  let payload;
  try { payload = await response.json(); }
  catch { throw new Error('Не удалось получить ответ сервера. Попробуйте ещё раз.'); }
  if(!response.ok) {
    if(response.status === 401) { draft = {}; save(); }
    throw new Error(typeof payload.detail === 'string' ? payload.detail : 'Проверьте заполненные поля.');
  }
  return payload;
}
function control(suffix, type, checked) {
  const input = field(suffix); input.type = type; input.removeAttribute('src');
  input.style.cssText = 'width:18px;height:18px;cursor:pointer';
  if(type === 'radio') input.name = 'chat-mode';
  input.checked = checked; return input;
}
// Missing historical checkbox bitmaps use native controls with the original labels.
document.querySelectorAll('img[src$="notice.gif"]').forEach(img => img.hidden = true);
document.querySelectorAll('a[href="parentLetter.aspx"]').forEach(link => {
  link.removeAttribute('target'); link.href = '#';
  link.addEventListener('click', event => { event.preventDefault(); window.showMogobePopup('Письма и подтверждение по почте пока не подключены.'); });
});
if(step === 2) {
  draft = {}; save();
  window.selectColor = color => {
    const selected = Number(color) >= 13 ? 1 : Number(color);
    if(!Number.isInteger(selected) || selected < 1 || selected > 12) return;
    document.getElementById('userColor').value = String(selected);
    draft.color_id = selected; save();
  };
}
if(step === 3) {
  if(!draft.color_id) go(2);
  field('txtNick').minLength = 4;
  field('txtNick').maxLength = 15;
  field('txtNick').pattern = '[A-Za-zА-Яа-яЁё0-9_]{4,15}';
  field('txtNick').title = '4–15 символов: латинские и русские буквы, цифры и _. Без пробелов.';
  field('Label1').textContent = 'Используйте латинские и русские буквы, цифры и _. Имя: 4–15 символов, без пробелов.';
  document.querySelectorAll('object param[name="movie"],embed').forEach(node => {
    const key = node.tagName === 'EMBED' ? 'src' : 'value';
    node.setAttribute(key, node.getAttribute(key).replace('color=0','color='+draft.color_id));
  });
  if(draft.username) field('txtNick').value = draft.username;
}
if([4,5,7].includes(step) && !draft.started) go(2);
if(step === 4) {
  const ageSelect = field('ddlAge');
  const ageInput = document.createElement('input');
  ageInput.id = ageSelect.id;
  ageInput.name = ageSelect.name;
  ageInput.className = ageSelect.className;
  ageInput.type = 'number';
  ageInput.min = '1';
  ageInput.max = '100';
  ageInput.step = '1';
  ageInput.required = true;
  ageInput.setAttribute('aria-label', 'Возраст');
  ageSelect.replaceWith(ageInput);
  control('imgRegular','radio',draft.chat_mode !== 'closed');
  control('imgYoung','radio',draft.chat_mode === 'closed');
  if(draft.age) field('ddlAge').value = draft.age;
}
if(step === 5) {
  control('btnAgree','checkbox',Boolean(draft.accepted_terms));
  control('btnEmailAgree','checkbox',Boolean(draft.newsletter));
}
if(step === 7) {
  note('Почту можно оставить пустой. Подтверждение по почте пока не требуется.');
  document.getElementById('ctl00_regHolder_3_btnSend').src = '/Media/images/Registration/continuebtn.gif';
}
if(step === 8 || step === 'confirm') {
  if(!draft.completed) go(2);
  document.querySelectorAll('a').forEach(link => { link.href = '/?registered=1'; link.removeAttribute('target'); });
  note('Аккаунт создан. Выберите сервер, чтобы войти в игру. Письма и награды пока не отправляются.');
  const link = document.createElement('a'); link.href = '/?registered=1'; link.textContent = 'Войти в игру';
  note('').appendChild(link);
}
let submitting = false;
document.getElementById('aspnetForm')?.addEventListener('invalid',event=>{
  event.preventDefault();
  error(event.target === field('txtNick') ? field('txtNick').title :
    event.target === field('ddlAge') ? 'Введите целый возраст от 1 до 100.' : 'Проверьте заполненные поля.');
},true);
document.getElementById('aspnetForm')?.addEventListener('submit', async event => {
  event.preventDefault();
  if(submitting) return;
  submitting = true;
  try {
    if(step === 2) {
      if(!draft.color_id) throw new Error('Выберите цвет своего могоби.');
      go(3);
    } else if(step === 3) {
      const username = field('txtNick').value, password = field('txtPass').value;
      if(username.length < 4 || username.length > 15 || /[^A-Za-zА-Яа-яЁё0-9_]/.test(username)) throw new Error('Имя: 4–15 символов — русские и латинские буквы, цифры и _. Пробелы и другие символы запрещены.');
      if(password.length < 4 || password.length > 10) throw new Error('Пароль: от 4 до 10 символов.');
      if(password !== field('txtRePass').value) throw new Error('Пароли не совпадают.');
      await api('/api/auth/registration-drafts', {username,password,color_id:draft.color_id});
      field('txtPass').value = ''; field('txtRePass').value = '';
      draft.username = username; draft.started = true; save(); go(4);
    } else if(step === 4) {
      const age = Number(field('ddlAge').value);
      if(!Number.isInteger(age) || age < 1 || age > 100) throw new Error('Введите целый возраст от 1 до 100.');
      draft.age = age; draft.chat_mode = field('imgYoung').checked ? 'closed' : 'open'; save(); go(5);
    } else if(step === 5) {
      draft.accepted_terms = field('btnAgree').checked;
      draft.newsletter = field('btnEmailAgree').checked; save(); go(7);
    } else if(step === 7) {
      const email = field('txtParentEmail').value.trim();
      if(email !== field('txtReEmail').value.trim()) throw new Error('Адреса электронной почты не совпадают.');
      await api('/api/auth/register', {age:draft.age,chat_mode:draft.chat_mode,
        accepted_terms:draft.accepted_terms,newsletter:draft.newsletter,parent_email:email || null});
      draft = {completed:true}; save(); go(8);
    } else if(step === 'confirm') location.assign('/?registered=1');
  } catch(exception) { error(exception.message || 'Нет связи с сервером. Попробуйте ещё раз.'); }
  finally { submitting = false; }
});
