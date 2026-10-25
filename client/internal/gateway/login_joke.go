package gateway

import (
	"net"
	"strings"
)

// Keep the joke local to the desktop client; never send these credentials remotely.
func (g *Gateway) openAdminLoginJoke(username, password string) bool {
	if g.OpenLoginJoke == nil || !strings.EqualFold(username, "admin") || password != "admin" {
		return false
	}
	host := strings.TrimSuffix(strings.ToLower(g.target.Hostname()), ".")
	if host == "localhost" {
		return false
	}
	if ip := net.ParseIP(host); ip != nil && ip.IsLoopback() {
		return false
	}
	g.OpenLoginJoke()
	return true
}
