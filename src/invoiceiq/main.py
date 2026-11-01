import uvicorn

from invoiceiq.api import create_app

app = create_app()


def main() -> None:
    uvicorn.run("invoiceiq.main:app", host="127.0.0.1", port=8000, reload=True)
