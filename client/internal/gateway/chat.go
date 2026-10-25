package gateway

import (
	"encoding/xml"
	"io"
	"strconv"
	"strings"
	"time"
)

type chatMessage struct {
	ReceivedAt int64  `json:"received_at"`
	ID         uint64 `json:"id"`
	Sender     string `json:"sender"`
	Text       string `json:"text"`
}

// Load the same original Russian ready-phrase catalogue that Main.swf uses.
func (g *Gateway) LoadChatPhrases(reader io.Reader) error {
	decoder := xml.NewDecoder(reader)
	phrases := make(map[string]string)
	for {
		token, err := decoder.Token()
		if err == io.EOF {
			break
		}
		if err != nil {
			return err
		}
		if start, ok := token.(xml.StartElement); ok {
			id, text := "", ""
			for _, attr := range start.Attr {
				if attr.Name.Local == "id" {
					id = attr.Value
				}
				if attr.Name.Local == "txt" {
					text = attr.Value
				}
			}
			if id != "" && text != "" {
				phrases[id] = text
			}
		}
	}
	g.chatPhrases = phrases
	return nil
}

// Observe only delivered speech, after server-side room and personal-mute
// filtering. Keep a bounded session history; neither credentials nor messages
// are written to disk. Repeated identical messages are separate entries.
func (g *Gateway) observeChatPacket(token string, generation uint64, packet []byte) {
	if len(packet) == 0 || packet[0] != '<' {
		return
	}
	type user struct {
		ID   int    `xml:"i,attr"`
		Name string `xml:"n"`
	}
	var event struct {
		Type string `xml:"t,attr"`
		Body struct {
			Action  string `xml:"action,attr"`
			Users   []user `xml:"uLs>u"`
			Enter   user   `xml:"u"`
			Speaker struct {
				ID int `xml:"id,attr"`
			} `xml:"user"`
			Text string `xml:"txt"`
		} `xml:"body"`
	}
	if xml.Unmarshal(packet, &event) != nil || event.Type != "sys" {
		return
	}
	g.world.mu.Lock()
	defer g.world.mu.Unlock()
	if token != g.world.token || generation != g.world.generation {
		return
	}
	b := event.Body
	switch b.Action {
	case "joinOK":
		g.world.chatUsers = make(map[int]string)
		for _, u := range b.Users {
			g.world.chatUsers[u.ID] = u.Name
		}
	case "uER":
		if g.world.chatUsers == nil {
			g.world.chatUsers = make(map[int]string)
		}
		g.world.chatUsers[b.Enter.ID] = b.Enter.Name
	case "userGone":
		delete(g.world.chatUsers, b.Speaker.ID)
	case "pubMsg":
		action, text, ok := strings.Cut(b.Text, "__")
		if action == "closeChat" {
			text = g.chatPhrases[text]
			action = "speak"
		}
		if !ok || (action != "speak" && action != "speakRoom" && action != "speakServer") || text == "" {
			return
		}
		name := g.world.chatUsers[b.Speaker.ID]
		if name == "" {
			return
		}
		g.world.chatSerial++
		g.world.chat = append(g.world.chat, chatMessage{ID: g.world.chatSerial, Sender: name, Text: text, ReceivedAt: time.Now().UnixMilli()})
		if len(g.world.chat) > 200 {
			g.world.chat = append([]chatMessage(nil), g.world.chat[len(g.world.chat)-200:]...)
		}
	}
}

func chatCursor(value string) uint64 {
	n, _ := strconv.ParseUint(value, 10, 64)
	return n
}
