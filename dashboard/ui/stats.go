// dashboard/ui/stats.go
package ui

import (
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"career-ops-fr/dashboard/db"
	"career-ops-fr/dashboard/model"
)

var (
	statsHeadingStyle = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("212")).MarginBottom(1)
	statsLabelStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("243")).Width(30)
	statsValueStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("255")).Bold(true)
	statsStaleStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("214")).Bold(true)
	statsZeroStyle    = lipgloss.NewStyle().Foreground(lipgloss.Color("240"))
	statsRowStyle     = lipgloss.NewStyle().Foreground(lipgloss.Color("252"))
	statsRowAltStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("245"))
)

// StatsModel is the Bubble Tea model for the statistics view.
type StatsModel struct{ stats db.Stats }

// NewStatsModel constructs a StatsModel.
func NewStatsModel(stats db.Stats) StatsModel { return StatsModel{stats: stats} }

// Init satisfies tea.Model.
func (m StatsModel) Init() tea.Cmd { return nil }

// Update satisfies tea.Model (stats view is read-only).
func (m StatsModel) Update(msg tea.Msg) (StatsModel, tea.Cmd) { return m, nil }

// View renders the statistics summary.
func (m StatsModel) View() string {
	var sb strings.Builder
	sb.WriteString(statsHeadingStyle.Render("Pipeline Statistics") + "\n\n")

	metrics := []struct {
		label string
		value string
		stale bool
	}{
		{"Total applications", fmt.Sprintf("%d", m.stats.TotalApplications), false},
		{"Response rate", fmt.Sprintf("%.1f%%", m.stats.ResponseRate), false},
		{"Interviews obtained", fmt.Sprintf("%d", m.stats.InterviewCount), false},
		{"Stale follow-ups (>7d)", fmt.Sprintf("%d", m.stats.StaleCount), m.stats.StaleCount > 0},
	}
	for _, metric := range metrics {
		label := statsLabelStyle.Render(metric.label + ":")
		var val string
		if metric.stale {
			val = statsStaleStyle.Render(metric.value + "  !")
		} else {
			val = statsValueStyle.Render(metric.value)
		}
		sb.WriteString(fmt.Sprintf("  %s  %s\n", label, val))
	}
	sb.WriteString("\n")

	sb.WriteString(fmt.Sprintf("  %-22s  %s\n", "Status", "Count"))
	sb.WriteString(strings.Repeat("─", 32) + "\n")
	for i, status := range model.ValidStatuses {
		count := m.stats.ByStatus[status]
		countStr := fmt.Sprintf("%d", count)
		row := fmt.Sprintf("  %-22s  %s", status, countStr)
		if count == 0 {
			sb.WriteString(statsZeroStyle.Render(row) + "\n")
		} else if i%2 == 0 {
			sb.WriteString(statsRowStyle.Render(row) + "\n")
		} else {
			sb.WriteString(statsRowAltStyle.Render(row) + "\n")
		}
	}
	return sb.String()
}
