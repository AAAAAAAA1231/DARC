//go:build windows

package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"syscall"
	"unsafe"
)

func startAppWindow(appURL string) (*exec.Cmd, error) {
	edge := findBrowser()
	if edge == "" {
		return nil, fmt.Errorf("未找到 Edge / Chrome")
	}
	profile := filepath.Join(os.TempDir(), "golden-dog-radar-profile")
	_ = os.MkdirAll(profile, 0755)
	cmd := exec.Command(edge,
		"--app="+appURL,
		"--window-size=1440,900",
		"--window-position=80,40",
		"--user-data-dir="+profile,
		"--no-first-run",
		"--disable-extensions",
	)
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: false}
	return cmd, cmd.Start()
}

func findBrowser() string {
	local := os.Getenv("LOCALAPPDATA")
	pf := os.Getenv("ProgramFiles")
	pfx86 := os.Getenv("ProgramFiles(x86)")
	candidates := []string{
		filepath.Join(local, `Microsoft\Edge\Application\msedge.exe`),
		filepath.Join(pf, `Microsoft\Edge\Application\msedge.exe`),
		filepath.Join(pfx86, `Microsoft\Edge\Application\msedge.exe`),
		filepath.Join(local, `Google\Chrome\Application\chrome.exe`),
		filepath.Join(pf, `Google\Chrome\Application\chrome.exe`),
		filepath.Join(pfx86, `Google\Chrome\Application\chrome.exe`),
	}
	for _, c := range candidates {
		if c == "" {
			continue
		}
		if st, err := os.Stat(c); err == nil && !st.IsDir() {
			return c
		}
	}
	if p, err := exec.LookPath("msedge"); err == nil {
		return p
	}
	if p, err := exec.LookPath("chrome"); err == nil {
		return p
	}
	return ""
}

func showError(msg string) {
	user32 := syscall.NewLazyDLL("user32.dll")
	proc := user32.NewProc("MessageBoxW")
	_, _, _ = proc.Call(0,
		uintptr(unsafe.Pointer(syscall.StringToUTF16Ptr(msg))),
		uintptr(unsafe.Pointer(syscall.StringToUTF16Ptr("金狗雷达"))),
		0x10)
}
