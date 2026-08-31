//go:build windows

package main

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/jchv/go-webview2"
)

func runWebView2(appURL string) error {
	dataDir := filepath.Join(os.TempDir(), "golden-dog-radar-webview2")
	_ = os.MkdirAll(dataDir, 0755)
	w := webview2.NewWithOptions(webview2.WebViewOptions{
		AutoFocus: true,
		DataPath:  dataDir,
		WindowOptions: webview2.WindowOptions{
			Title:  "金狗雷达",
			Width:  1440,
			Height: 900,
			Center: true,
			IconId: 1,
		},
	})
	if w == nil {
		return fmt.Errorf("WebView2 窗口创建失败。请安装 Microsoft Edge WebView2 运行时后重试")
	}
	defer w.Destroy()
	w.SetSize(1440, 900, webview2.HintNone)
	w.Navigate(appURL)
	w.Run()
	return nil
}
