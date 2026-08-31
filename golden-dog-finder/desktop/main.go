package main

import (
	"encoding/json"
	"flag"
	"io"
	"io/fs"
	"log"
	"net"
	"net/http"
	"os"
	"strings"
	"time"
)

func main() {
	serverOnly := flag.Bool("server", false, "only serve HTTP, do not open a window")
	addr := flag.String("addr", "127.0.0.1:0", "listen address")
	flag.Parse()

	ln, err := net.Listen("tcp", *addr)
	if err != nil {
		fatal("无法监听端口: " + err.Error())
	}
	url := "http://" + ln.Addr().String() + "/"

	mux := http.NewServeMux()
	mux.HandleFunc("/api/health", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, map[string]any{"ok": true, "service": "golden-dog-radar"})
	})
	mux.HandleFunc("/api/thesis", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, thesis)
	})
	mux.HandleFunc("/api/scan", func(w http.ResponseWriter, r *http.Request) {
		force := r.URL.Query().Get("force") == "true"
		writeJSON(w, runScan(force))
	})

	uiRoot, err := fs.Sub(uiFS, "ui")
	if err != nil {
		fatal("界面资源缺失，请先运行 desktop/build.sh")
	}
	fileServer := http.FileServer(http.FS(uiRoot))
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/" || r.URL.Path == "/index.html" {
			serveIndex(w, uiRoot)
			return
		}
		if strings.HasPrefix(r.URL.Path, "/assets/") {
			fileServer.ServeHTTP(w, r)
			return
		}
		// SPA fallback
		if _, err := fs.Stat(uiRoot, strings.TrimPrefix(r.URL.Path, "/")); err != nil {
			serveIndex(w, uiRoot)
			return
		}
		fileServer.ServeHTTP(w, r)
	})

	srv := &http.Server{Handler: mux, ReadHeaderTimeout: 10 * time.Second}
	go func() {
		if err := srv.Serve(ln); err != nil && err != http.ErrServerClosed {
			log.Println(err)
		}
	}()

	if *serverOnly {
		log.Println("金狗雷达", url)
		select {}
	}

	cmd, err := startAppWindow(url)
	if err != nil {
		showError("无法打开桌面窗口，请安装 Microsoft Edge 或 Chrome。\n" + url + "\n" + err.Error())
		log.Println("无法打开桌面窗口，请手动访问:", url, err)
		select {}
	}
	_ = cmd.Wait()
	os.Exit(0)
}

func serveIndex(w http.ResponseWriter, uiRoot fs.FS) {
	f, err := uiRoot.Open("index.html")
	if err != nil {
		http.Error(w, "index.html missing", 500)
		return
	}
	defer f.Close()
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	io.Copy(w, f)
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	enc := json.NewEncoder(w)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(v)
}

func fatal(msg string) {
	showError(msg)
	log.Println(msg)
	time.Sleep(2 * time.Second)
	os.Exit(1)
}
