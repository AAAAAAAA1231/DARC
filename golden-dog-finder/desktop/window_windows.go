//go:build windows

package main

import (
	"syscall"
	"unsafe"
)

func runAppWindow(appURL string) error {
	return runWebView2(appURL)
}

func showError(msg string) {
	user32 := syscall.NewLazyDLL("user32.dll")
	proc := user32.NewProc("MessageBoxW")
	_, _, _ = proc.Call(0,
		uintptr(unsafe.Pointer(syscall.StringToUTF16Ptr(msg))),
		uintptr(unsafe.Pointer(syscall.StringToUTF16Ptr("金狗雷达"))),
		0x10)
}
