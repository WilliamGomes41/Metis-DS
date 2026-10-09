"""Disposable local UI proof. Synthetic sources/accounts and provider only."""
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import uvicorn
from tests.test_availability_repair import state, accounts, bind, provider, installed_app
folder=TemporaryDirectory()
console=state(Path(folder.name))
author,reviewer=accounts(console)
bind(console,provider)
app=installed_app(console)
uvicorn.run(app,host='127.0.0.1',port=8818,log_level='warning')
