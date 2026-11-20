"""Unit tests for Docker simulator (no Tk)."""
from __future__ import annotations

import pytest

from stamina.lounge.docker_sim import (
    DockerSimulator,
    ImageNotFound,
    ContainerNameInUse,
    PortAlreadyAllocated,
    NoSuchContainer,
    BuildError,
    ComposeError,
)


class TestDockerSimulator:
    """Tests for the pure Docker simulator."""

    def setup_method(self) -> None:
        self.sim = DockerSimulator()

    # ─── Built-in images ────────────────────────────────────────────────

    def test_builtin_images_exist(self) -> None:
        assert "ship/radio:latest" in self.sim.images
        assert "ship/orion:latest" in self.sim.images
        assert "ship/lab:latest" in self.sim.images
        assert "ship/scanner:latest" in self.sim.images
        assert "ship/base:latest" in self.sim.images

    def test_image_has_layers(self) -> None:
        img = self.sim.images["ship/radio:latest"]
        assert len(img.layers) >= 4
        assert img.size > 0

    # ─── docker run ────────────────────────────────────────────────────

    def test_run_detached_returns_container_id(self) -> None:
        out, code = self.sim.execute("docker run -d ship/radio")
        assert code == 0
        assert len(out.strip()) == 12  # container ID
        assert out.strip() in self.sim.containers

    def test_run_with_name(self) -> None:
        out, code = self.sim.execute("docker run -d --name myradio ship/radio")
        assert code == 0
        cid = out.strip()
        container = self.sim.containers[cid]
        assert container.name == "myradio"

    def test_run_duplicate_name_raises(self) -> None:
        self.sim.execute("docker run -d --name myradio ship/radio")
        out, code = self.sim.execute("docker run -d --name myradio ship/orion")
        assert code == 1
        assert "already in use" in out.lower()

    def test_run_port_mapping(self) -> None:
        out, code = self.sim.execute("docker run -d -p 8080:80 ship/radio")
        assert code == 0
        cid = out.strip()
        container = self.sim.containers[cid]
        assert len(container.ports) == 1
        assert container.ports[0].host_port == 8080
        assert container.ports[0].container_port == 80

    def test_run_port_conflict_raises(self) -> None:
        self.sim.execute("docker run -d -p 8080:80 ship/radio")
        out, code = self.sim.execute("docker run -d -p 8080:80 ship/orion")
        assert code == 1
        assert "port is already allocated" in out.lower()

    def test_run_with_volume(self) -> None:
        out, code = self.sim.execute("docker run -d -v mydata:/data ship/radio")
        assert code == 0
        cid = out.strip()
        container = self.sim.containers[cid]
        assert len(container.volumes) == 1
        assert container.volumes[0].target == "/data"
        assert container.volumes[0].type == "volume"

    def test_run_with_bind_mount(self) -> None:
        out, code = self.sim.execute("docker run -d -v /host/path:/container/path ship/radio")
        assert code == 0
        cid = out.strip()
        container = self.sim.containers[cid]
        assert container.volumes[0].type == "bind"
        assert container.volumes[0].source == "/host/path"

    def test_run_with_env(self) -> None:
        out, code = self.sim.execute("docker run -d -e KEY=value ship/radio")
        assert code == 0
        cid = out.strip()
        container = self.sim.containers[cid]
        assert container.env["KEY"] == "value"

    def test_run_unknown_image_raises(self) -> None:
        out, code = self.sim.execute("docker run -d unknown/image:latest")
        assert code == 1
        assert "image not found" in out.lower() or "pull access denied" in out.lower()

    def test_run_foreground_generates_logs(self) -> None:
        out, code = self.sim.execute("docker run ship/radio")
        assert code == 0
        assert "Starting module" in out
        assert "Module ready" in out

    # ─── docker ps ──────────────────────────────────────────────────────

    def test_ps_shows_running_only_by_default(self) -> None:
        self.sim.execute("docker run -d ship/radio")
        self.sim.execute("docker run -d ship/orion")
        out, code = self.sim.execute("docker ps")
        assert code == 0
        lines = out.strip().split("\n")
        assert len(lines) == 3  # header + 2 containers
        assert "ship/radio" in out
        assert "ship/orion" in out

    def test_ps_a_shows_all(self) -> None:
        cid, _ = self.sim.execute("docker run -d ship/radio")
        self.sim.execute(f"docker stop {cid.strip()}")
        out, code = self.sim.execute("docker ps -a")
        assert code == 0
        assert "Exited" in out or "stopped" in out.lower()

    # ─── docker logs ────────────────────────────────────────────────────

    def test_logs_shows_container_output(self) -> None:
        out, _ = self.sim.execute("docker run -d ship/radio")
        cid = out.strip()
        logs, code = self.sim.execute(f"docker logs {cid}")
        assert code == 0
        assert "Starting module" in logs
        assert "Module ready" in logs

    def test_logs_unknown_container_raises(self) -> None:
        out, code = self.sim.execute("docker logs nonexistent")
        assert code == 1
        assert "no such container" in out.lower()

    # ─── docker stop ────────────────────────────────────────────────────

    def test_stop_changes_status(self) -> None:
        out, _ = self.sim.execute("docker run -d ship/radio")
        cid = out.strip()
        self.sim.execute(f"docker stop {cid}")
        container = self.sim.containers[cid]
        assert container.status == "stopped"

    def test_stop_releases_ports(self) -> None:
        out, _ = self.sim.execute("docker run -d -p 8080:80 ship/radio")
        cid = out.strip()
        self.sim.execute(f"docker stop {cid}")
        # Should be able to reuse port
        out2, code = self.sim.execute("docker run -d -p 8080:80 ship/orion")
        assert code == 0

    # ─── docker rm ──────────────────────────────────────────────────────

    def test_rm_removes_stopped_container(self) -> None:
        out, _ = self.sim.execute("docker run -d ship/radio")
        cid = out.strip()
        self.sim.execute(f"docker stop {cid}")
        self.sim.execute(f"docker rm {cid}")
        assert cid not in self.sim.containers

    def test_rm_running_requires_force(self) -> None:
        out, _ = self.sim.execute("docker run -d ship/radio")
        cid = out.strip()
        out, code = self.sim.execute(f"docker rm {cid}")
        assert code == 1
        assert "running" in out.lower()

    def test_rm_f_force_removes_running(self) -> None:
        out, _ = self.sim.execute("docker run -d ship/radio")
        cid = out.strip()
        self.sim.execute(f"docker rm -f {cid}")
        assert cid not in self.sim.containers

    # ─── docker images ──────────────────────────────────────────────────

    def test_images_lists_builtin(self) -> None:
        out, code = self.sim.execute("docker images")
        assert code == 0
        assert "ship/radio" in out
        assert "ship/orion" in out

    # ─── docker port ────────────────────────────────────────────────────

    def test_port_shows_mappings(self) -> None:
        out, _ = self.sim.execute("docker run -d -p 8080:80 -p 9000:443 ship/radio")
        cid = out.strip()
        port_out, code = self.sim.execute(f"docker port {cid}")
        assert code == 0
        assert "80/tcp -> 0.0.0.0:8080" in port_out
        assert "443/tcp -> 0.0.0.0:9000" in port_out

    # ─── docker volume ──────────────────────────────────────────────────

    def test_volume_create_and_ls(self) -> None:
        out, code = self.sim.execute("docker volume create myvol")
        assert code == 0, f"volume create failed: {out}"
        assert "myvol" in out
        ls_out, code = self.sim.execute("docker volume ls")
        assert code == 0, f"volume ls failed: {ls_out}"
        assert "myvol" in ls_out

    def test_volume_rm(self) -> None:
        self.sim.execute("docker volume create myvol")
        self.sim.execute("docker volume rm myvol")
        ls_out, _ = self.sim.execute("docker volume ls")
        assert "myvol" not in ls_out

    # ─── docker network ─────────────────────────────────────────────────

    def test_network_create_and_ls(self) -> None:
        out, code = self.sim.execute("docker network create mynet")
        assert code == 0, f"network create failed: {out}"
        ls_out, code = self.sim.execute("docker network ls")
        assert code == 0, f"network ls failed: {ls_out}"
        assert "mynet" in ls_out

    # ─── docker build ───────────────────────────────────────────────────

    def test_build_requires_tag(self) -> None:
        out, code = self.sim.execute("docker build .")
        assert code == 1
        assert "requires a tag" in out.lower()

    def test_build_with_tag_succeeds(self) -> None:
        out, code = self.sim.execute("docker build -t myapp .")
        assert code == 0
        assert "Successfully tagged myapp" in out

    # ─── docker compose ─────────────────────────────────────────────────

    def test_compose_up_detached(self) -> None:
        out, code = self.sim.execute("docker compose up -d orion lab base")
        assert code == 0
        assert "orion" in out
        assert "lab" in out
        assert "base" in out
        # Check containers created with compose_ prefix
        compose_containers = [c for c in self.sim.containers.values() if c.name.startswith("compose_")]
        assert len(compose_containers) == 3

    def test_compose_down_removes_containers(self) -> None:
        self.sim.execute("docker compose up -d orion lab")
        self.sim.execute("docker compose down")
        compose_containers = [c for c in self.sim.containers.values() if c.name.startswith("compose_")]
        assert len(compose_containers) == 0

    def test_compose_ps_shows_services(self) -> None:
        self.sim.execute("docker compose up -d orion lab")
        out, code = self.sim.execute("docker compose ps")
        assert code == 0
        assert "orion" in out
        assert "lab" in out

    def test_compose_unknown_service_raises(self) -> None:
        out, code = self.sim.execute("docker compose up -d unknown_service")
        assert code == 1
        assert "not defined in compose file" in out.lower() or "unknown service" in out.lower()

    # ─── docker system prune ────────────────────────────────────────────

    def test_prune_removes_stopped_containers(self) -> None:
        out, _ = self.sim.execute("docker run -d ship/radio")
        cid = out.strip()
        self.sim.execute(f"docker stop {cid}")
        initial_count = len(self.sim.containers)
        out, code = self.sim.execute("docker system prune")
        assert code == 0, f"prune failed: {out}"
        assert len(self.sim.containers) < initial_count

    # ─── State serialization ────────────────────────────────────────────

    def test_serialize_deserialize(self) -> None:
        self.sim.execute("docker run -d --name test -p 8080:80 ship/radio")
        self.sim.execute("docker volume create myvol")
        self.sim.execute("docker network create mynet")

        data = self.sim.to_dict()
        sim2 = DockerSimulator.from_dict(data)

        assert len(sim2.containers) == 1
        assert "test" in [c.name for c in sim2.containers.values()]
        assert "myvol" in sim2.volumes
        assert "mynet" in sim2.networks
        assert 8080 in sim2._used_host_ports
        assert "mynet" in sim2.networks
        assert 8080 in sim2._used_host_ports

    # ─── Error messages realism ─────────────────────────────────────────

    def test_image_not_found_message(self) -> None:
        out, code = self.sim.execute("docker run -d nonexistent:latest")
        assert code == 1
        assert "pull access denied" in out.lower()
        assert "image not found" in out.lower()

    def test_port_allocated_message(self) -> None:
        self.sim.execute("docker run -d -p 8080:80 ship/radio")
        out, code = self.sim.execute("docker run -d -p 8080:80 ship/orion")
        assert code == 1
        assert "port is already allocated" in out.lower()

    def test_container_name_in_use_message(self) -> None:
        self.sim.execute("docker run -d --name myradio ship/radio")
        out, code = self.sim.execute("docker run -d --name myradio ship/orion")
        assert code == 1
        assert "already in use" in out.lower()


