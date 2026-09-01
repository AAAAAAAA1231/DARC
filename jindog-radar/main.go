package main

import (
	"embed"
	"encoding/json"
	"flag"
	"fmt"
	"io/fs"
	"log"
	"net"
	"net/http"
	"os"
	"os/exec"
	"runtime"
	"strings"
	"sync"
	"time"
)

//go:embed web/*
var webFS embed.FS

var (
	cacheMu    sync.Mutex
	cachedScan ScanResult
	cachedAt   time.Time
	cacheTTL   = 20 * time.Second
)

func main() {
	port := flag.Int("port", 17890, "本地端口")
	noBrowser := flag.Bool("no-browser", false, "不自动打开浏览器")
	flag.Parse()

	sub, err := fs.Sub(webFS, "web")
	if err != nil {
		log.Fatal(err)
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/api/pipeline", handlePipeline)
	mux.HandleFunc("/api/scan", handleScan)
	mux.HandleFunc("/api/deep", handleDeep)
	mux.Handle("/", http.FileServer(http.FS(sub)))

	addr := fmt.Sprintf("127.0.0.1:%d", *port)
	ln, err := net.Listen("tcp", addr)
	if err != nil {
		log.Fatalf("无法监听 %s: %v", addr, err)
	}
	url := "http://" + addr + "/"
	fmt.Println("========================================")
	fmt.Println("  金狗雷达  JinGouRadar")
	fmt.Println("  逻辑来源：加密狗 @jiamigou")
	fmt.Println("  https://x.com/jiamigou/status/2075057589457735949")
	fmt.Println("----------------------------------------")
	fmt.Println("  发现顺序：准备 → 双监控 → 年龄 → 叙事 → 数据 → 链上 → 聪明钱 → 小仓 → 止盈")
	fmt.Println("  本工具只做公开数据筛选，不保存私钥，不自动买入。")
	fmt.Println("  界面：", url)
	fmt.Println("  关闭本窗口即停止。")
	fmt.Println("========================================")

	if !*noBrowser {
		go func() {
			time.Sleep(400 * time.Millisecond)
			_ = openBrowser(url)
		}()
	}

	srv := &http.Server{
		Handler:           withCORS(mux),
		ReadHeaderTimeout: 8 * time.Second,
	}
	if err := srv.Serve(ln); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}

func withCORS(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-App", "JinGouRadar")
		next.ServeHTTP(w, r)
	})
}

func handlePipeline(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{
		"source":   Chain.SourceURL,
		"chain":    Chain,
		"pipeline": Pipeline,
		"note":     "看到新币后按顺序检查。99% 新链 Memecoin 会归零。活得久比抓到 100 倍更重要。",
	})
}

func handleScan(w http.ResponseWriter, r *http.Request) {
	force := r.URL.Query().Get("refresh") == "1"
	cacheMu.Lock()
	fresh := time.Since(cachedAt) < cacheTTL && cachedScan.Count > 0
	if fresh && !force {
		out := cachedScan
		cacheMu.Unlock()
		writeJSON(w, out)
		return
	}
	cacheMu.Unlock()

	res := ScanMarket(time.Now())
	cacheMu.Lock()
	cachedScan = res
	cachedAt = time.Now()
	cacheMu.Unlock()
	writeJSON(w, res)
}

func handleDeep(w http.ResponseWriter, r *http.Request) {
	ca := strings.TrimSpace(r.URL.Query().Get("ca"))
	if ca == "" {
		http.Error(w, "缺少 ca", http.StatusBadRequest)
		return
	}
	c, err := DeepCheck(ca, TokenSnapshot{}, time.Now())
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadGateway)
		return
	}
	writeJSON(w, c)
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	enc := json.NewEncoder(w)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(v)
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
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Start()
}
