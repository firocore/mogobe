package main

import (
	"crypto/sha256"
	"embed"
	"flag"
	"fmt"
	"io/fs"
	"net"
	"net/http"
	"os"
	"time"

	"github.com/firocore/mogobe/client/internal/accounts"
	"github.com/firocore/mogobe/client/internal/config"
	"github.com/firocore/mogobe/client/internal/gateway"
	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
	"github.com/wailsapp/wails/v2/pkg/options/windows"
)

//go:embed all:frontend
var web embed.FS

func main() {
	configPath := flag.String("config", config.DefaultPath(), "Path to client.json")
	serverURL := flag.String("server", "", "Override server_url from client.json")
	preview := flag.String("preview", "", "Serve the same client on loopback for diagnostics, e.g. 127.0.0.1:8091")
	flag.Parse()
	cfg, err := config.Load(*configPath, *serverURL)
	if err != nil {
		fatal("Не удалось прочитать настройки подключения. Проверьте client.json.", err)
	}
	assets, _ := fs.Sub(web, "frontend")
	proxy := gateway.New(cfg.ServerURL, time.Duration(cfg.RequestTimeoutSeconds)*time.Second)
	proxy.ItemAssets, _ = fs.Sub(assets, "items")
	phrases, err := assets.Open("Xmls/lang/chat_5.xml")
	if err != nil {
		fatal("Не удалось прочитать оригинальные фразы чата.", err)
	}
	if err = proxy.LoadChatPhrases(phrases); err != nil {
		fatal("Не удалось прочитать оригинальные фразы чата.", err)
	}
	phrases.Close()
	profileRoot, _ := os.UserCacheDir()
	if root := uiTestDataDir(); root != "" {
		profileRoot = root
	}
	profileKey := sha256.Sum256([]byte(cfg.ServerURL))
	profile, accountsPath, releaseProfile, err := reserveClientProfile(profileRoot, fmt.Sprintf("%x", profileKey[:8]))
	if err != nil {
		fatal("Не удалось открыть отдельный профиль окна клиента.", err)
	}
	defer releaseProfile()
	store, err := accounts.Open(accountsPath, cfg.ServerURL)
	if err != nil {
		fatal("Не удалось прочитать сохранённых могоби.", err)
	}
	proxy.Accounts = store
	proxy.CopyAvatarImage = copyAvatarImage
	closeSocket, err := proxy.StartWorldSocket(*preview)
	if err != nil {
		fatal("Не удалось создать локальное подключение к миру.", err)
	}
	defer closeSocket()
	if *preview != "" {
		host, _, err := net.SplitHostPort(*preview)
		if err != nil || (host != "127.0.0.1" && host != "localhost" && host != "::1") {
			fmt.Fprintln(os.Stderr, "Preview must bind to loopback")
			os.Exit(1)
		}
		server := &http.Server{Addr: *preview, Handler: proxy.Middleware(http.FileServer(http.FS(assets))), ReadHeaderTimeout: 5 * time.Second}
		fmt.Fprintln(os.Stdout, "Mogobe preview: http://"+*preview)
		if err := server.ListenAndServe(); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		return
	}
	opts := &options.App{
		Title: "Могоби", Width: 1000, Height: 720, MinWidth: 900, MinHeight: 640,
		BackgroundColour: &options.RGBA{R: 166, G: 205, B: 10, A: 255},
		AssetServer:      &assetserver.Options{Assets: assets, Middleware: proxy.Middleware},
		Windows:          &windows.Options{WebviewIsTransparent: false, WebviewUserDataPath: profile},
	}
	configureUITest(opts)
	err = wails.Run(opts)
	if err != nil {
		fatal("Не удалось запустить клиент.", err)
	}
}
