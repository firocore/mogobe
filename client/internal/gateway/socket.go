package gateway

import (
	"bytes"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"io"
	"log"
	"net"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

// WebView2's asset response writer cannot upgrade HTTP to WebSocket. This
// loopback bridge tunnels Ruffle's original TCP stream to the configured API.
// Only a random local capability reaches JS; the account session stays in Go.
type worldNotice struct {
	Text   string `json:"text"`
	Sender string `json:"sender"`
}

type worldSocket struct {
	chatSession    string
	chat           []chatMessage
	chatSerial     uint64
	chatUsers      map[int]string
	notices        []worldNotice
	mu             sync.Mutex
	avatarID       int
	avatarName     string
	token          string
	generation     uint64
	socialRevision uint64
	shopRevision   uint64
	shopSerial     uint64
	shopKey        string
	minigameSerial uint64
	minigameKey    string
	error          string
	url            string
	origin         string
	connections    map[*websocket.Conn]bool
}

func (g *Gateway) setWorldSession(token string) {
	g.changeWorldSession(token, false)
}

func (g *Gateway) changeWorldSession(token string, preserveChat bool) {
	g.world.mu.Lock()
	defer g.world.mu.Unlock()
	if !preserveChat && (token == "" || g.world.chatSession != token) {
		g.world.chat = nil
		g.world.chatSerial = 0
		g.world.chatSession = ""
	}
	if token != "" {
		g.world.chatSession = token
	}
	if g.world.token != token {
		g.world.chatUsers = nil
		for connection := range g.world.connections {
			connection.Close()
		}
	}
	g.world.token = token
	g.world.generation++
	g.world.avatarID, g.world.avatarName = 0, ""
	g.world.error = ""
	g.world.notices = nil
	g.world.minigameSerial, g.world.minigameKey = 0, ""
}

func (g *Gateway) StartWorldSocket(preview string) (func(), error) {
	listener, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		return nil, err
	}
	secret := make([]byte, 32)
	if _, err = rand.Read(secret); err != nil {
		listener.Close()
		return nil, err
	}
	path := "/world/" + hex.EncodeToString(secret)
	g.world.url = "ws://" + listener.Addr().String() + path
	g.world.origin = "http://wails.localhost"
	if preview != "" {
		g.world.origin = "http://" + preview
	}
	g.world.connections = make(map[*websocket.Conn]bool)
	mux := http.NewServeMux()
	mux.HandleFunc(path, g.serveWorldSocket)
	server := &http.Server{Handler: mux, ReadHeaderTimeout: 5 * time.Second}
	go server.Serve(listener)
	return func() { g.setWorldSession(""); server.Close() }, nil
}

func (g *Gateway) worldRuntime(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"socket_url": g.world.url})
}

func (g *Gateway) worldStatus(w http.ResponseWriter, r *http.Request) {
	after := chatCursor(r.URL.Query().Get("chat_after"))
	g.world.mu.Lock()
	message, revision := g.world.error, g.world.socialRevision
	chat := make([]chatMessage, 0)
	for _, row := range g.world.chat {
		if row.ID > after {
			chat = append(chat, row)
		}
	}
	notices := g.world.notices
	g.world.notices = nil
	shopRevision, shopSerial, shopKey := g.world.shopRevision, g.world.shopSerial, g.world.shopKey
	minigameSerial, minigameKey := g.world.minigameSerial, g.world.minigameKey
	g.world.mu.Unlock()
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]any{"chat": chat, "minigame_serial": minigameSerial, "minigame_key": minigameKey, "notices": notices, "error": message, "social_revision": revision, "shop_revision": shopRevision, "shop_serial": shopSerial, "shop_key": shopKey})
}

// Social changes already arrive on the game connection. Expose a local
// revision so the frontend refreshes HTTP state only after a relevant event.
// Only server-to-client frames are inspected; the original stream is unchanged.
func (g *Gateway) observeSocialPacket(token string, generation uint64, packet []byte) {
	var event struct {
		Type string `json:"t"`
		Body struct {
			Object struct {
				Command     string `json:"_cmd"`
				Key         string `json:"key"`
				MessageType string `json:"messageType"`
				Text        string `json:"text"`
				Sender      string `json:"sender"`
			} `json:"o"`
		} `json:"b"`
	}
	if json.Unmarshal(packet, &event) != nil || event.Type != "xt" {
		return
	}
	g.world.mu.Lock()
	defer g.world.mu.Unlock()
	if g.world.token == token && g.world.generation == generation {
		command := event.Body.Object.Command
		notice := event.Body.Object
		if command == "msg__sendPublicMsg" && notice.MessageType == "alert" && notice.Text != "" {
			if len(g.world.notices) >= 64 {
				g.world.notices = g.world.notices[1:]
			}
			g.world.notices = append(g.world.notices, worldNotice{Text: notice.Text, Sender: notice.Sender})
		}
		if strings.HasPrefix(command, "buddyList__") {
			g.world.socialRevision++
		}
		if command == "shop__changed" {
			g.world.shopRevision++
		}
		if command == "minigame__open" && event.Body.Object.Key == "goldfishing" {
			g.world.minigameSerial++
			g.world.minigameKey = event.Body.Object.Key
		}
		if command == "shop__open" {
			g.world.shopSerial++
			g.world.shopKey = event.Body.Object.Key
		}
	}
}

