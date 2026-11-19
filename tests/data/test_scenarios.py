"""Scenario Lab (Phase 8.3): synthetic changes stay in the training period, so every metric is
computed on the original SECOM test period."""

import pytest

from foresight.data.cleaning import CleaningConfig
from foresight.data.scenarios import KINDS, Scenario, check_test_period, generate
from foresight.data.secom import load_raw
from foresight.validation.contract import DatasetContract
from foresight.validation.gates import GateStatus


@pytest.fixture
def setup(secom_env):
    settings = secom_env
    raw = load_raw(settings.paths.data_raw_dir)
    contract = DatasetContract.load(settings.paths.contract_path)
    config = CleaningConfig(max_missing_ratio=settings.data.max_missing_ratio,
                            contract_features=contract.features.required,
                            contract_dropped=contract.dropped_columns)
    return raw, config, settings.analytics.test_fraction


@pytest.mark.parametrize("kind", list(KINDS))
def test_scenarios_change_only_the_training_period(setup, kind):
    raw, config, fraction = setup
    data, scenario, truth = generate(raw, Scenario(kind=kind, seed=3), config, fraction)
    assert check_test_period(raw, data, config, fraction).status == GateStatus.PASS
    test = data.run_id >= truth["training_runs_changed"]  # synthetic data is time-ordered
    changed = (data.drop(columns="timestamp").fillna(-1e9)
               != raw.drop(columns="timestamp").fillna(-1e9)).any(axis=1)
    assert changed[~test].any() and not changed[test].any()
    assert truth["synthetic"] and truth["test_runs_untouched"] == int(test.sum())
    if KINDS[kind][3]:
        assert len(scenario.sensors) == KINDS[kind][3] and "f_020" not in scenario.sensors
    again, _, _ = generate(raw, Scenario(kind=kind, seed=3), config, fraction)
    assert again.equals(data)  # reproducible from its recipe
    resumed, _, _ = generate(raw, scenario, config, fraction)  # the saved, resolved recipe
    assert resumed.equals(data)  # Continue regenerates exactly the same data


def test_a_planted_fault_shifts_only_failing_training_runs(setup):
    raw, config, fraction = setup
    data, scenario, _ = generate(raw, Scenario(kind="planted_fault", intensity=2.0), config,
                                 fraction)
    sensor = scenario.sensors[0]
    moved = (data[sensor] - raw[sensor]).fillna(0) != 0
    assert set(data.loc[moved, "label_raw"]) == {1}
    assert "planted fault on " + sensor in scenario.label()


def test_a_changed_test_period_stops_the_run(setup):
    raw, config, fraction = setup
    data, _, _ = generate(raw, Scenario(kind="noise"), config, fraction)
    data.loc[data.index[-1], "f_030"] += 1.0  # one value in the test period
    check = check_test_period(raw, data, config, fraction)
    assert check.status == GateStatus.ERROR and "only the training period" in check.message
