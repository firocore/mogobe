package gateway

import (
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"

	"github.com/firocore/mogobe/client/internal/accounts"
)

type jokeTransport func(*http.Request) (*http.Response, error)

func (f jokeTransport) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }

func TestAdminLoginJokeOnlyInterceptsRemotePasswordLogin(t *testing.T) {
	cases := []struct {
		name, server, username, password string
		joke                             bool
	}{
		{"remote", "https://game.example", "admin", "admin", true},
		{"remote prefix", "https://game.example/mogobe", "ADMIN", "admin", true},
		{"localhost", "http://localhost:8000", "admin", "admin", false},
		{"localhost spelling", "https://LOCALHOST.:8000", "admin", "admin", false},
		{"ipv4", "http://127.0.0.1:8000", "admin", "admin", false},
		{"loopback range", "http://127.0.0.2:8000", "admin", "admin", false},
		{"ipv6", "http://[::1]:8000", "admin", "admin", false},
		{"mapped loopback", "http://[::ffff:127.0.0.1]:8000", "admin", "admin", false},
		{"lan server", "http://192.168.1.2:8000", "admin", "admin", true},
		{"misleading hostname", "https://localhost.example", "admin", "admin", true},
		{"other password", "https://game.example", "admin", "Admin", false},
		{"other user", "https://game.example", "Player", "admin", false},
		{"saved session", "https://game.example", "admin", accounts.SavedSessionMarker, false},
	}
	for _, remembered := range []bool{false, true} {
		mode := "legacy/"
		if remembered {
			mode = "remembered/"
		}
		for _, tc := range cases {
			t.Run(mode+tc.name, func(t *testing.T) {
				g := New(tc.server, time.Second)
				if remembered {
					g.Accounts = &accounts.Store{}
				}
				opened, forwarded := 0, 0
				g.OpenLoginJoke = func() { opened++ }
				g.client.Transport = jokeTransport(func(r *http.Request) (*http.Response, error) {
					forwarded++
					return &http.Response{StatusCode: 200, Header: http.Header{"Content-Type": {"application/xml"}}, Body: io.NopCloser(strings.NewReader(`<Response><Login status="2"/></Response>`))}, nil
				})
				r := httptest.NewRequest("GET", "/Servises/Login.aspx?user="+url.QueryEscape(tc.username)+"&pass="+url.QueryEscape(tc.password), nil)
				w := httptest.NewRecorder()
				g.ServeHTTP(w, r)
				if (opened == 1) != tc.joke {
					t.Fatalf("opened %d times, expected joke=%v", opened, tc.joke)
				}
				if tc.joke && (forwarded != 0 || len(w.Result().Cookies()) != 0 || g.world.token != "") {
					t.Fatal("joke forwarded credentials or changed session")
				}
				if !tc.joke && tc.password != accounts.SavedSessionMarker && forwarded != 1 {
					t.Fatalf("normal login forwarded %d times", forwarded)
				}
				if w.Code != http.StatusOK || !strings.Contains(w.Body.String(), `status="2"`) {
					t.Fatalf("login response: %d %s", w.Code, w.Body.String())
				}
			})
		}
	}
}