class TestRunParser:
    """Tests for the docker run argument parser."""

    def test_parse_detach(self) -> None:
        from stamina.lounge.docker_sim import _RunParser
        parser = _RunParser().parse(["-d", "ship/radio"])
        assert parser.detach is True
        assert parser.image == "ship/radio"

    def test_parse_name(self) -> None:
        from stamina.lounge.docker_sim import _RunParser
        parser = _RunParser().parse(["--name", "mycontainer", "ship/radio"])
        assert parser.name == "mycontainer"

    def test_parse_port(self) -> None:
        from stamina.lounge.docker_sim import _RunParser
        parser = _RunParser().parse(["-p", "8080:80", "ship/radio"])
        assert len(parser.ports) == 1
        assert parser.ports[0].host_port == 8080
        assert parser.ports[0].container_port == 80

    def test_parse_volume(self) -> None:
        from stamina.lounge.docker_sim import _RunParser
        parser = _RunParser().parse(["-v", "mydata:/data", "ship/radio"])
        assert len(parser.volumes) == 1
        assert parser.volumes[0].source == "mydata"
        assert parser.volumes[0].target == "/data"
        assert parser.volumes[0].type == "volume"

    def test_parse_bind_mount(self) -> None:
        from stamina.lounge.docker_sim import _RunParser
        parser = _RunParser().parse(["-v", "/host/path:/container/path", "ship/radio"])
        assert parser.volumes[0].type == "bind"
        assert parser.volumes[0].source == "/host/path"

    def test_parse_env(self) -> None:
        from stamina.lounge.docker_sim import _RunParser
        parser = _RunParser().parse(["-e", "KEY=value", "ship/radio"])
        assert parser.env["KEY"] == "value"

    def test_parse_command(self) -> None:
        from stamina.lounge.docker_sim import _RunParser
        parser = _RunParser().parse(["ship/radio", "python", "app.py"])
        assert parser.command == ["python", "app.py"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])