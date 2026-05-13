import pytest
from unittest.mock import patch
from tlm.safety.transaction import AtomicTransaction


@pytest.fixture
def temp_dir(tmp_path):
    d = tmp_path / "test_txn"
    d.mkdir()
    return d


def test_transaction_success(temp_dir):
    f1 = temp_dir / "a.txt"
    f2 = temp_dir / "subdir" / "b.txt"

    with AtomicTransaction(temp_dir) as txn:
        txn.stage(f1, "hello")
        txn.stage(f2, "world")
        written = txn.commit()
        assert len(written) == 2

    assert f1.read_text() == "hello"
    assert f2.read_text() == "world"


def test_transaction_rollback_on_failure(temp_dir):
    f1 = temp_dir / "exist.txt"
    f1.write_text("original")

    f2 = temp_dir / "fail.txt"

    # We'll mock os.replace to fail on the second item
    import os

    original_replace = os.replace

    call_count = 0

    def mock_replace(src, dst):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("simulated failure")
        return original_replace(src, dst)

    with patch("os.replace", side_effect=mock_replace):
        with AtomicTransaction(temp_dir) as txn:
            txn.stage(f1, "new content")
            txn.stage(f2, "will fail")
            with pytest.raises(RuntimeError):
                txn.commit()

    # f1 should be restored to original
    assert f1.read_text() == "original"
    # f2 should not exist
    assert not f2.exists()


def test_transaction_cleanup(temp_dir):
    with AtomicTransaction(temp_dir) as txn:
        txn.stage(temp_dir / "a.txt", "content")
        txn.commit()
        txn_dir = txn.tmp_dir

    assert not txn_dir.exists()
