//go:build !windows

package main

import (
	"log"
	"os"
	"os/exec"
	"runtime"
)

func startAppWindow(appURL string) (*exec.Cmd, error) {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "darwin":
		cmd = exec.Command("open", appURL)
	default:
		if _, err := exec.LookPath("xdg-open"); err == nil {
			cmd = exec.Command("xdg-open", appURL)
		} else {
			cmd = exec.Command("sh", "-c", "echo "+appURL)
		}
	}
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd, cmd.Start()
}

func showError(msg string) {
	log.Println(msg)
}
