from app.config_loader import load_repo_config
from app.cli_review import chunk_patches


def test_load_repo_config_reads_yaml(tmp_path):
    f = tmp_path / ".gpt-pr-bot.yml"
    f.write_text("max_files: 7\nseverity_gate: low\n")
    cfg = load_repo_config(str(tmp_path))
    assert cfg["max_files"] == 7
    assert cfg["severity_gate"] == "low"


def test_chunk_patches_splits():
    patches = [
        {"filename": "a.py", "patch": "+" * 50},
        {"filename": "b.py", "patch": "+" * 60},
        {"filename": "c.py", "patch": "+" * 70},
    ]
    batches = chunk_patches(patches, max_chars=100)
    assert len(batches) == 3
    for b in batches:
        assert sum(len(p["patch"]) for p in b) <= 100
