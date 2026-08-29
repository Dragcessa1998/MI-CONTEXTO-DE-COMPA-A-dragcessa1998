from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_reproducible_parts_one_to_three_script(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "run_rfp_workflow_e2e.py"), "--workdir", str(tmp_path)],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    output = json.loads(result.stdout)

    assert output["states"] == ["intake_complete", "under_evaluation", "waiting_for_approval", "done"]
    assert output["departments"] == ["seleccion", "capacitacion"]
    assert output["approval_order"] == ["capacitacion", "seleccion"]
    assert output["all_approved"] is True
    assert len(set(output["thread_ids"])) == 2
    assert Path(output["final_document"]["file_path"]).is_file()
