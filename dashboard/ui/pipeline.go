// dashboard/ui/pipeline.go
package ui

import (
	"fmt"
	"time"

	"github.com/charmbracelet/bubbles/key"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"career-ops-fr/dashboard/model"
)

var (
	pipelineColumnStyle = lipgloss.NewStyle().
				Border(lipgloss.RoundedBorder()).
				BorderForeground(lipgloss.Color("63")).
				Padding(0, 1).
				Width(22)

	pipelineColumnHeaderStyle = lipgloss.NewStyle().
					Bold(true).
					Foreground(lipgloss.Color("63")).
					MarginBottom(1)

	cardStyle = lipgloss.NewStyle().
			Border(lipgloss.NormalBorder()).
			BorderForeground(lipgloss.Color("240")).
			Padding(0, 1).
			MarginBottom(1).
			Width(18)

	cardSelectedStyle = lipgloss.NewStyle().
				Border(lipgloss.NormalBorder()).
				BorderForeground(lipgloss.Color("212")).
				Padding(0, 1).
				MarginBottom(1).
				Width(18)

	cardStaleStyle = lipgloss.NewStyle().
			Border(lipgloss.NormalBorder()).
			BorderForeground(lipgloss.Color("214")).
			Foreground(lipgloss.Color("214")).
			Padding(0, 1).
			MarginBottom(1).
			Width(18)

	gradeGoodStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("82"))
	gradeBadStyle    = lipgloss.NewStyle().Foreground(lipgloss.Color("226"))
	staleMarkerStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("214")).Bold(true)
)

type pipelineKeyMap struct {
	Left, Right, Up, Down, Select key.Binding
}

var pipelineKeys = pipelineKeyMap{
	Left:   key.NewBinding(key.WithKeys("left", "h")),
	Right:  key.NewBinding(key.WithKeys("right", "l")),
	Up:     key.NewBinding(key.WithKeys("up", "k")),
	Down:   key.NewBinding(key.WithKeys("down", "j")),
	Select: key.NewBinding(key.WithKeys("enter")),
}

// PipelineModel is the Bubble Tea model for the kanban pipeline view.
type PipelineModel struct {
	apps       []model.Application
	colIdx     int
	cardIdx    int
	selectedID int64
	width      int
	height     int
	now        time.Time
}

// NewPipelineModel constructs a PipelineModel.
func NewPipelineModel(apps []model.Application, width, height int) PipelineModel {
	return PipelineModel{apps: apps, width: width, height: height, now: time.Now()}
}

// SelectedAppID returns the ID of the selected application, or 0.
func (m PipelineModel) SelectedAppID() int64 { return m.selectedID }

func (m PipelineModel) appsForStatus(status string) []model.Application {
	var result []model.Application
	for _, app := range m.apps {
		if app.Status == status {
			result = append(result, app)
		}
	}
	return result
}

// Init satisfies tea.Model.
func (m PipelineModel) Init() tea.Cmd { return nil }

// Update handles keyboard navigation.
func (m PipelineModel) Update(msg tea.Msg) (PipelineModel, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.KeyMsg:
		switch {
		case key.Matches(msg, pipelineKeys.Left):
			if m.colIdx > 0 {
				m.colIdx--
				m.cardIdx = 0
				m.selectedID = 0
			}
		case key.Matches(msg, pipelineKeys.Right):
			if m.colIdx < len(model.ValidStatuses)-1 {
				m.colIdx++
				m.cardIdx = 0
				m.selectedID = 0
			}
		case key.Matches(msg, pipelineKeys.Up):
			if m.cardIdx > 0 {
				m.cardIdx--
			}
		case key.Matches(msg, pipelineKeys.Down):
			if m.cardIdx < len(m.appsForStatus(model.ValidStatuses[m.colIdx]))-1 {
				m.cardIdx++
			}
		case key.Matches(msg, pipelineKeys.Select):
			colApps := m.appsForStatus(model.ValidStatuses[m.colIdx])
			if m.cardIdx < len(colApps) {
				m.selectedID = colApps[m.cardIdx].ID
			}
		}
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
	}
	return m, nil
}

func (m PipelineModel) renderCard(app model.Application, selected bool) string {
	stale := app.IsStale(m.now)
	var gradeStr string
	if app.ScoreGrade == "A" || app.ScoreGrade == "B" {
		gradeStr = gradeGoodStyle.Render(fmt.Sprintf("%s %.1f", app.ScoreGrade, app.ScoreValue))
	} else {
		gradeStr = gradeBadStyle.Render(fmt.Sprintf("%s %.1f", app.ScoreGrade, app.ScoreValue))
	}
	staleStr := ""
	if stale {
		staleStr = staleMarkerStyle.Render(" !")
	}
	content := fmt.Sprintf("%s%s\n%s\n%s", app.Company, staleStr, app.Role, gradeStr)
	switch {
	case selected:
		return cardSelectedStyle.Render(content)
	case stale:
		return cardStaleStyle.Render(content)
	default:
		return cardStyle.Render(content)
	}
}

// View renders the kanban board.
func (m PipelineModel) View() string {
	colWidth := 22
	visibleCols := m.width / colWidth
	if visibleCols < 1 {
		visibleCols = 1
	}
	if visibleCols > len(model.ValidStatuses) {
		visibleCols = len(model.ValidStatuses)
	}
	startCol := m.colIdx - visibleCols/2
	if startCol < 0 {
		startCol = 0
	}
	if startCol+visibleCols > len(model.ValidStatuses) {
		startCol = len(model.ValidStatuses) - visibleCols
	}

	var columns []string
	for i := startCol; i < startCol+visibleCols; i++ {
		status := model.ValidStatuses[i]
		colApps := m.appsForStatus(status)
		header := pipelineColumnHeaderStyle.Render(fmt.Sprintf("%s (%d)", status, len(colApps)))
		colContent := header + "\n"
		for j, app := range colApps {
			colContent += m.renderCard(app, i == m.colIdx && j == m.cardIdx) + "\n"
		}
		style := pipelineColumnStyle
		if i == m.colIdx {
			style = pipelineColumnStyle.Copy().BorderForeground(lipgloss.Color("212"))
		}
		columns = append(columns, style.Render(colContent))
	}
	return lipgloss.JoinHorizontal(lipgloss.Top, columns...)
}
