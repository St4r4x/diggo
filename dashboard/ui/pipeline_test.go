// dashboard/ui/pipeline_test.go
package ui_test

import (
	"strings"
	"testing"
	"time"

	"career-ops-fr/dashboard/model"
	"career-ops-fr/dashboard/ui"
)

func makeSampleApps() []model.Application {
	now := time.Date(2026, 5, 25, 0, 0, 0, 0, time.UTC)
	return []model.Application{
		{
			ID: 1, Company: "Mistral AI", Role: "ML Engineer",
			DetectionDate: now, ScoreGrade: "A", ScoreValue: 4.7, Status: "À envoyer",
		},
		{
			ID: 2, Company: "HuggingFace", Role: "NLP Engineer",
			DetectionDate: now, ScoreGrade: "B", ScoreValue: 4.1, Status: "Envoyée",
			SendDate: now.AddDate(0, 0, -10),
		},
		{
			ID: 3, Company: "Dataiku", Role: "Data Engineer",
			DetectionDate: now, ScoreGrade: "C", ScoreValue: 3.2, Status: "Entretien RH",
		},
	}
}

func TestPipelineView(t *testing.T) {
	t.Run("View returns non-empty string", func(t *testing.T) {
		m := ui.NewPipelineModel(makeSampleApps(), 80, 24)
		if out := m.View(); out == "" {
			t.Error("View() returned empty string")
		}
	})

	t.Run("View contains company names", func(t *testing.T) {
		m := ui.NewPipelineModel(makeSampleApps(), 120, 30)
		out := m.View()
		if !strings.Contains(out, "Mistral AI") {
			t.Error("View() does not contain 'Mistral AI'")
		}
		if !strings.Contains(out, "HuggingFace") {
			t.Error("View() does not contain 'HuggingFace'")
		}
	})

	t.Run("View contains all column headers", func(t *testing.T) {
		m := ui.NewPipelineModel(makeSampleApps(), 200, 30)
		out := m.View()
		for _, status := range model.ValidStatuses {
			if !strings.Contains(out, status) {
				t.Errorf("View() does not contain status column header %q", status)
			}
		}
	})

	t.Run("SelectedAppID returns zero when nothing selected", func(t *testing.T) {
		m := ui.NewPipelineModel(makeSampleApps(), 80, 24)
		if id := m.SelectedAppID(); id != 0 {
			t.Errorf("SelectedAppID() = %d, want 0", id)
		}
	})
}
