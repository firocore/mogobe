package gateway

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestRegistrationPagesUseHTMLWithoutChangingLegacyXML(t *testing.T) {
	g := New("http://unused.invalid", time.Second)
	pages := map[string]bool{
		"/Registration2.aspx": true, "/Registration3.aspx": true,
		"/Registration4.aspx": true, "/Registration5.aspx": true,
		"/Registration7.aspx": true, "/Registration8.aspx": true,
		"/ConfirmRegistration.aspx": true,
	}
	files := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !pages[r.URL.Path] && r.URL.Path != "/Servises/lang.aspx" {
			http.NotFound(w, r)
			return
		}
		// Simulate Windows registering .aspx as XML.
		if w.Header().Get("Content-Type") == "" {
			w.Header().Set("Content-Type", "application/xml")
		}
		io.WriteString(w, "<html></html>")
	})
	handler := g.Middleware(files)
	for path := range pages {
		t.Run(path, func(t *testing.T) {
			w := httptest.NewRecorder()
			handler.ServeHTTP(w, httptest.NewRequest("GET", path, nil))
			if w.Code != http.StatusOK || w.Header().Get("Content-Type") != "text/html; charset=utf-8" {
				t.Fatalf("status %d, content type %q", w.Code, w.Header().Get("Content-Type"))
			}
		})
	}
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, httptest.NewRequest("GET", "/Servises/lang.aspx", nil))
	if w.Code != http.StatusOK || w.Header().Get("Content-Type") != "application/xml" {
		t.Fatalf("legacy XML changed: status %d, content type %q", w.Code, w.Header().Get("Content-Type"))
	}
	w = httptest.NewRecorder()
	handler.ServeHTTP(w, httptest.NewRequest("GET", "/Registrationconfirm.aspx", nil))
	if w.Code != http.StatusNotFound {
		t.Fatalf("nonexistent registration page: status %d", w.Code)
	}
}

func TestLegacyLoginUsesRemoteHTTPSPostAndLocalCookie(t *testing.T) {
	remote := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" || r.URL.Path != "/prefix/legacy/login" || r.URL.RawQuery != "" {
			t.Errorf("unexpected request: %s %s", r.Method, r.URL)
		}
		var credentials map[string]string
		json.NewDecoder(r.Body).Decode(&credentials)
		if credentials["username"] != "Mogo12" || credentials["password"] != "Pass1234" {
			t.Error("credentials not translated")
		}
		http.SetCookie(w, &http.Cookie{Name: "mogobe_session", Value: "opaque-token", Secure: true, Domain: "remote.example"})
		w.Header().Set("Content-Type", "application/xml")
		io.WriteString(w, `<Response><Login status="1"/></Response>`)
	}))
	defer remote.Close()
	g := New(remote.URL+"/prefix", time.Second)
	g.client = remote.Client()
	w := httptest.NewRecorder()
	g.ServeHTTP(w, httptest.NewRequest("GET", "http://local/Servises/Login.aspx?user=Mogo12&pass=Pass1234", nil))
	if w.Code != 200 || !strings.Contains(w.Body.String(), `status="1"`) {
		t.Fatalf("%d %s", w.Code, w.Body.String())
	}
	cookies := w.Result().Cookies()
	if len(cookies) != 1 || !cookies[0].HttpOnly || cookies[0].Secure || cookies[0].Domain != "" || cookies[0].Path != "/" {
		t.Fatalf("bad local cookies: %+v", cookies)
	}
}

func TestServerListDropsCredentialsAndForwardsSession(t *testing.T) {
	remote := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/legacy/servers" || r.URL.RawQuery != "" {
			t.Errorf("unsafe target %s", r.URL)
		}
		cookie, err := r.Cookie("mogobe_session")
		if err != nil || cookie.Value != "session" {
			t.Error("missing session")
		}
		if _, err := r.Cookie("unrelated"); err == nil {
			t.Error("forwarded unrelated cookie")
		}
		io.WriteString(w, "servers")
	}))
	defer remote.Close()
	g := New(remote.URL, time.Second)
	r := httptest.NewRequest("GET", "http://local/Servises/Servers.aspx?user=Mogo&pass=Secret", nil)
	r.AddCookie(&http.Cookie{Name: "mogobe_session", Value: "session"})
	r.AddCookie(&http.Cookie{Name: "unrelated", Value: "private"})
	w := httptest.NewRecorder()
	g.ServeHTTP(w, r)
	if w.Code != 200 || w.Body.String() != "servers" {
		t.Fatal(w.Code, w.Body.String())
	}
}

