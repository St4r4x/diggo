// dashboard/ui/app.go
package ui

import (
	"fmt"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"career-ops-fr/dashboard/db"
	"career-ops-fr/dashboard/model"
)

type view int

const (
	viewPipeline view = iota
	viewDetail
	viewStats
)

var (
	tabBarStyle    = lipgloss.NewStyle().Padding(0, 1)
	activeTabStyle = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("212")).
			Border(lipgloss.NormalBorder(), false, false, true, false).
			BorderForeground(lipgloss.Color("212")).
			Padding(0, 2)
	inactiveTabStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("240")).
				Padding(0, 2)
	statusBarStyle      = lipgloss.NewStyle().Foreground(lipgloss.Color("252")).Padding(0, 1)
	statusBarErrorStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("196")).Bold(true).Padding(0, 1)
)

// AppModel is the root Bubble Tea model for the career-ops-fr dashboard.
type AppModel struct {
	database    *db.DB
	currentView view
	pipeline    PipelineModel
	detail      DetailModel
	stats       StatsModel
	width       int
	height      int
	statusMsg   string
	isError     bool
}

// NewAppModel constructs an AppModel, loading all applications and stats from the DB.
func NewAppModel(database *db.DB) (AppModel, error) {
	m := AppModel{
		database:    database,
		currentView: viewPipeline,
		width:       80,
		height:      24,
	}
	if err := m.reload(); err != nil {
		return AppModel{}, fmt.Errorf("NewAppModel: %w", err)
	}
	return m, nil
}

// reload fetches fresh data from the DB and rebuilds the pipeline and stats sub-models.
func (m *AppModel) reload() error {
	apps, err := m.database.GetAll()
	if err != nil {
		return fmt.Errorf("reload GetAll: %w", err)
	}
	stats, err := m.database.GetStats(time.Now())
	if err != nil {
		return fmt.Errorf("reload GetStats: %w", err)
	}
	m.pipeline = NewPipelineModel(apps, m.width, m.height-3) // reserve rows for tab bar + status bar
	m.stats = NewStatsModel(stats)
	return nil
}

// Init satisfies tea.Model.
func (m AppModel) Init() tea.Cmd {
	return m.pipeline.Init()
}

