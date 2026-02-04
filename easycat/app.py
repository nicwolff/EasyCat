"""Main Textual application for EasyCat."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from easycat.config import Config, load_config
from easycat.db.repository import Repository
from easycat.screens.transactions import TransactionsScreen


class EasyCatApp(App):
    """Main application for QuickBooks transaction categorization."""

    TITLE = "EasyCat"
    SUB_TITLE = "QuickBooks Transaction Categorization"

    CSS = """
    Screen {
        background: $surface;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("?", "help", "Help", show=True),
    ]

    def __init__(self, config: Config | None = None):
        super().__init__()
        self._config = config or load_config()
        self._repository: Repository | None = None

    @property
    def config(self) -> Config:
        """Get application configuration."""
        return self._config

    @property
    def repository(self) -> Repository | None:
        """Get the database repository."""
        return self._repository

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Footer()

    async def on_mount(self) -> None:
        """Handle app mount event."""
        self._repository = Repository(self._config.database.path)
        await self._repository.connect()
        self.push_screen(TransactionsScreen())

    async def on_unmount(self) -> None:
        """Clean up resources when app closes."""
        if self._repository:
            await self._repository.close()

    def action_help(self) -> None:
        """Show help screen."""
        self.notify("Help: j/k to navigate, Enter to categorize, s to split, p to post")


def main() -> None:  # pragma: no cover
    """Entry point for the application."""
    app = EasyCatApp()
    app.run()


if __name__ == "__main__":  # pragma: no cover
    main()
