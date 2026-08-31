package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"os/exec"
	"runtime"
	"sync"
	"time"

	"embed"
)

//go:embed web/index.html
var webFS embed.FS

var (
	scanMu     sync.Mutex
	lastResult *ScanResult
	shutOnce   sync.Once
)

func main() {
	log.SetFlags(log.LstdFlags)
	if len(os.Args) > 1 && os.Args[1] == "scan" {
		res, err := RunScan(context.Background(), func(msg string) { log.Println(msg) })
		if err != nil {
			fatal("%v", err)
		}
		enc := json.NewEncoder(os.Stdout)
		enc.SetEscapeHTML(false)
		enc.SetIndent("", "  ")
		_ = enc.Encode(res)
		return
	}

	listen := "127.0.0.1:0"
	if v := os.Getenv("HCW_ADDR"); v != "" {
		listen = v
	}
	ln, err := net.Listen("tcp", listen)
	if err != nil {
		fatal("无法监听本地端口: %v", err)
	}
	addr := ln.Addr().String()
	url := "http://" + addr + "/"

	mux := http.NewServeMux()
	mux.HandleFunc("/", handleIndex)
	mux.HandleFunc("/api/scan", handleScan)
	mux.HandleFunc("/api/scan-stream", handleScanStream)
	mux.HandleFunc("/api/last", handleLast)
	mux.HandleFunc("/api/shutdown", handleShutdown)
	mux.HandleFunc("/api/health", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintf(w, `{"ok":true,"version":"%s"}`, appVersion)
	})

	srv := &http.Server{Handler: withCORS(mux)}
	go func() {
		if err := srv.Serve(ln); err != nil && err != http.ErrServerClosed {
			log.Printf("server: %v", err)
		}
	}()

	log.Printf("%s %s  →  %s", appName, appVersion, url)
	if os.Getenv("HCW_NO_BROWSER") != "1" {
		if err := openBrowser(url); err != nil {
			log.Printf("自动打开浏览器失败，请手动访问: %s (%v)", url, err)
		}
	}

	// Keep process alive. UI 里的「退出」会调 /api/shutdown。
	select {}
}

func handleIndex(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	b, err := webFS.ReadFile("web/index.html")
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Write(b)
}

func handleScan(w http.ResponseWriter, r *http.Request) {
	res, err := doScan(r.Context(), nil)
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	writeJSON(w, res)
}

func handleScanStream(w http.ResponseWriter, r *http.Request) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		handleScan(w, r)
		return
	}
	w.Header().Set("Content-Type", "text/event-stream; charset=utf-8")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	emit := func(event string, v any) {
		b, _ := json.Marshal(v)
		fmt.Fprintf(w, "event: %s\ndata: %s\n\n", event, b)
		flusher.Flush()
	}
	emit("status", map[string]string{"msg": "开始扫描"})
	res, err := doScan(r.Context(), func(msg string) {
		emit("status", map[string]string{"msg": msg})
	})
	if err != nil {
		emit("error", map[string]string{"msg": err.Error()})
		return
	}
	emit("done", res)
}

func handleLast(w http.ResponseWriter, r *http.Request) {
	scanMu.Lock()
	res := lastResult
	scanMu.Unlock()
	if res == nil {
		res = loadCache()
	}
	if res == nil {
		http.Error(w, "no cache", 404)
		return
	}
	writeJSON(w, res)
}

func handleShutdown(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprint(w, `{"ok":true}`)
	go func() {
		time.Sleep(300 * time.Millisecond)
		shutOnce.Do(func() { os.Exit(0) })
	}()
}

func doScan(ctx context.Context, progress progressFn) (*ScanResult, error) {
	if !scanMu.TryLock() {
		scanMu.Lock()
		res := lastResult
		scanMu.Unlock()
		if res != nil {
			return res, nil
		}
		return nil, fmt.Errorf("扫描正在进行")
	}
	defer scanMu.Unlock()

	ctx, cancel := context.WithTimeout(ctx, 50*time.Second)
	defer cancel()
	res, err := RunScan(ctx, progress)
	if err != nil {
		return nil, err
	}
	lastResult = res
	return res, nil
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	enc := json.NewEncoder(w)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(v)
}

func withCORS(h http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		h.ServeHTTP(w, r)
	})
}

func openBrowser(url string) error {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
	case "darwin":
		cmd = exec.Command("open", url)
	default:
		cmd = exec.Command("xdg-open", url)
	}
	return cmd.Start()
}

func fatal(format string, args ...any) {
	msg := fmt.Sprintf(format, args...)
	log.Println(msg)
	if runtime.GOOS == "windows" {
		fmt.Fprintf(os.Stderr, "%s\n按任意键退出…\n", msg)
	}
	os.Exit(1)
}
