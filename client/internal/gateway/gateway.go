// Package gateway translates the old SWF's local GET login to a remote POST.
// All account state belongs to FastAPI. This layer owns no game database.
package gateway

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"io/fs"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"

	"github.com/firocore/mogobe/client/internal/accounts"
)

type Gateway struct {
	chatPhrases     map[string]string
	ItemAssets      fs.FS
	CopyAvatarImage ImageCopier
	target          *url.URL
	client          *http.Client
	Accounts        *accounts.Store
	resultMu        sync.Mutex
	lastLogin       loginResult
	world           worldSocket
}

func New(serverURL string, timeout time.Duration) *Gateway {
	target, _ := url.Parse(serverURL) // Config is validated before construction.
	return &Gateway{target: target, client: &http.Client{
		Timeout:       timeout,
		CheckRedirect: func(_ *http.Request, _ []*http.Request) error { return http.ErrUseLastResponse },
	}}
}

func (g *Gateway) Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		lower := strings.ToLower(r.URL.Path)
		// Original Main requests numbered popup paths. Store each SWF once
		// under its descriptive name and resolve the old URL locally.
		popupAliases := map[string]string{
			"/swf/assets/popups/p_3.swf":  "/Swf/Assets/Popups/WorldMap.swf",
			"/swf/assets/popups/p_7.swf":  "/Swf/Assets/Popups/MyProfile.swf",
			"/swf/assets/popups/p_8.swf":  "/Swf/Assets/Popups/PlayerProfile.swf",
			"/swf/assets/popups/p_24.swf": "/Swf/Assets/Popups/FriendsList.swf",
			"/swf/assets/popups/p_33.swf": "/Swf/Assets/Popups/Shop.swf",
		}
		// Administration is a separate application with its own browser session.
		if lower == "/admin" || strings.HasPrefix(lower, "/admin/") || strings.HasPrefix(lower, "/api/admin/") {
			http.NotFound(w, r)
			return
		}
		if strings.HasPrefix(lower, "/swf/items/") {
			parts := strings.Split(strings.TrimPrefix(lower, "/swf/items/"), "/")
			roles := map[string]string{"display": "Display", "inuse": "InUse", "cats": "Cats"}
			if len(parts) == 2 && roles[parts[0]] != "" {
				clone := r.Clone(r.Context())
				clone.URL.Path = "/api/shop-assets/" + roles[parts[0]] + "/" + parts[1]
				clone.URL.RawPath = ""
				g.ServeHTTP(w, clone)
				return
			}
		}
		if canonical, ok := popupAliases[lower]; ok {
			clone := r.Clone(r.Context())
			clone.URL.Path, clone.URL.RawPath = canonical, ""
			next.ServeHTTP(w, clone)
			return
		}

		if strings.HasPrefix(lower, "/api/") || strings.HasPrefix(lower, "/servises/") || strings.HasPrefix(lower, "/client/") {
			if lower == "/servises/lang.aspx" {
				next.ServeHTTP(w, r)
				return
			}
			g.ServeHTTP(w, r)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func (g *Gateway) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "no-store")
	if origin := r.Header.Get("Origin"); origin != "" {
		u, err := url.Parse(origin)
		if err != nil || !strings.EqualFold(u.Host, r.Host) {
			http.Error(w, "Origin rejected", http.StatusForbidden)
			return
		}
	}
	if r.Header.Get("Sec-Fetch-Site") == "cross-site" {
		http.Error(w, "Origin rejected", http.StatusForbidden)
		return
	}
	if r.URL.Path == "/client/world/status" && r.Method == http.MethodGet {
		g.worldStatus(w, r)
		return
	}
	if r.URL.Path == "/client/runtime" && r.Method == "GET" {
		g.worldRuntime(w)
		return
	}
	if r.URL.Path == "/client/world/leave" && r.Method == http.MethodPost {
		// F5 keeps the bounded history for this Go-held session only.
		// A normal return to the picker clears it without revoking the login.
		g.changeWorldSession("", r.URL.Query().Get("reconnect") == "1")
		w.WriteHeader(http.StatusNoContent)
		return
	}
	if r.URL.Path == "/client/clipboard/avatar" {
		g.avatarClipboard(w, r)
		return
	}
	path := r.URL.Path
	if strings.HasPrefix(path, "/client/") {
		g.localAccounts(w, r)
		return
	}
	if strings.HasPrefix(r.URL.Path, "/api/shop-assets/") {
		g.serveGraphic(w, r)
		return
	}
	method, body := r.Method, io.Reader(r.Body)
	legacy := false
	switch strings.ToLower(path) {
	case "/servises/login.aspx":
		if g.Accounts != nil {
			g.rememberedLogin(w, r)
			return
		}
		legacy = true
		if method != http.MethodGet {
			http.Error(w, "Method not allowed", 405)
			return
		}
		query := r.URL.Query()
		user, password := query.Get("user"), query.Get("pass")
		if user == "" || password == "" || len(user) > 256 || len(password) > 512 {
			w.Header().Set("Content-Type", "application/xml")
			io.WriteString(w, `<Response><Login status="6"/></Response>`)
			return
		}
		encoded, _ := json.Marshal(map[string]string{"username": user, "password": password})
		method, body, path = http.MethodPost, bytes.NewReader(encoded), "/legacy/login"
	case "/servises/servers.aspx":
		if method != http.MethodGet {
			http.Error(w, "Method not allowed", 405)
			return
		}
		path = "/legacy/servers" // Old SWF repeats credentials; never forward that query.
	default:
		if !strings.HasPrefix(path, "/api/") || strings.HasPrefix(path, "/api/admin/") {
			http.NotFound(w, r)
			return
		}
		if method != http.MethodGet && method != http.MethodPost {
			http.Error(w, "Method not allowed", 405)
			return
		}
		body = http.MaxBytesReader(w, r.Body, 64*1024)
	}
	target := *g.target
	target.Path = strings.TrimRight(target.Path, "/") + path
	target.RawPath, target.RawQuery = "", ""
	if path == "/api/shop-points" {
		query := target.Query()
		if room := r.URL.Query().Get("room"); room != "" {
			query.Set("room", room)
		}
		target.RawQuery = query.Encode()
	}
	out, err := http.NewRequestWithContext(r.Context(), method, target.String(), body)
	if err != nil {
		http.Error(w, "Invalid backend URL", 502)
		return
	}
	out.Header.Set("Content-Type", "application/json")
	for _, cookie := range r.Cookies() {
		if cookie.Name == "mogobe_session" || cookie.Name == "mogobe_registration" {
			out.AddCookie(cookie)
		}
	}
	response, err := g.client.Do(out)
	if err != nil {
		// Never print errors containing the SWF's original URL or credentials.
		if legacy {
			w.Header().Set("Content-Type", "application/xml")
			io.WriteString(w, `<Response><Login status="4"/></Response>`)
		} else {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadGateway)
			json.NewEncoder(w).Encode(map[string]string{"detail": "Сервер недоступен. Проверьте адрес в client.json и запустите сервер."})
		}
		return
	}
	defer response.Body.Close()
	if path == "/api/auth/logout" && response.StatusCode == 204 {
		g.setWorldSession("")
	}
	if path == "/api/auth/logout" && response.StatusCode == 204 && g.Accounts != nil {
		if cookie, err := r.Cookie("mogobe_session"); err == nil {
			if err = g.Accounts.ClearToken(cookie.Value); err != nil {
				http.Error(w, "Не удалось обновить список могоби", 500)
				return
			}
		}
	}
	if response.StatusCode >= 300 && response.StatusCode < 400 {
		http.Error(w, "Backend redirect rejected; configure its final URL", 502)
		return
	}
	w.Header().Set("Content-Type", response.Header.Get("Content-Type"))
	// Wails' Windows response writer joins repeated Set-Cookie values with a
	// comma, which can apply the draft's expiry to the new session. A consumed
	// draft is already invalid on the server, so let its local cookie expire
	// naturally and deliver the session in a single Set-Cookie header.
	hasNewSession := false
	for _, cookie := range response.Cookies() {
		if cookie.Name == "mogobe_session" && cookie.MaxAge >= 0 && cookie.Value != "" {
			hasNewSession = true
			g.setWorldSession(cookie.Value)
		}
	}
	for _, cookie := range response.Cookies() {
		if cookie.Name != "mogobe_session" && cookie.Name != "mogobe_registration" {
			continue
		}
		if hasNewSession && cookie.Name == "mogobe_registration" && cookie.MaxAge < 0 {
			continue
		}
		cookie.Domain, cookie.Path = "", "/"
		// This cookie belongs to Wails' local HTTP origin. The remote request still uses HTTPS.
		cookie.Secure, cookie.HttpOnly, cookie.SameSite = false, true, http.SameSiteStrictMode
		http.SetCookie(w, cookie)
	}
	w.WriteHeader(response.StatusCode)
	responseLimit := int64(1024 * 1024)
	if strings.HasPrefix(path, "/api/shop-assets/") {
		responseLimit = 8 * 1024 * 1024
	}
	if _, err = io.Copy(w, io.LimitReader(response.Body, responseLimit)); err != nil {
		return
	}
}

func (g *Gateway) ServerLabel() string { return fmt.Sprint(g.target.Host) }