func (g *Gateway) socketFailed(token string, generation uint64, err error) {
	message := "Соединение с игровым сервером прервано. Войдите снова."
	if websocket.IsCloseError(err, 4009) {
		message = "Этот могоби уже находится в игре. Сначала выйдите из игры на другом устройстве."
	}
	g.world.mu.Lock()
	defer g.world.mu.Unlock()
	if g.world.token == token && g.world.generation == generation {
		g.world.error = message
	}
}

func (g *Gateway) serveWorldSocket(w http.ResponseWriter, r *http.Request) {
	if r.Header.Get("Origin") != g.world.origin {
		log.Print("World connection rejected: foreign origin")
		http.Error(w, "Origin rejected", http.StatusForbidden)
		return
	}
	g.world.mu.Lock()
	token := g.world.token
	generation := g.world.generation
	g.world.mu.Unlock()
	if token == "" {
		log.Print("World connection rejected: no active session")
		http.Error(w, "Login required", http.StatusUnauthorized)
		return
	}
	target := *g.target
	if target.Scheme == "https" {
		target.Scheme = "wss"
	} else {
		target.Scheme = "ws"
	}
	target.Path += "/legacy/socket"
	target.RawPath, target.RawQuery = "", ""
	headers := http.Header{"Authorization": {"Bearer " + token}}
	dialer := websocket.Dialer{HandshakeTimeout: g.client.Timeout, Proxy: http.ProxyFromEnvironment}
	upstream, response, err := dialer.DialContext(r.Context(), target.String(), headers)
	if response != nil && response.Body != nil {
		defer response.Body.Close()
	}
	if err != nil {
		g.socketFailed(token, generation, err)
		log.Print("World connection failed: backend WebSocket handshake")
		http.Error(w, "World server unavailable", http.StatusBadGateway)
		return
	}
	defer upstream.Close()
	upgrader := websocket.Upgrader{CheckOrigin: func(r *http.Request) bool { return r.Header.Get("Origin") == g.world.origin }}
	downstream, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}
	defer downstream.Close()
	g.world.mu.Lock()
	if token != g.world.token || generation != g.world.generation {
		g.world.mu.Unlock()
		return
	}
	g.world.connections[downstream] = true
	g.world.mu.Unlock()
	defer func() { g.world.mu.Lock(); delete(g.world.connections, downstream); g.world.mu.Unlock() }()
	downstream.SetReadLimit(65536)
	upstream.SetReadLimit(65536)
	done := make(chan struct{}, 2)
	copyFrames := func(dst, src *websocket.Conn) {
		defer func() { done <- struct{}{} }()
		var observed []byte
		for {
			kind, reader, err := src.NextReader()
			if err != nil {
				if src == upstream {
					g.socketFailed(token, generation, err)
				}
				return
			}
			if kind != websocket.BinaryMessage && kind != websocket.TextMessage {
				return
			}
			if src == upstream {
				packet, readErr := io.ReadAll(reader)
				if readErr != nil {
					return
				}
				observed = append(observed, packet...)
				for {
					end := bytes.IndexByte(observed, 0)
					if end < 0 {
						break
					}
					g.observeChatPacket(token, generation, observed[:end])
					g.observeSocialPacket(token, generation, observed[:end])
					g.observeOutfitPacket(token, generation, observed[:end])
					observed = observed[end+1:]
				}
				// Match the protocol's 64 KiB limit even if a peer never
				// terminates a packet across multiple WebSocket messages.
				if len(observed) > 65536 {
					return
				}
				reader = bytes.NewReader(packet)
			}
			writer, err := dst.NextWriter(kind)
			if err != nil {
				return
			}
			_, err = io.Copy(writer, reader)
			closeErr := writer.Close()
			if err != nil || closeErr != nil {
				return
			}
		}
	}
	go copyFrames(upstream, downstream)
	go copyFrames(downstream, upstream)
	<-done
	downstream.Close()
	upstream.Close()
	<-done
}
