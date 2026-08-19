import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root

import pytest

from serving.conversations import ConversationOwnershipStore


@pytest.fixture
def store(tmp_path):
    return ConversationOwnershipStore(db_path=tmp_path / "conversations.db")


def test_first_use_claims_ownership(store):
    assert store.check_and_claim("conv_1", "client_a") is True


def test_owner_can_reuse_their_own_conversation_id(store):
    store.check_and_claim("conv_1", "client_a")
    assert store.check_and_claim("conv_1", "client_a") is True


def test_different_client_is_rejected(store):
    store.check_and_claim("conv_1", "client_a")
    assert store.check_and_claim("conv_1", "client_b") is False


def test_ownership_is_isolated_per_conversation_id(store):
    store.check_and_claim("conv_1", "client_a")
    assert store.check_and_claim("conv_2", "client_b") is True  # different id, no conflict
