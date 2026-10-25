package gateway

import (
	"encoding/json"
	"fmt"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestChatHistoryDeliveredSpeechAndSessionIsolation(t *testing.T) {
	g := New("http://example.invalid", 0)
	g.setWorldSession("session")
	observe := func(packet string) { g.observeChatPacket("session", g.world.generation, []byte(packet)) }
	observe(`<msg t="sys"><body action="joinOK"><uLs><u i="1"><n>Мого</n></u><u i="2"><n>Друг</n></u></uLs></body></msg>`)
	speech := `<msg t="sys"><body action="pubMsg"><user id="2"/><txt>speak__&lt;b&gt; &amp; Привет!</txt></body></msg>`
	before := time.Now().UnixMilli()
	observe(speech)
	observe(speech)
	after := time.Now().UnixMilli()
	observe(`<msg t="sys"><body action="pubMsg"><user id="2"/><txt>emoticons__Ico_wink</txt></body></msg>`)
	g.observeChatPacket("other", g.world.generation, []byte(speech))
	g.observeChatPacket("session", g.world.generation-1, []byte(speech))
	if len(g.world.chat) != 2 || g.world.chat[0].Sender != "Друг" || g.world.chat[0].Text != "<b> & Привет!" || g.world.chat[1].ID != 2 {
		t.Fatalf("History: %+v", g.world.chat)
	}
	for _, row := range g.world.chat {
		if row.ReceivedAt < before || row.ReceivedAt > after {
			t.Fatalf("Invalid receive time: %+v", row)
		}
	}
	stamp := g.world.chat[1].ReceivedAt
	w := httptest.NewRecorder()
	g.ServeHTTP(w, httptest.NewRequest("GET", "http://local/client/world/status?chat_after=1", nil))
	var status struct {
		Chat []chatMessage `json:"chat"`
	}
	if json.Unmarshal(w.Body.Bytes(), &status) != nil || len(status.Chat) != 1 || status.Chat[0].ID != 2 || status.Chat[0].ReceivedAt != stamp {
		t.Fatalf("Cursor: %s", w.Body.String())
	}
	// A room snapshot changes speaker lookup without clearing the session log.
	observe(`<msg t="sys"><body action="joinOK"><uLs><u i="1"><n>Мого</n></u></uLs></body></msg>`)
	observe(speech)
	if len(g.world.chat) != 2 {
		t.Fatal("Unknown/previous-room speaker recorded")
	}
	observe(`<msg t="sys"><body action="uER"><u i="3"><n>Новый</n></u></body></msg>`)
	for i := 0; i < 205; i++ {
		observe(fmt.Sprintf(`<msg t="sys"><body action="pubMsg"><user id="3"/><txt>speak__%d</txt></body></msg>`, i))
	}
	if len(g.world.chat) != 200 || g.world.chat[0].Text != "5" || g.world.chat[199].Text != "204" {
		t.Fatal("History cap/order failed")
	}
	g.setWorldSession("session")
	if len(g.world.chat) != 200 {
		t.Fatal("Same-session reconnect erased history")
	}
	lastStamp := g.world.chat[199].ReceivedAt
	g.changeWorldSession("", true)
	g.setWorldSession("session")
	if len(g.world.chat) != 200 || g.world.chat[199].ReceivedAt != lastStamp {
		t.Fatal("F5 changed same-session history or receive times")
	}
	g.changeWorldSession("", true)
	g.setWorldSession("another")
	if len(g.world.chat) != 0 {
		t.Fatal("F5 history leaked to another account")
	}
	g.setWorldSession("")
	if len(g.world.chat) != 0 || g.world.chatSerial != 0 || len(g.world.chatUsers) != 0 {
		t.Fatal("Previous account's history survived exit")
	}
}

func TestChatHistoryReadyPhrases(t *testing.T) {
	g := New("http://example.invalid", 0)
	if err := g.LoadChatPhrases(strings.NewReader(`<Lang><chat><ms id="100"><m id="1010" txt="Привет!"/></ms></chat></Lang>`)); err != nil {
		t.Fatal(err)
	}
	g.setWorldSession("session")
	g.world.chatUsers = map[int]string{1: "Мого"}
	g.observeChatPacket("session", g.world.generation, []byte(`<msg t="sys"><body action="pubMsg"><user id="1"/><txt>closeChat__1010</txt></body></msg>`))
	if len(g.world.chat) != 1 || g.world.chat[0].Text != "Привет!" {
		t.Fatalf("Ready phrase: %+v", g.world.chat)
	}
}
