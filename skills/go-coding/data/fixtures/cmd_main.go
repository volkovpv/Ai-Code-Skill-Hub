// Command report is a calibration fixture for the main-package context: a
// program's entry point is where the root context is created and where the
// process exit code is decided, so GO-EXIT (for os.Exit) and GO-CTX-ROOT stay
// silent in package main. Output still goes through an injected writer —
// GO-PRINT applies here as everywhere.
package main

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"os/signal"
	"syscall"
)

var errUsage = errors.New("usage: report <file>")

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	err := run(ctx, os.Args[1:], os.Stdout)
	stop()
	if err != nil {
		fmt.Fprintln(os.Stderr, "report:", err)
		os.Exit(1)
	}
}

func run(ctx context.Context, args []string, out io.Writer) error {
	if len(args) == 0 {
		return errUsage
	}
	if _, err := fmt.Fprintln(out, "report:", args[0]); err != nil {
		return fmt.Errorf("write report: %w", err)
	}
	if err := ctx.Err(); err != nil {
		return fmt.Errorf("report interrupted: %w", err)
	}
	return nil
}
