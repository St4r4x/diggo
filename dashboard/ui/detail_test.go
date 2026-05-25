// dashboard/ui/detail_test.go
package ui_test

import (
	"strings"
	"testing"
	"time"

	"career-ops-fr/dashboard/model"
	"career-ops-fr/dashboard/ui"
)

func TestDetailView(t *testing.T) {
	t.Run("View returns non-empty string for new application", func(t *testing.T) {
		m := ui.NewDetailModel(model.Application{}, true)
		if out := m.View(); out == "" {
			t.Error("View() returned empty string for new application")
		}
	})

	t.Run("View returns non-empty string for existing application", func(t *testing.T) {
		app := model.Application{
			ID: 1, Company: "Mistral AI", Role: "ML Engineer",
			OfferURL: "https://mistral.ai/jobs/1",
			DetectionDate: time.Date(2026, 5, 25, 0, 0, 0, 0, time.UTC),
			ScoreGrade: "A", ScoreValue: 4.7, Status: "À envoyer", Notes: "Priority.",
		}
		if out := ui.NewDetailModel(app, false).View(); out == "" {
			t.Error("View() returned empty string for existing application")
		}
	})

	t.Run("View contains company name for existing application", func(t *testing.T) {
		app := model.Application{
			ID: 1, Company: "Mistral AI", Role: "ML Engineer",
			OfferURL: "https://mistral.ai/jobs/1",
			DetectionDate: time.Date(2026, 5, 25, 0, 0, 0, 0, time.UTC),
			ScoreGrade: "A", ScoreValue: 4.7, Status: "À envoyer",
		}
		out := ui.NewDetailModel(app, false).View()
		if !strings.Contains(out, "Mistral AI") {
			t.Errorf("View() does not contain 'Mistral AI':\n%s", out)
		}
	})

	t.Run("IsNew returns true for new application", func(t *testing.T) {
		if !ui.NewDetailModel(model.Application{}, true).IsNew() {
			t.Error("IsNew() = false, want true")
		}
	})

	t.Run("IsNew returns false for existing application", func(t *testing.T) {
		app := model.Application{ID: 1, Company: "Co", Role: "Role",
			OfferURL: "https://x.com", DetectionDate: time.Now(),
			ScoreGrade: "B", ScoreValue: 3.0, Status: "À envoyer"}
		if ui.NewDetailModel(app, false).IsNew() {
			t.Error("IsNew() = true, want false")
		}
	})

	t.Run("GetApplication returns correct company after construction", func(t *testing.T) {
		app := model.Application{
			ID: 5, Company: "Owkin", Role: "ML Scientist",
			OfferURL: "https://owkin.com/jobs/5",
			DetectionDate: time.Date(2026, 5, 20, 0, 0, 0, 0, time.UTC),
			ScoreGrade: "A", ScoreValue: 4.9, Status: "Entretien RH",
		}
		got := ui.NewDetailModel(app, false).GetApplication()
		if got.Company != "Owkin" {
			t.Errorf("GetApplication().Company = %q, want %q", got.Company, "Owkin")
		}
		if got.ID != 5 {
			t.Errorf("GetApplication().ID = %d, want 5", got.ID)
		}
	})
}
