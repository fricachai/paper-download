# Login Gate Reuse Guide

這份文件把目前 `Stock_K-chat` 的前端登入門禁與登入視覺拆成可重用做法，方便直接套用到其他純前端專案。

## 1. 功能內容

- 前端帳密登入
- 可接受多個帳號
- 密碼共用
- `sessionStorage` / `localStorage` 記住登入狀態
- 登出按鈕
- 登入前遮住主畫面
- 登入卡片的霓虹圓角外框
- 登入按鈕 hover 的淡紫色光暈互動

## 2. 現在專案內的對應檔案

- HTML 結構：`index.html`
- 樣式：`styles.css`
- 邏輯：`app.js`

## 3. 直接套用方式

### Step 1. 在 HTML 放入登入遮罩

把這段放在 `body` 內，並放在主應用畫面前面：

```html
<div id="loginGate" class="login-gate">
  <div class="login-frame">
    <svg class="login-border-svg" viewBox="0 0 420 520" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id="loginBorderGradient" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="420" y2="0">
          <stop offset="0%" stop-color="#ff63c8" />
          <stop offset="25%" stop-color="#ffbe72" />
          <stop offset="50%" stop-color="#7ce1ff" />
          <stop offset="75%" stop-color="#b47cff" />
          <stop offset="100%" stop-color="#ff63c8" />
          <animateTransform
            attributeName="gradientTransform"
            type="rotate"
            from="0 210 260"
            to="360 210 260"
            dur="7.2s"
            repeatCount="indefinite"
          />
        </linearGradient>
      </defs>
      <rect x="1.5" y="1.5" width="417" height="517" rx="22" ry="22" class="login-border-stroke" />
    </svg>

    <div class="login-panel">
      <h2>登入股票觀察面板</h2>
      <form id="loginForm" class="login-form">
        <input id="loginUsername" type="text" autocomplete="username" placeholder="帳號" />
        <input id="loginPassword" type="password" autocomplete="current-password" placeholder="密碼" />
        <label class="remember-me">
          <input id="rememberLogin" type="checkbox" />
          <span>記住登入狀態</span>
        </label>
        <button type="submit">登入</button>
      </form>
      <p id="loginStatus" class="login-status">請先登入後再進入面板。</p>
    </div>
  </div>
</div>
```

### Step 2. 把你的主應用包起來

把主畫面最外層容器改成：

```html
<div id="appShell" class="app-shell app-shell--hidden" aria-hidden="true">
  <!-- 原本主畫面內容 -->
</div>
```

如果你需要登出按鈕，在主畫面內加：

```html
<button id="logoutButton" type="button">登出</button>
```

### Step 3. 加入 CSS

至少需要下面這些選擇器：

```css
body.auth-locked {
  overflow: hidden;
}

.login-gate {
  position: fixed;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 24px;
  background:
    radial-gradient(circle at top left, rgba(54, 104, 190, 0.18), transparent 24%),
    radial-gradient(circle at bottom right, rgba(255, 152, 17, 0.08), transparent 20%),
    rgba(4, 6, 10, 0.86);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  z-index: 30;
}

.login-gate--hidden {
  display: none;
}

.login-frame {
  position: relative;
  width: min(100%, 420px);
  padding: 2px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.01);
  box-shadow: 0 0 20px rgba(0, 0, 0, 0.24);
  overflow: hidden;
}

.login-border-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 2;
  pointer-events: none;
}

.login-border-stroke {
  fill: none;
  stroke: url(#loginBorderGradient);
  stroke-width: 3;
  stroke-linecap: round;
  opacity: 0.96;
  filter:
    drop-shadow(0 0 8px rgba(255, 99, 200, 0.28))
    drop-shadow(0 0 12px rgba(124, 225, 255, 0.22))
    drop-shadow(0 0 16px rgba(180, 124, 255, 0.18));
}

.login-panel {
  position: relative;
  z-index: 1;
  width: 100%;
  padding: 28px;
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(17, 20, 27, 0.96), rgba(11, 13, 18, 0.98));
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.38);
}

.login-panel h2 {
  margin-top: 6px;
  font-size: 28px;
  text-align: center;
}

.login-form {
  display: grid;
  gap: 12px;
  margin-top: 20px;
}

.login-form input[type="text"],
.login-form input[type="password"] {
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.03);
  color: #f5f6fa;
  font-size: 15px;
}

.login-form button {
  border: 1px solid rgba(247, 200, 67, 0.28);
  border-radius: 14px;
  padding: 12px 14px;
  background: linear-gradient(180deg, rgba(247, 200, 67, 0.26), rgba(247, 200, 67, 0.12));
  color: #fff9de;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition:
    transform 180ms ease,
    border-color 220ms ease,
    box-shadow 220ms ease,
    background 220ms ease;
}

.login-form button:hover {
  transform: translateY(-1px);
  border-color: rgba(197, 162, 255, 0.56);
  background: linear-gradient(180deg, rgba(214, 184, 255, 0.34), rgba(180, 147, 255, 0.24) 56%, rgba(143, 121, 255, 0.18));
  box-shadow:
    0 0 12px rgba(208, 176, 255, 0.28),
    0 0 20px rgba(176, 143, 255, 0.24),
    0 0 28px rgba(145, 120, 255, 0.14);
}

.remember-me {
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  align-self: flex-start;
  justify-self: start;
  width: auto;
  max-width: fit-content;
  gap: 0;
  color: #97a0af;
  font-size: 14px;
  white-space: nowrap;
}

.remember-me input {
  flex: 0 0 auto;
  accent-color: #f7c843;
  margin: 0;
}

.remember-me span {
  white-space: nowrap;
  margin-left: 0;
}

.login-status {
  margin-top: 14px;
  min-height: 22px;
  color: #97a0af;
  font-size: 13px;
}

.login-status.error {
  color: #ffd7dd;
}

.app-shell--hidden {
  visibility: hidden;
}
```

