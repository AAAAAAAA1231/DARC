package main

import "testing"

func TestQuantileAndRegime(t *testing.T) {
	x := []float64{-0.02, -0.01, 0, 0.01, 0.03}
	if q := quantile(x, 0.5); q != 0 {
		t.Fatalf("median %v", q)
	}
	if classify(110, 105, 100, 0.04) != "上升" {
		t.Fatal("up")
	}
	if classify(90, 95, 100, -0.04) != "下降" {
		t.Fatal("down")
	}
}

func TestCodeBoards(t *testing.T) {
	if !codeBelongs("sse", "600519") || codeBelongs("sse", "300750") {
		t.Fatal("sse filter")
	}
	if !codeBelongs("chinext", "300308") {
		t.Fatal("cyb")
	}
}
