// dashboard/ui/stats_test.go
package ui_test

import (
	"strings"
	"testing"

	"career-ops-fr/dashboard/db"
	"career-ops-fr/dashboard/ui"
)

func TestStatsView(t *testing.T) {
	t.Run("View returns non-empty string with zero stats", func(t *testing.T) {
		s := db.Stats{ByStatus: make(map[string]int)}
		if out := ui.NewStatsModel(s).View(); out == "" {
			t.Error("View() returned empty string")
		}
	})

	t.Run("View contains total count", func(t *testing.T) {
		s := db.Stats{TotalApplications: 12, ResponseRate: 41.7, InterviewCount: 3, ByStatus: make(map[string]int)}
		if !strings.Contains(ui.NewStatsModel(s).View(), "12") {
			t.Error("View() does not contain '12'")
		}
	})

	t.Run("View contains response rate", func(t *testing.T) {
		s := db.Stats{TotalApplications: 10, ResponseRate: 50.0, InterviewCount: 2, ByStatus: make(map[string]int)}
		if !strings.Contains(ui.NewStatsModel(s).View(), "50") {
			t.Error("View() does not contain '50'")
		}
	})

	t.Run("View highlights stale count when greater than zero", func(t *testing.T) {
		s := db.Stats{TotalApplications: 5, ResponseRate: 20.0, StaleCount: 3, ByStatus: make(map[string]int)}
		if !strings.Contains(ui.NewStatsModel(s).View(), "3") {
			t.Error("View() does not contain stale count '3'")
		}
	})

	t.Run("View contains all status names in by-status table", func(t *testing.T) {
		byStatus := map[string]int{
			"À envoyer": 3, "Envoyée": 2, "Relance": 1, "Entretien RH": 1,
			"Entretien tech": 0, "Offre": 0, "Acceptée": 0, "Refusée": 0, "Abandonnée": 0,
		}
		s := db.Stats{TotalApplications: 7, ResponseRate: 28.5, InterviewCount: 1, ByStatus: byStatus}
		out := ui.NewStatsModel(s).View()
		for status := range byStatus {
			if !strings.Contains(out, status) {
				t.Errorf("View() does not contain status %q", status)
			}
		}
	})
}
