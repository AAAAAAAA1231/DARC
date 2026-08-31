//go:build !windows

package main

import (
	"log"
	"os"
	"os/exec"
	"runtime"
)

func runAppWindow(appURL string) error {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "darwin":
		cmd = exec.Command("open", appURL)
	default:
		if _, err := exec.LookPath("xdg-open"); err == nil {
			cmd = exec.Command("xdg-open", appURL)
		} else {
			log.Println("请在浏览器打开:", appURL)
			select {}
		}
	}
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Start(); err != nil {
		return err
	}
	log.Println("金狗雷达已启动:", appURL)
	select {}
}

func showError(msg string) {
	log.Println(msg)
}
