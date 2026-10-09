"""The production FastAPI app, with retrieval pointed at the offline snapshot KBs instead of Qdrant Cloud.

    python -m uvicorn eval.offline_app:app --port 8001

Everything else (floor, prompts, provider, output filters) is the real code, so end-to-end eval runs
exercise the production pipeline without any reads or writes on the live cluster.
"""
from __future__ import annotations

from eval.offline_kb import build_offline_clients
from serving import mode_config

_clients = build_offline_clients()
for _mode, _cfg in list(mode_config.MODE_CONFIG.items()):
    _client = _clients[_cfg.collection_alias]
    mode_config.MODE_CONFIG[_mode] = _cfg.model_copy(update={"get_client": (lambda c=_client: c)})

from serving.app import app  # noqa: E402  (must import after the config is patched)

__all__ = ["app"]
