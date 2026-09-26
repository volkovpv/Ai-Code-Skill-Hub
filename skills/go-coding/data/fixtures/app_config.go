// Package config is a calibration fixture for the configuration layer: it is
// the one place environment variables are read, so GO-ENV is silent here when
// the checker sees this file's path — and fires when the same text arrives on
// stdin, which carries no path.
package config

import (
	"errors"
	"fmt"
	"os"
	"strconv"
	"time"
)

// Config is the process configuration, parsed once at startup.
type Config struct {
	DatabaseURL string
	HTTPAddr    string
	ReadTimeout time.Duration
}

// ErrMissing reports a required variable that is not set.
var ErrMissing = errors.New("config: required variable not set")

// Load reads and validates every variable, failing closed on the first gap.
func Load() (Config, error) {
	dbURL, ok := os.LookupEnv("DATABASE_URL")
	if !ok || dbURL == "" {
		return Config{}, fmt.Errorf("DATABASE_URL: %w", ErrMissing)
	}
	addr, ok := os.LookupEnv("HTTP_ADDR")
	if !ok || addr == "" {
		addr = ":8080"
	}
	timeout := 5 * time.Second
	if raw, ok := os.LookupEnv("READ_TIMEOUT_SECONDS"); ok {
		seconds, err := strconv.Atoi(raw)
		if err != nil || seconds <= 0 {
			return Config{}, fmt.Errorf("READ_TIMEOUT_SECONDS=%q: must be a positive integer", raw)
		}
		timeout = time.Duration(seconds) * time.Second
	}
	return Config{DatabaseURL: dbURL, HTTPAddr: addr, ReadTimeout: timeout}, nil
}
