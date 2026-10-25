//go:build uitest

// Test-only evaluation bridge. It is excluded from the distributed EXE.
// Wails' WebView2 loader intentionally strips CDP environment overrides.
package main

import (
	"context"
	"encoding/json"
	"net/http"
	"os"
	"strconv"
	"sync"
	"time"

	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/runtime"
)

func configureUITest(opts *options.App) {
	secret := os.Getenv("MOGOBE_UI_TEST_SECRET")
	if secret == "" {
		return
	}
	var ctx context.Context
	var lock sync.Mutex
	results := make(chan json.RawMessage, 1)
	previousStartup := opts.OnStartup
	opts.OnStartup = func(value context.Context) {
		ctx = value
		if previousStartup != nil {
			previousStartup(value)
		}
	}
	ready := make(chan struct{})
	var once sync.Once
	opts.OnDomReady = func(_ context.Context) { once.Do(func() { close(ready) }) }
	previous := opts.AssetServer.Middleware
	opts.AssetServer.Middleware = func(next http.Handler) http.Handler {
		handler := previous(next)
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if r.URL.Path == "/__test/result" {
				var result json.RawMessage
				if json.NewDecoder(r.Body).Decode(&result) == nil {
					select {
					case results <- result:
					default:
					}
				}
				w.WriteHeader(204)
				return
			}
			handler.ServeHTTP(w, r)
		})
	}
	mux := http.NewServeMux()
	mux.HandleFunc("/eval", func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer "+secret {
			http.Error(w, "Denied", 403)
			return
		}
		lock.Lock()
		defer lock.Unlock()
		select {
		case <-ready:
		case <-time.After(10 * time.Second):
			http.Error(w, "Not ready", 503)
			return
		}
		var request struct {
			Expression string `json:"expression"`
		}
		if json.NewDecoder(r.Body).Decode(&request) != nil {
			http.Error(w, "Bad request", 400)
			return
		}
		encoded, _ := json.Marshal(request.Expression)
		runtime.WindowExecJS(ctx, `(async()=>{let result;try{result={value:await (0,eval)(`+string(encoded)+`)}}catch(e){result={error:String(e)}}fetch('/__test/result',{method:'POST',body:JSON.stringify(result)});})()`)
		select {
		case result := <-results:
			w.Header().Set("Content-Type", "application/json")
			w.Write(result)
		case <-time.After(25 * time.Second):
			http.Error(w, "Evaluation timed out", 504)
		}
	})
	address := "127.0.0.1:19225"
	if port, err := strconv.Atoi(os.Getenv("MOGOBE_UI_TEST_PORT")); err == nil && port > 1024 && port <= 65535 {
		address = "127.0.0.1:" + strconv.Itoa(port)
	}
	server := &http.Server{Addr: address, Handler: mux, ReadHeaderTimeout: 5 * time.Second}
	go server.ListenAndServe()
	opts.OnShutdown = func(_ context.Context) { server.Close() }
}

func uiTestDataDir() string { return os.Getenv("MOGOBE_UI_TEST_PROFILE") }
