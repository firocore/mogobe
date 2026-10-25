package gateway

import (
	"bytes"
	"context"
	"encoding/json"
	"encoding/xml"
	"errors"
	"io"
	"net/http"
	"net/url"
	"strings"

	"github.com/firocore/mogobe/client/internal/accounts"
)

// A non-secret marker for the HttpOnly session created by registration.
const currentSessionMarker = "__MOGOBE_CURRENT_SESSION__"

type loginPreferences struct {
	Username        string `json:"username"`
	RememberName    bool   `json:"remember_name"`
	RememberSession bool   `json:"remember_session"`
	Attempt         string `json:"attempt"`
}

type loginResult struct {
	Attempt string `json:"attempt"`
	Status  string `json:"status"`
	Message string `json:"message,omitempty"`
}

func (g *Gateway) localAccounts(w http.ResponseWriter, r *http.Request) {
	if g.Accounts == nil {
		http.Error(w, "Account store unavailable", 503)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	switch {
	case r.URL.Path == "/client/accounts/refresh" && r.Method == "POST":
		g.refreshSavedOutfits(r)
		json.NewEncoder(w).Encode(g.Accounts.List())
	case r.URL.Path == "/client/accounts" && r.Method == "GET":
		json.NewEncoder(w).Encode(g.Accounts.List())
	case r.URL.Path == "/client/login-result" && r.Method == "GET":
		g.resultMu.Lock()
		result := g.lastLogin
		g.resultMu.Unlock()
		json.NewEncoder(w).Encode(result)
	case r.URL.Path == "/client/accounts/sync" && r.Method == "POST":
		var body struct {
			Names []string `json:"names"`
		}
		if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 4096)).Decode(&body); err != nil || len(body.Names) > 6 {
			http.Error(w, "Invalid account list", 400)
			return
		}
		tokens, err := g.Accounts.KeepNames(body.Names)
		if err != nil {
			http.Error(w, "Не удалось сохранить список могоби", 500)
			return
		}
		// Forget locally even when the remote server is unavailable.
		go g.revokeTokens(tokens)
		json.NewEncoder(w).Encode(g.Accounts.List())
	default:
		http.NotFound(w, r)
	}
}

func (g *Gateway) remoteJSON(path, method string, body any, token string) (*http.Response, []byte, error) {
	return g.remoteJSONContext(context.Background(), path, method, body, token)
}

func (g *Gateway) remoteJSONContext(ctx context.Context, path, method string, body any, token string) (*http.Response, []byte, error) {
	var reader io.Reader
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			return nil, nil, err
		}
		reader = bytes.NewReader(data)
	}
	target := *g.target
	target.Path = strings.TrimRight(target.Path, "/") + path
	target.RawPath = ""
	target.RawQuery = ""
	request, err := http.NewRequestWithContext(ctx, method, target.String(), reader)
	if err != nil {
		return nil, nil, err
	}
	request.Header.Set("Content-Type", "application/json")
	if token != "" {
		request.Header.Set("Authorization", "Bearer "+token)
	}
	response, err := g.client.Do(request)
	if err != nil {
		return nil, nil, err
	}
	defer response.Body.Close()
	if response.StatusCode >= 300 && response.StatusCode < 400 {
		return nil, nil, errors.New("backend redirect")
	}
	data, err := io.ReadAll(io.LimitReader(response.Body, 1024*1024))
	return response, data, err
}

func (g *Gateway) revokeTokens(tokens []string) {
	for _, token := range tokens {
		g.remoteJSON("/api/auth/logout", "POST", nil, token)
	}
}

