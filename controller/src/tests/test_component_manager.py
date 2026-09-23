import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest
import types
import subprocess

from component_manager import ComponentManager
from globals import Globals


# -------------------------
# Fixtures & helpers
# -------------------------

@pytest.fixture
def mock_env(mocker):
    mocker.patch.dict(
        "os.environ",
        {
            "DOCKER_INFLUXDB_INIT_HOST": "localhost",
            "DOCKER_INFLUXDB_INIT_PORT": "8086",
            "DOCKER_INFLUXDB_INIT_ORG": "org",
            "DOCKER_INFLUXDB_INIT_ADMIN_TOKEN": "token",
            "DOCKER_SYSTEM_DIRECTORY": "/docker",
        },
    )


@pytest.fixture
def mock_influx(mocker):
    return mocker.patch("component_manager.InfluxDBClient")


@pytest.fixture
def mock_docker(mocker):
    docker_client = mocker.Mock()
    docker_client.images.list.return_value = []
    mocker.patch("component_manager.docker.from_env", return_value=docker_client)
    return docker_client


@pytest.fixture
def mock_worker_threads(mocker):
    # Fake worker_threads module loading
    mocker.patch("os.listdir", return_value=["worker_a.py"])
    mocker.patch("importlib.util.spec_from_file_location")
    mocker.patch("importlib.util.module_from_spec")

    fake_module = types.SimpleNamespace()

    class FakeWorker:
        def __init__(self, influx, docker, config):
            self.started = False
            self.stopped = False

        def start(self):
            self.started = True

        def stop(self):
            self.stopped = True

    fake_module.FakeComponent = FakeWorker
    fake_module.WorkerThread = FakeWorker

    mocker.patch(
        "importlib.util.module_from_spec",
        return_value=fake_module,
    )

    spec = mocker.Mock()
    spec.loader.exec_module = mocker.Mock()
    mocker.patch("importlib.util.spec_from_file_location", return_value=spec)


@pytest.fixture
def manager(mock_env, mock_influx, mock_docker, mock_worker_threads):
    return ComponentManager()


# -------------------------
# Influx configuration
# -------------------------

def test_configure_influx_external_success(mock_influx, mock_docker, mock_worker_threads):
    cm = ComponentManager(
        external_influx={
            "host": "h",
            "port": "p",
            "org": "o",
            "token": "t",
        }
    )
    assert cm.influxdb_client is not None


def test_configure_influx_external_missing_field_exits(mocker):
    mocker.patch("sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        ComponentManager(external_influx={"host": "h"})


# -------------------------
# build
# -------------------------

def test_build_missing_docker_image(manager, mocker):
    mocker.patch("sys.exit", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        manager.build({"component": "X"})


def test_build_enable_pull(manager, mock_docker):
    mock_docker.api.pull.return_value = iter([])

    manager.build(
        {
            "component": "cueltschey/rt-env-test",
            "docker_image": "img",
            "enable_pull": True,
        }
    )

    mock_docker.api.pull.assert_called_once_with("img", stream=True, decode=True)


# -------------------------
# build_if_not_exists
# -------------------------

def test_build_if_not_exists_skips(manager, mock_docker):
    image = mock_docker.images.list.return_value = [
        types.SimpleNamespace(tags=["img"])
    ]

    manager.build_if_not_exists(
        {
            "component": "cueltschey/rt-env-test",
            "docker_image": "img",
        }
    )


def test_build_if_not_exists_calls_build(manager, mocker):
    mocker.patch.object(manager, "build")

    manager.build_if_not_exists(
        {
            "component": "cueltschey/rt-env-test",
            "docker_image": "img",
        }
    )

    manager.build.assert_called_once()


# -------------------------
# start (internal)
# -------------------------

def test_start_missing_name(manager):
    manager.start({"component": "cueltschey/rt-env-test"})
    assert manager.process_metadata == []


def test_start_success(manager, mocker):
    mocker.patch("os.path.exists", return_value=True)

    manager.start(
        {
            "name": "proc1",
            "component": "cueltschey/rt-env-test",
        }
    )

    assert len(manager.process_metadata) == 1
    assert manager.process_metadata[0]["id"] == "proc1"


def test_start_invalid_component(manager):
    manager.start(
        {
            "name": "proc1",
            "component": "DoesNotExist",
        }
    )

    assert manager.process_metadata == []


# -------------------------
# start_external
# -------------------------

def test_start_external_success(manager, mocker):
    external = mocker.Mock()
    Globals.target_managers["tgt"] = external

    mocker.patch("os.path.exists", return_value=False)
    mocker.patch("os.walk", return_value=[("/host", [], ["cfg.conf"])])

    manager.start_external(
        {
            "name": "proc1",
            "component": "cueltschey/rt-env-test",
            "rf": 1,
            "target": "tgt",
        }
    )

    external.make_request.assert_called_once()
    assert len(manager.process_metadata) == 1


def test_start_external_missing_target(manager):
    manager.start_external(
        {
            "name": "proc1",
            "component": "cueltschey/rt-env-test",
            "rf": 1,
            "target": "missing",
        }
    )

    assert manager.process_metadata == []


# -------------------------
# stop
# -------------------------

def test_stop_internal_process(manager):
    handle = types.SimpleNamespace(stop=lambda: None)
    manager.stop({"handle": handle})


def test_stop_external_process(manager, mocker):
    external = mocker.Mock()
    Globals.target_managers["tgt"] = external

    manager.stop(
        {
            "id": "proc1",
            "target": "tgt",
        }
    )

    external.make_request.assert_called_once_with(
        "stop",
        payload={"id": "proc1"},
    )


# -------------------------
# _run_buildx_build
# -------------------------

def test_run_buildx_build_success(manager, mocker):
    process = mocker.Mock()
    process.stdout.readline.side_effect = ["", ""]
    process.stderr.readline.side_effect = ["", ""]
    process.wait.return_value = 0

    mocker.patch("subprocess.Popen", return_value=process)

    manager._run_buildx_build("img", "Dockerfile", "/ctx")


def test_run_buildx_build_failure(manager, mocker):
    process = mocker.Mock()
    process.stdout.readline.side_effect = ["", ""]
    process.stderr.readline.side_effect = ["", ""]
    process.wait.return_value = 1

    mocker.patch("subprocess.Popen", return_value=process)

    with pytest.raises(RuntimeError):
        manager._run_buildx_build("img", "Dockerfile", "/ctx")


# -------------------------
# Main entry
# -------------------------

if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__]))

