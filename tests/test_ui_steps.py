# tests/test_ui_steps.py
from frappe_cli.ui.steps import StepListRenderer, StepStatus


def test_initial_state_all_pending():
    r = StepListRenderer(["Step A", "Step B"])
    rendered = r.render()
    assert "○" in str(rendered)


def test_mark_running():
    r = StepListRenderer(["Step A"])
    r.mark_running("Step A")
    assert r._steps[0].status == StepStatus.RUNNING


def test_mark_done():
    r = StepListRenderer(["Step A"])
    r.mark_done("Step A")
    assert r._steps[0].status == StepStatus.DONE


def test_mark_skipped():
    r = StepListRenderer(["Step A"])
    r.mark_skipped("Step A")
    assert r._steps[0].status == StepStatus.SKIPPED


def test_mark_failed():
    r = StepListRenderer(["Step A"])
    r.mark_failed("Step A")
    assert r._steps[0].status == StepStatus.FAILED


def test_unknown_step_name_ignored():
    r = StepListRenderer(["Step A"])
    r.mark_done("Nonexistent")  # should not raise
    assert r._steps[0].status == StepStatus.PENDING
