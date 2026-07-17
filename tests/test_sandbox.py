from pathlib import Path

from reprove.execution import Runner


def test_deployment_docker_command_is_network_and_capability_restricted(tmp_path):
    command = Runner(tmp_path).docker_command("python:3.12", ["python", "-m", "pytest"])
    assert "--network" in command and command[command.index("--network") + 1] == "none"
    assert "--read-only" in command
    assert "--cap-drop" in command and command[command.index("--cap-drop") + 1] == "ALL"
    assert "no-new-privileges" in command
    assert f"{Path(tmp_path).resolve()}:/workspace:ro" in command
