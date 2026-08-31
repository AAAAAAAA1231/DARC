package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"
)

const (
	browserUA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
	scannerUA = "GoldenDogRadar/1.0 (on-chain research scanner)"
)

var httpClient = &http.Client{Timeout: 18 * time.Second}

func getJSON(rawURL string, params url.Values, headers map[string]string, browser bool) (any, error) {
	if params != nil {
		u, err := url.Parse(rawURL)
		if err != nil {
			return nil, err
		}
		q := u.Query()
		for k, vs := range params {
			for _, v := range vs {
				q.Set(k, v)
			}
		}
		u.RawQuery = q.Encode()
		rawURL = u.String()
	}
	req, err := http.NewRequest(http.MethodGet, rawURL, nil)
	if err != nil {
		return nil, err
	}
	if browser {
		req.Header.Set("User-Agent", browserUA)
		req.Header.Set("Accept", "application/json,text/plain,*/*")
		req.Header.Set("Origin", "https://pump.fun")
		req.Header.Set("Referer", "https://pump.fun/")
	} else {
		req.Header.Set("User-Agent", scannerUA)
		req.Header.Set("Accept", "application/json")
	}
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	resp, err := httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("http %d", resp.StatusCode)
	}
	body, err := io.ReadAll(io.LimitReader(resp.Body, 8<<20))
	if err != nil {
		return nil, err
	}
	trim := strings.TrimSpace(string(body))
	if trim == "" {
		return nil, fmt.Errorf("empty")
	}
	var out any
	if err := json.Unmarshal(body, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func gather(limit int, fns []func() any) []any {
	sem := make(chan struct{}, limit)
	out := make([]any, len(fns))
	var wg sync.WaitGroup
	for i, fn := range fns {
		wg.Add(1)
		go func(i int, fn func() any) {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()
			defer func() { recover() }()
			out[i] = fn()
		}(i, fn)
	}
	wg.Wait()
	return out
}

func asMap(v any) map[string]any {
	m, _ := v.(map[string]any)
	return m
}

func asSlice(v any) []any {
	s, _ := v.([]any)
	return s
}

func num(v any) float64 {
	switch t := v.(type) {
	case float64:
		return t
	case float32:
		return float64(t)
	case int:
		return float64(t)
	case int64:
		return float64(t)
	case json.Number:
		f, _ := t.Float64()
		return f
	case string:
		var f float64
		fmt.Sscanf(t, "%f", &f)
		return f
	case bool:
		if t {
			return 1
		}
	}
	return 0
}

func str(v any) string {
	if v == nil {
		return ""
	}
	if s, ok := v.(string); ok {
		return s
	}
	return fmt.Sprint(v)
}

func truthy(v any) bool {
	switch t := v.(type) {
	case nil:
		return false
	case bool:
		return t
	case string:
		return t != ""
	case float64:
		return t != 0
	default:
		return v != nil
	}
}

func nested(m map[string]any, keys ...string) any {
	var cur any = m
	for _, k := range keys {
		mm := asMap(cur)
		if mm == nil {
			return nil
		}
		cur = mm[k]
	}
	return cur
}

func clip(s string, n int) string {
	r := []rune(s)
	if len(r) <= n {
		return s
	}
	return string(r[:n])
}
