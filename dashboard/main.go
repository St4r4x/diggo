package main

import (
	"fmt"
	"log"
	"os"
	"path/filepath"

	tea "github.com/charmbracelet/bubbletea"

	"career-ops-fr/dashboard/db"
	"career-ops-fr/dashboard/ui"
)

func main() {
	dbPath := filepath.Join("data", "applications.db")
	if err := os.MkdirAll(filepath.Dir(dbPath), 0755); err != nil {
		log.Fatalf("mkdir: %v", err)
	}
	database, err := db.Open(dbPath)
	if err != nil {
		log.Fatalf("db.Open: %v", err)
	}
	defer database.Close()

	if err := database.CreateTable(); err != nil {
		log.Fatalf("CreateTable: %v", err)
	}

	appModel, err := ui.NewAppModel(database)
	if err != nil {
		log.Fatalf("NewAppModel: %v", err)
	}

	p := tea.NewProgram(appModel, tea.WithAltScreen(), tea.WithMouseCellMotion())
	if _, err := p.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}
}