// Update handles top-level messages and delegates to sub-models.
func (m AppModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {

	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		var cmd tea.Cmd
		m.pipeline, cmd = m.pipeline.Update(msg)
		return m, cmd

	case SaveMsg:
		var saveErr error
		if msg.App.ID == 0 {
			_, saveErr = m.database.Insert(msg.App)
		} else {
			saveErr = m.database.Update(msg.App)
		}
		if saveErr != nil {
			m.statusMsg = fmt.Sprintf("Save error: %v", saveErr)
			m.isError = true
			return m, nil
		}
		if err := m.reload(); err != nil {
			m.statusMsg = fmt.Sprintf("Reload error: %v", err)
			m.isError = true
			return m, nil
		}
		if msg.App.ID == 0 {
			m.statusMsg = fmt.Sprintf("Application for %s created.", msg.App.Company)
		} else {
			m.statusMsg = fmt.Sprintf("Application for %s updated.", msg.App.Company)
		}
		m.isError = false
		m.currentView = viewPipeline
		return m, nil

	case CancelMsg:
		m.currentView = viewPipeline
		m.statusMsg = ""
		m.isError = false
		return m, nil

	case tea.KeyMsg:
		// Delegate all keypresses to the detail sub-model when in detail view.
		if m.currentView == viewDetail {
			var cmd tea.Cmd
			m.detail, cmd = m.detail.Update(msg)
			return m, cmd
		}

		// Top-level key bindings (pipeline / stats views).
		switch msg.String() {
		case "q", "ctrl+c":
			return m, tea.Quit

		case "tab":
			if m.currentView == viewPipeline {
				m.currentView = viewStats
			} else {
				m.currentView = viewPipeline
			}
			m.statusMsg = ""
			return m, nil

		case "shift+tab":
			if m.currentView == viewStats {
				m.currentView = viewPipeline
			} else {
				m.currentView = viewStats
			}
			m.statusMsg = ""
			return m, nil

		case "p":
			m.currentView = viewPipeline
			m.statusMsg = ""
			return m, nil

		case "s":
			m.currentView = viewStats
			m.statusMsg = ""
			return m, nil

		case "n":
			m.detail = NewDetailModel(model.Application{}, true)
			m.currentView = viewDetail
			m.statusMsg = ""
			return m, m.detail.Init()

		case "e":
			id := m.pipeline.SelectedAppID()
			if id == 0 {
				m.statusMsg = "No application selected. Use Enter to select one first."
				m.isError = true
				return m, nil
			}
			app, err := m.database.GetByID(id)
			if err != nil {
				m.statusMsg = fmt.Sprintf("Error loading application: %v", err)
				m.isError = true
				return m, nil
			}
			m.detail = NewDetailModel(app, false)
			m.currentView = viewDetail
			m.statusMsg = ""
			return m, m.detail.Init()

		case "d":
			id := m.pipeline.SelectedAppID()
			if id == 0 {
				m.statusMsg = "No application selected. Use Enter to select one first."
				m.isError = true
				return m, nil
			}
			if err := m.database.Delete(id); err != nil {
				m.statusMsg = fmt.Sprintf("Delete error: %v", err)
				m.isError = true
				return m, nil
			}
			if err := m.reload(); err != nil {
				m.statusMsg = fmt.Sprintf("Reload error: %v", err)
				m.isError = true
				return m, nil
			}
			m.statusMsg = "Application deleted."
			m.isError = false
			return m, nil
		}

		// Forward other keys to the active sub-model.
		if m.currentView == viewPipeline {
			var cmd tea.Cmd
			m.pipeline, cmd = m.pipeline.Update(msg)
			return m, cmd
		}
		if m.currentView == viewStats {
			var cmd tea.Cmd
			m.stats, cmd = m.stats.Update(msg)
			return m, cmd
		}

	default:
		// Forward unrecognised messages to sub-models.
		if m.currentView == viewDetail {
			var cmd tea.Cmd
			m.detail, cmd = m.detail.Update(msg)
			return m, cmd
		}
		if m.currentView == viewPipeline {
			var cmd tea.Cmd
			m.pipeline, cmd = m.pipeline.Update(msg)
			return m, cmd
		}
		if m.currentView == viewStats {
			var cmd tea.Cmd
			m.stats, cmd = m.stats.Update(msg)
			return m, cmd
		}
	}

	return m, nil
}

// View renders the full TUI layout: tab bar → content → status bar.
func (m AppModel) View() string {
	// --- Tab bar ---
	tabs := []struct {
		label string
		v     view
	}{
		{"Pipeline", viewPipeline},
		{"Stats", viewStats},
		{"Detail", viewDetail},
	}
	var tabParts []string
	for _, t := range tabs {
		if m.currentView == t.v {
			tabParts = append(tabParts, activeTabStyle.Render(t.label))
		} else {
			tabParts = append(tabParts, inactiveTabStyle.Render(t.label))
		}
	}
	tabBar := tabBarStyle.Render(strings.Join(tabParts, " "))

	// --- Content ---
	var content string
	switch m.currentView {
	case viewPipeline:
		content = m.pipeline.View()
	case viewDetail:
		content = m.detail.View()
	case viewStats:
		content = m.stats.View()
	}

	// --- Status bar ---
	var statusBar string
	if m.statusMsg != "" {
		if m.isError {
			statusBar = statusBarErrorStyle.Render(m.statusMsg)
		} else {
			statusBar = statusBarStyle.Render(m.statusMsg)
		}
	} else {
		hint := "[q] quit  [p] pipeline  [s] stats  [n] new  [e] edit  [d] delete"
		statusBar = statusBarStyle.Render(hint)
	}

	return lipgloss.JoinVertical(lipgloss.Left, tabBar, content, statusBar)
}
