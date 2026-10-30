"""Synthetic account over real PostgreSQL/ASGI for the read-only guide."""
from tests.browser_postgres_support import browser_application

app = browser_application("metis-explained")
app.state.operations_kernel.create_account(
    username="uitleg.reviewer", password="Synthetic-guide-only-936",
    roles=("reviewer",), display_name="Inhoudelijk beoordelaar",
)


@app.get("/browser-manifest")
def manifest():
    return {"username": "uitleg.reviewer", "password": "Synthetic-guide-only-936"}