func TestRejectCrossOriginAndBackendRedirect(t *testing.T) {
	remote := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, "https://elsewhere.example", http.StatusTemporaryRedirect)
	}))
	defer remote.Close()
	g := New(remote.URL, time.Second)
	r := httptest.NewRequest("POST", "http://local/api/auth/login", strings.NewReader(`{}`))
	r.Header.Set("Origin", "https://other.example")
	w := httptest.NewRecorder()
	g.ServeHTTP(w, r)
	if w.Code != 403 {
		t.Fatal(w.Code)
	}
	r.Header.Set("Origin", "http://local")
	w = httptest.NewRecorder()
	g.ServeHTTP(w, r)
	if w.Code != 502 {
		t.Fatal(w.Code)
	}
}

func TestOfflineLegacyIsValidXMLError(t *testing.T) {
	closed := httptest.NewServer(http.NotFoundHandler())
	address := closed.URL
	closed.Close()
	g := New(address, time.Second)
	w := httptest.NewRecorder()
	g.ServeHTTP(w, httptest.NewRequest("GET", "http://local/Servises/Login.aspx?user=Mogo&pass=Secret", nil))
	if w.Code != 200 || !strings.Contains(w.Body.String(), `status="4"`) || strings.Contains(w.Body.String(), "Secret") {
		t.Fatal(w.Code, w.Body.String())
	}
}

func TestRegistrationSessionSurvivesWindowsCookieHeaderJoining(t *testing.T) {
	remote := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.SetCookie(w, &http.Cookie{Name: "mogobe_session", Value: "new-session", MaxAge: 86400, HttpOnly: true})
		http.SetCookie(w, &http.Cookie{Name: "mogobe_registration", Value: "", MaxAge: -1, Expires: time.Unix(0, 0)})
		w.WriteHeader(http.StatusCreated)
		io.WriteString(w, `{"username":"NewMogo","color_id":1}`)
	}))
	defer remote.Close()
	g := New(remote.URL, time.Second)
	w := httptest.NewRecorder()
	g.ServeHTTP(w, httptest.NewRequest("POST", "http://local/api/auth/register", strings.NewReader(`{}`)))
	cookies := w.Result().Cookies()
	if w.Code != http.StatusCreated || len(cookies) != 1 || cookies[0].Name != "mogobe_session" || cookies[0].Value != "new-session" || cookies[0].MaxAge != 86400 || !cookies[0].HttpOnly {
		t.Fatalf("registration session cookie lost: %+v", cookies)
	}
}

func TestOriginalPopupPathsResolveToDescriptiveAssets(t *testing.T) {
	g := New("http://127.0.0.1:8000", time.Second)
	for numbered, canonical := range map[string]string{"p_7.swf": "MyProfile.swf", "p_8.swf": "PlayerProfile.swf", "p_24.swf": "FriendsList.swf"} {
		downstream := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if r.URL.Path != "/Swf/Assets/Popups/"+canonical || r.URL.RawQuery != "appVer=2013" {
				t.Fatalf("incorrect resource mapping: %s", r.URL.String())
			}
			w.WriteHeader(200)
		})
		request := httptest.NewRequest("GET", "http://local/Swf/Assets/Popups/"+numbered+"?appVer=2013", nil)
		response := httptest.NewRecorder()
		g.Middleware(downstream).ServeHTTP(response, request)
		if response.Code != 200 || !strings.HasSuffix(request.URL.Path, numbered) {
			t.Fatal("resource alias failed or mutated original request")
		}
	}
}

func TestShopPointsForwardOnlyRoomQuery(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/shop-points" || r.URL.RawQuery != "room=mall" {
			t.Errorf("unexpected point request: %s", r.URL.String())
		}
		io.WriteString(w, `{"room":"mall","points":[]}`)
	}))
	defer server.Close()
	g := New(server.URL, time.Second)
	w := httptest.NewRecorder()
	g.ServeHTTP(w, httptest.NewRequest(http.MethodGet, "/api/shop-points?room=mall&password=discard", nil))
	if w.Code != http.StatusOK {
		t.Fatalf("status %d", w.Code)
	}
}