func (g *Gateway) rememberedLogin(w http.ResponseWriter, r *http.Request) {
	if r.Method != "GET" {
		http.Error(w, "Method not allowed", 405)
		return
	}
	query := r.URL.Query()
	username, password := query.Get("user"), query.Get("pass")
	prefs := loginPreferences{Username: username, RememberName: true}
	if cookie, err := r.Cookie("mogobe_login_preferences"); err == nil {
		decoded, _ := url.QueryUnescape(cookie.Value)
		var value loginPreferences
		if json.Unmarshal([]byte(decoded), &value) == nil && strings.EqualFold(value.Username, username) {
			prefs = value
		}
	}
	finish := func(status, message string) {
		g.resultMu.Lock()
		g.lastLogin = loginResult{prefs.Attempt, status, message}
		g.resultMu.Unlock()
	}
	fail := func(status, message string) {
		finish(status, message)
		w.Header().Set("Content-Type", "application/xml")
		io.WriteString(w, `<Response><Login status="`+status+`"/></Response>`)
	}
	if username == "" || password == "" || len(username) > 256 || len(password) > 512 {
		fail("6", "")
		return
	}
	if g.openAdminLoginJoke(username, password) {
		fail("2", "")
		return
	}
	currentSession := password == currentSessionMarker
	resuming := password == accounts.SavedSessionMarker || currentSession
	var previous string
	if cookie, err := r.Cookie("mogobe_session"); err == nil {
		previous = cookie.Value
	}
	path := "/legacy/login"
	var body any = map[string]any{"username": username, "password": password, "remember_me": prefs.RememberSession}
	if resuming {
		if !currentSession {
			previous = g.Accounts.Token(username)
		}
		if previous == "" {
			fail("2", "Введите пароль этого могоби.")
			return
		}
		path = "/legacy/resume"
		body = map[string]string{"username": username}
	}
	response, data, err := g.remoteJSON(path, "POST", body, previous)
	if err != nil {
		fail("4", "Нет связи с сервером. Сохранённая авторизация не удалена.")
		return
	}
	var reply struct {
		Login struct {
			Status   string `xml:"status,attr"`
			Message  string `xml:"message,attr"`
			Username string `xml:"username,attr"`
			ColorID  int    `xml:"colorId,attr"`
		} `xml:"Login"`
	}
	if response.StatusCode != 200 || xml.Unmarshal(data, &reply) != nil || reply.Login.Status == "" {
		fail("4", "Сервер вернул некорректный ответ.")
		return
	}
	if reply.Login.Status != "1" {
		if resuming && !currentSession && reply.Login.Status == "2" {
			if err = g.Accounts.ClearToken(previous); err != nil {
				fail("4", "Не удалось обновить сохранённую авторизацию.")
				return
			}
			fail("2", "Сохранённая сессия истекла. Введите пароль ещё раз.")
			return
		}
		fail(reply.Login.Status, reply.Login.Message)
		return
	}
	token := previous
	maxAge := 24 * 3600
	for _, cookie := range response.Cookies() {
		if cookie.Name == "mogobe_session" {
			token = cookie.Value
			maxAge = cookie.MaxAge
		}
	}
	if resuming && prefs.RememberSession {
		maxAge = 30 * 86400
	}
	if token == "" || reply.Login.Username == "" || reply.Login.ColorID < 1 || reply.Login.ColorID > 12 {
		fail("4", "Сервер не передал данные могоби.")
		return
	}
	removed, err := g.Accounts.Remember(reply.Login.Username, reply.Login.ColorID, token, prefs.RememberName, prefs.RememberSession)
	if err != nil {
		fail("4", "Не удалось сохранить авторизацию на этом компьютере.")
		return
	}
	// The selected token remains valid for this login even if Remember is unchecked.
	var superseded []string
	for _, old := range removed {
		if old != token {
			superseded = append(superseded, old)
		}
	}
	go g.revokeTokens(superseded)
	g.setWorldSession(token)
	http.SetCookie(w, &http.Cookie{Name: "mogobe_session", Value: token, Path: "/", HttpOnly: true, SameSite: http.SameSiteStrictMode, MaxAge: maxAge})
	finish("1", "")
	w.Header().Set("Content-Type", "application/xml")
	w.Write(data)
}