### Step 4. 加入 JS 驗證邏輯

把下面邏輯加到主程式：

```js
const appShell = document.getElementById("appShell");
const loginGate = document.getElementById("loginGate");
const loginForm = document.getElementById("loginForm");
const loginUsername = document.getElementById("loginUsername");
const loginPassword = document.getElementById("loginPassword");
const rememberLogin = document.getElementById("rememberLogin");
const loginStatus = document.getElementById("loginStatus");
const logoutButton = document.getElementById("logoutButton");

const AUTH_CONFIG = {
  usernames: ["frica", "jimmy"],
  password: "stock2026",
};

const AUTH_STORAGE_KEY = "stock-k-chat-auth";

function getAuthStorage(remember) {
  return remember ? window.localStorage : window.sessionStorage;
}

function hasStoredAuth() {
  return (
    window.localStorage.getItem(AUTH_STORAGE_KEY) === "1" ||
    window.sessionStorage.getItem(AUTH_STORAGE_KEY) === "1"
  );
}

function persistAuth(remember) {
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  window.sessionStorage.removeItem(AUTH_STORAGE_KEY);
  getAuthStorage(remember).setItem(AUTH_STORAGE_KEY, "1");
}

function clearAuth() {
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  window.sessionStorage.removeItem(AUTH_STORAGE_KEY);
}

function setGateLocked(locked) {
  document.body.classList.toggle("auth-locked", locked);
  appShell.classList.toggle("app-shell--hidden", locked);
  appShell.setAttribute("aria-hidden", locked ? "true" : "false");
  loginGate.classList.toggle("login-gate--hidden", !locked);
}

function setLoginStatus(message, type = "") {
  loginStatus.textContent = message;
  loginStatus.className = `login-status${type ? ` ${type}` : ""}`;
}

function startApp() {
  // 在這裡放你原本的初始化流程
  // 例如 renderAll()、loadData()、mountApp()...
}

let appStarted = false;

function bootstrap() {
  if (appStarted) return;
  appStarted = true;
  startApp();
}

function handleLoginSubmit(event) {
  event.preventDefault();
  const username = loginUsername.value.trim();
  const password = loginPassword.value;

  if (!AUTH_CONFIG.usernames.includes(username) || password !== AUTH_CONFIG.password) {
    setLoginStatus("帳號或密碼錯誤。", "error");
    loginPassword.value = "";
    loginPassword.focus();
    return;
  }

  persistAuth(rememberLogin.checked);
  setLoginStatus("登入成功。");
  setGateLocked(false);
  bootstrap();
}

function handleLogout() {
  clearAuth();
  appStarted = false;
  setGateLocked(true);
  setLoginStatus("請先登入後再進入面板。");
  loginPassword.value = "";
  loginUsername.focus();
}

loginForm.addEventListener("submit", handleLoginSubmit);
if (logoutButton) logoutButton.addEventListener("click", handleLogout);

if (hasStoredAuth()) {
  setGateLocked(false);
  bootstrap();
} else {
  setGateLocked(true);
  setLoginStatus("請先登入後再進入面板。");
}
```

## 4. 你在其他專案中只要改的地方

### 帳號密碼

改這段即可：

```js
const AUTH_CONFIG = {
  usernames: ["frica", "jimmy"],
  password: "stock2026",
};
```

### 登入成功後要啟動什麼

把：

```js
function startApp() {
  // 在這裡放你原本的初始化流程
}
```

改成你的主專案初始化。

### 主畫面容器 id

如果你不是用 `appShell`，把 JS 裡 `document.getElementById("appShell")` 改成你的實際 id。

## 5. 建議的複用方式

如果你想在別的專案快速套：

1. 先複製 HTML 結構
2. 再複製 CSS 區塊
3. 最後把 JS 驗證與 `startApp()` 接進你的專案初始化流程

## 6. 現在專案中的實作來源

如果你要直接對照目前正式版本，可看：

- `index.html` 的登入畫面結構
- `styles.css` 的 `.login-gate`、`.login-frame`、`.login-border-svg`、`.login-border-stroke`
- `app.js` 的 `AUTH_CONFIG`、`hasStoredAuth()`、`persistAuth()`、`handleLoginSubmit()`、`handleLogout()`
