"""Docker Simulator — pure Python, no Tk.

Simulates Docker CLI: images, containers, ports, volumes, networks, logs,
build cache layers, and virtual disk. Realistic errors included.
"""
from __future__ import annotations

import re
import shlex
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DockerError(Exception):
    """Base Docker error with realistic message."""
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ImageNotFound(DockerError):
    pass


class ContainerNameInUse(DockerError):
    pass


class PortAlreadyAllocated(DockerError):
    pass


class NoSuchContainer(DockerError):
    pass


class ContainerNotRunning(DockerError):
    pass


class InvalidReferenceFormat(DockerError):
    pass


class NetworkNotFound(DockerError):
    pass


class VolumeNotFound(DockerError):
    pass


class BuildError(DockerError):
    pass


class ComposeError(DockerError):
    pass


@dataclass
class ImageLayer:
    """Single layer in image cache."""
    id: str
    instruction: str
    size: int
    cached: bool = True


@dataclass
class Image:
    """Docker image with layers."""
    name: str
    tag: str = "latest"
    layers: list[ImageLayer] = field(default_factory=list)
    size: int = 0
    created: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.name}:{self.tag}"


@dataclass
class PortBinding:
    """Port mapping host:container."""
    host_port: int
    container_port: int
    protocol: str = "tcp"


@dataclass
class VolumeMount:
    """Volume or bind mount."""
    source: str
    target: str
    read_only: bool = False
    type: str = "volume"  # volume, bind, tmpfs


@dataclass
class Container:
    """Docker container state."""
    id: str
    name: str
    image: Image
    command: list[str] = field(default_factory=list)
    status: str = "created"  # created, running, paused, stopped, dead
    ports: list[PortBinding] = field(default_factory=list)
    volumes: list[VolumeMount] = field(default_factory=list)
    networks: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)
    exit_code: int = 0
    created_at: str = ""
    started_at: str = ""
    finished_at: str = ""

    def add_log(self, line: str) -> None:
        self.logs.append(line)


@dataclass
class Network:
    """Docker network."""
    name: str
    driver: str = "bridge"
    containers: list[str] = field(default_factory=list)  # container ids
    subnet: str = ""
    gateway: str = ""


@dataclass
class Volume:
    """Docker volume."""
    name: str
    driver: str = "local"
    mountpoint: str = ""
    labels: dict[str, str] = field(default_factory=dict)


class DockerSimulator:
    """Pure Docker simulator with realistic behavior."""

    # Predefined ship module images
    SHIP_IMAGES = {
        "radio": "ship/radio:latest",
        "orion": "ship/orion:latest",
        "lab": "ship/lab:latest",
        "scanner": "ship/scanner:latest",
        "base": "ship/base:latest",
    }

    def __init__(self) -> None:
        self.images: dict[str, Image] = {}  # key: name:tag
        self.containers: dict[str, Container] = {}  # key: container id
        self.networks: dict[str, Network] = {}
        self.volumes: dict[str, Volume] = {}
        self._used_host_ports: set[int] = set()
        self._disk_usage: int = 0  # bytes
        self._layer_cache: dict[str, ImageLayer] = {}  # instruction hash -> layer
        self._init_builtin_images()

    def _init_builtin_images(self) -> None:
        """Initialize built-in ship module images."""
        for name, full_name in self.SHIP_IMAGES.items():
            img_name, tag = full_name.split(":")
            img = Image(name=img_name, tag=tag)
            # Add base layers
            img.layers = [
                ImageLayer(id=self._layer_id("FROM scratch"), instruction="FROM scratch", size=0),
                ImageLayer(id=self._layer_id(f"COPY {name} /app"), instruction=f"COPY {name} /app", size=1024 * 1024),
                ImageLayer(id=self._layer_id(f"EXPOSE {self._default_port(name)}"), instruction=f"EXPOSE {self._default_port(name)}", size=0),
                ImageLayer(id=self._layer_id(f"CMD [\"./{name}\"]"), instruction=f'CMD ["./{name}"]', size=512 * 1024),
            ]
            img.size = sum(l.size for l in img.layers)
            self.images[img.full_name] = img

    def _default_port(self, name: str) -> int:
        ports = {"radio": 8080, "orion": 9000, "lab": 8888, "scanner": 7777, "base": 5432}
        return ports.get(name, 80)

    def _layer_id(self, instruction: str) -> str:
        """Generate deterministic layer ID from instruction."""
        return "sha256:" + str(hash(instruction))[2:14]

    def _container_id(self) -> str:
        return str(uuid.uuid4())[:12]

    def _parse_image_ref(self, ref: str) -> tuple[str, str]:
        """Parse image reference into (name, tag)."""
        if ":" in ref and not ref.startswith("sha256:"):
            parts = ref.rsplit(":", 1)
            if "/" in parts[1] or "." in parts[1]:
                # It's a hostname:port, not a tag
                return ref, "latest"
            return parts[0], parts[1]
        return ref, "latest"

    def _get_image(self, ref: str) -> Image:
        name, tag = self._parse_image_ref(ref)
        key = f"{name}:{tag}"
        if key not in self.images:
            raise ImageNotFound(f"pull access denied for {ref}, repository does not exist or may require 'docker login': image not found")
        return self.images[key]

    def _find_container(self, name_or_id: str) -> Container | None:
        """Find container by name or ID prefix."""
        # Exact ID match
        if name_or_id in self.containers:
            return self.containers[name_or_id]
        # Exact name match
        for c in self.containers.values():
            if c.name == name_or_id:
                return c
        # ID prefix match
        for cid, c in self.containers.items():
            if cid.startswith(name_or_id):
                return c
        return None

    # ─── Commands ────────────────────────────────────────────────────────

    def cmd_run(self, args: list[str]) -> tuple[str, int]:
        """docker run [OPTIONS] IMAGE [COMMAND] [ARG...]"""
        parser = _RunParser()
        parsed = parser.parse(args)

        image = self._get_image(parsed.image)

        # Check name conflict
        if parsed.name:
            for c in self.containers.values():
                if c.name == parsed.name:
                    raise ContainerNameInUse(f"Conflict. The container name \"{parsed.name}\" is already in use by container \"{c.id}\". You have to remove (or rename) that container to be able to reuse that name.")

        # Check port conflicts
        for pb in parsed.ports:
            if pb.host_port in self._used_host_ports:
                raise PortAlreadyAllocated(f"driver failed programming external connectivity on endpoint {parsed.name or 'container'}: Bind for 0.0.0.0:{pb.host_port} failed: port is already allocated")

        # Create container
        cid = self._container_id()
        container = Container(
            id=cid,
            name=parsed.name or f"ship_{cid[:8]}",
            image=image,
            command=parsed.command,
            ports=parsed.ports,
            volumes=parsed.volumes,
            env=parsed.env,
            labels=parsed.labels,
        )

        # Reserve ports
        for pb in parsed.ports:
            self._used_host_ports.add(pb.host_port)

        # Default network
        if "bridge" not in self.networks:
            self.networks["bridge"] = Network(name="bridge", driver="bridge", subnet="172.17.0.0/16", gateway="172.17.0.1")
        container.networks.append("bridge")
        self.networks["bridge"].containers.append(cid)

        self.containers[cid] = container

        if parsed.detach:
            # Start immediately in background - set status to running and generate logs
            container.status = "running"
            container.started_at = "2026-11-20T10:00:00Z"
            logs = self._generate_startup_logs(container)
            for log in logs:
                container.add_log(log)
            return cid + "\n", 0
        else:
            # Foreground - simulate running and capturing logs
            return self._run_foreground(cid)

    def _run_foreground(self, cid: str) -> tuple[str, int]:
        """Run container in foreground mode."""
        container = self.containers[cid]
        container.status = "running"
        container.started_at = "2026-11-20T10:00:00Z"

        # Simulate startup logs
        logs = self._generate_startup_logs(container)
        for log in logs:
            container.add_log(log)

        output = "\n".join(logs)
        container.status = "stopped"
        container.finished_at = "2026-11-20T10:00:05Z"
        container.exit_code = 0
        return output, 0

    def _generate_startup_logs(self, container: Container) -> list[str]:
        """Generate realistic startup logs for ship modules."""
        name = container.image.name
        logs = [
            f"[{name}] Starting module...",
            f"[{name}] Loading configuration...",
            f"[{name}] Initializing systems...",
        ]

        # Module-specific logs
        if name == "radio":
            logs.extend([
                "[radio] Scanning frequencies...",
                "[radio] Found: Jazz, Swing, BBC World Service",
                "[radio] Receiver online at port 8080",
            ])
        elif name == "orion":
            logs.extend([
                "[orion] Neural core initializing...",
                "[orion] Loading agent manifests...",
                "[orion] Agent 'Orion' ready on port 9000",
            ])
        elif name == "lab":
            logs.extend([
                "[lab] Knowledge constellation loading...",
                "[lab] Entities: 1247, Connections: 8923",
                "[lab] Visualization ready on port 8888",
            ])
        elif name == "scanner":
            logs.extend([
                "[scanner] Calibrating sensors...",
                "[scanner] Frequency sweep complete",
                "[scanner] Active on port 7777",
            ])
        elif name == "base":
            logs.extend([
                "[base] Pilot database connecting...",
                "[base] Migrations up to date",
                "[base] PostgreSQL ready on port 5432",
            ])

        logs.append(f"[{name}] Module ready ✓")
        return logs

    def cmd_ps(self, args: list[str]) -> tuple[str, int]:
        """docker ps [OPTIONS]"""
        show_all = "-a" in args or "--all" in args
        containers = list(self.containers.values())
        if not show_all:
            containers = [c for c in containers if c.status == "running"]

        if not containers:
            return "CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES\n", 0

        lines = ["CONTAINER ID   IMAGE                COMMAND                  CREATED         STATUS         PORTS                    NAMES"]
        for c in containers:
            ports_str = ", ".join(f"0.0.0.0:{pb.host_port}->{pb.container_port}/{pb.protocol}" for pb in c.ports) or "—"
            cmd_str = " ".join(c.command) if c.command else (c.image.layers[-1].instruction if c.image.layers else "—")
            if len(cmd_str) > 40:
                cmd_str = cmd_str[:37] + "..."
            status = c.status
            if c.status == "stopped":
                status = f"Exited ({c.exit_code})"
            lines.append(f"{c.id}   {c.image.full_name:<20} {cmd_str:<24} 5 min ago      {status:<14} {ports_str:<22} {c.name}")

        return "\n".join(lines) + "\n", 0

    def cmd_logs(self, args: list[str]) -> tuple[str, int]:
        """docker logs [OPTIONS] CONTAINER"""
        if not args:
            return "", 1
        name_or_id = args[0]
        container = self._find_container(name_or_id)
        if not container:
            raise NoSuchContainer(f"No such container: {name_or_id}")
        return "\n".join(container.logs) + "\n", 0

    def cmd_stop(self, args: list[str]) -> tuple[str, int]:
        """docker stop [OPTIONS] CONTAINER [CONTAINER...]"""
        if not args:
            return "", 1
        for name_or_id in args:
            container = self._find_container(name_or_id)
            if not container:
                raise NoSuchContainer(f"No such container: {name_or_id}")
            if container.status == "running":
                container.status = "stopped"
                container.finished_at = "2026-11-20T10:05:00Z"
                container.exit_code = 0
                # Release ports
                for pb in container.ports:
                    self._used_host_ports.discard(pb.host_port)
        return "\n".join(args) + "\n", 0

    def cmd_rm(self, args: list[str]) -> tuple[str, int]:
        """docker rm [OPTIONS] CONTAINER [CONTAINER...]"""
        force = "-f" in args or "--force" in args
        targets = [a for a in args if not a.startswith("-")]
        if not targets:
            return "", 1

        for name_or_id in targets:
            container = self._find_container(name_or_id)
            if not container:
                raise NoSuchContainer(f"No such container: {name_or_id}")
            if container.status == "running" and not force:
                raise DockerError(f"You cannot remove a running container {container.id}. Stop the container before removing or use -f")
            # Release ports
            for pb in container.ports:
                self._used_host_ports.discard(pb.host_port)
            # Remove from network
            for net in self.networks.values():
                if container.id in net.containers:
                    net.containers.remove(container.id)
            del self.containers[container.id]
        return "\n".join(targets) + "\n", 0

    def cmd_images(self, args: list[str]) -> tuple[str, int]:
        """docker images [OPTIONS] [REPOSITORY[:TAG]]"""
        lines = ["REPOSITORY          TAG       IMAGE ID       CREATED       SIZE"]
        for img in self.images.values():
            size_mb = img.size / (1024 * 1024)
            lines.append(f"{img.name:<18} {img.tag:<9} {img.layers[0].id if img.layers else 'sha256:0':<14} 5 min ago      {size_mb:.1f}MB")
        return "\n".join(lines) + "\n", 0

    def cmd_pull(self, args: list[str]) -> tuple[str, int]:
        """docker pull [OPTIONS] NAME[:TAG]"""
        if not args:
            return "", 1
        ref = args[0]
        name, tag = self._parse_image_ref(ref)
        key = f"{name}:{tag}"
        if key in self.images:
            return f"Status: Image is up to date for {ref}\n", 0
        # Simulate pulling
        return f"Pulling from {name}\nDigest: sha256:abcdef123456\nStatus: Downloaded newer image for {ref}\n", 0

    def cmd_build(self, args: list[str]) -> tuple[str, int]:
        """docker build [OPTIONS] PATH | URL | -"""
        # Simplified: parse -t tag and Dockerfile content from stdin or context
        tag = None
        i = 0
        while i < len(args):
            if args[i] == "-t" and i + 1 < len(args):
                tag = args[i + 1]
                i += 2
            else:
                i += 1
        if not tag:
            raise BuildError("requires a tag with -t")

        # Simulate build with cache
        lines = [
            "Sending build context to Docker daemon  2.56kB",
            "Step 1/4 : FROM ship/base",
            " ---> " + self._layer_id("FROM ship/base"),
            "Step 2/4 : COPY app.py /app",
            " ---> Using cache",
            " ---> " + self._layer_id("COPY app.py /app"),
            "Step 3/4 : EXPOSE 8080",
            " ---> Using cache",
            " ---> " + self._layer_id("EXPOSE 8080"),
            "Step 4/4 : CMD [\"python\", \"app.py\"]",
            " ---> Running in abcdef123456",
            " ---> " + self._layer_id("CMD [\"python\", \"app.py\"]"),
            f"Successfully built {self._layer_id('final')[:12]}",
            f"Successfully tagged {tag}",
        ]
        return "\n".join(lines) + "\n", 0

    def cmd_port(self, args: list[str]) -> tuple[str, int]:
        """docker port CONTAINER [PRIVATE_PORT[/PROTO]]"""
        if not args:
            return "", 1
        container = self._find_container(args[0])
        if not container:
            raise NoSuchContainer(f"No such container: {args[0]}")
        if not container.ports:
            return "", 0
        lines = []
        for pb in container.ports:
            lines.append(f"{pb.container_port}/{pb.protocol} -> 0.0.0.0:{pb.host_port}")
        return "\n".join(lines) + "\n", 0

    def cmd_volume_ls(self, args: list[str]) -> tuple[str, int]:
        """docker volume ls"""
        lines = ["DRIVER    VOLUME NAME"]
        for vol in self.volumes.values():
            lines.append(f"{vol.driver:<9} {vol.name}")
        return "\n".join(lines) + "\n", 0

    def cmd_volume_create(self, args: list[str]) -> tuple[str, int]:
        """docker volume create [OPTIONS] [VOLUME]"""
        name = None
        for a in args:
            if not a.startswith("-"):
                name = a
                break
        if not name:
            name = f"vol_{uuid.uuid4().hex[:8]}"
        if name in self.volumes:
            raise DockerError(f"volume {name} already exists")
        vol = Volume(name=name, mountpoint=f"/var/lib/docker/volumes/{name}/_data")
        self.volumes[name] = vol
        return name + "\n", 0

    def cmd_volume_rm(self, args: list[str]) -> tuple[str, int]:
        """docker volume rm [OPTIONS] VOLUME [VOLUME...]"""
        for name in args:
            if name not in self.volumes:
                raise VolumeNotFound(f"No such volume: {name}")
            del self.volumes[name]
        return "\n".join(args) + "\n", 0

    def cmd_network_ls(self, args: list[str]) -> tuple[str, int]:
        """docker network ls"""
        lines = ["NETWORK ID     NAME      DRIVER    SCOPE"]
        for net in self.networks.values():
            lines.append(f"{net.name[:12]:<14} {net.name:<9} {net.driver:<9} local")
        return "\n".join(lines) + "\n", 0

    def cmd_network_create(self, args: list[str]) -> tuple[str, int]:
        """docker network create [OPTIONS] NETWORK"""
        name = None
        driver = "bridge"
        i = 0
        while i < len(args):
            if args[i] == "-d" and i + 1 < len(args):
                driver = args[i + 1]
                i += 2
            elif not args[i].startswith("-"):
                name = args[i]
                i += 1
            else:
                i += 1
        if not name:
            raise DockerError("network name is required")
        if name in self.networks:
            raise DockerError(f"network with name {name} already exists")
        net = Network(name=name, driver=driver)
        self.networks[name] = net
        return name + "\n", 0

    def cmd_compose_up(self, args: list[str]) -> tuple[str, int]:
        """docker compose up [OPTIONS] [SERVICE...]"""
        detached = "-d" in args or "--detach" in args
        services = [a for a in args if not a.startswith("-")]

        if not services:
            services = ["orion", "lab", "base"]

        outputs = []
        for svc in services:
            if svc not in self.SHIP_IMAGES:
                raise ComposeError(f"Service {svc} not defined in compose file")
            ref = self.SHIP_IMAGES[svc]
            name = f"compose_{svc}"
            # Check if already running
            existing = None
            for c in self.containers.values():
                if c.name == name and c.status == "running":
                    existing = c
                    break
            if existing:
                outputs.append(f"Container {name}  Running")
                continue

            # Run detached
            try:
                out, _ = self.cmd_run(["--name", name, "-d", ref])
                outputs.append(f"Container {name}  Started")
            except Exception as e:
                raise ComposeError(str(e))

        return "\n".join(outputs) + "\n", 0

    def cmd_compose_down(self, args: list[str]) -> tuple[str, int]:
        """docker compose down [OPTIONS]"""
        volumes = "-v" in args or "--volumes" in args
        removed = []
        for cid, c in list(self.containers.items()):
            if c.name.startswith("compose_"):
                if c.status == "running":
                    self.cmd_stop([cid])
                self.cmd_rm([cid])
                removed.append(c.name)
        if volumes:
            for name in list(self.volumes.keys()):
                if name.startswith("compose_"):
                    del self.volumes[name]
                    removed.append(f"volume {name}")
        return "\n".join(removed) + "\n" if removed else "Nothing to remove\n", 0

    def cmd_compose_ps(self, args: list[str]) -> tuple[str, int]:
        """docker compose ps"""
        lines = ["NAME                IMAGE                COMMAND                  SERVICE             CREATED         STATUS         PORTS"]
        for c in self.containers.values():
            if c.name.startswith("compose_"):
                svc = c.name.replace("compose_", "")
                ports_str = ", ".join(f"{pb.host_port}:{pb.container_port}" for pb in c.ports) or "—"
                lines.append(f"{c.name:<18} {c.image.full_name:<20} {' '.join(c.command)[:24]:<24} {svc:<17} 5 min ago      {c.status:<14} {ports_str}")
        return "\n".join(lines) + "\n", 0

    def cmd_system_prune(self, args: list[str]) -> tuple[str, int]:
        """docker system prune [OPTIONS]"""
        removed_containers = 0
        removed_images = 0
        removed_volumes = 0
        removed_networks = 0

        # Remove stopped containers
        for cid, c in list(self.containers.items()):
            if c.status != "running":
                self.cmd_rm([cid])
                removed_containers += 1

        # Remove unused images (not referenced by any container)
        used_images = {c.image.full_name for c in self.containers.values()}
        for key, img in list(self.images.items()):
            if key not in used_images and not key.startswith("ship/"):
                del self.images[key]
                removed_images += 1

        # Remove unused volumes
        used_volumes = set()
        for c in self.containers.values():
            for vm in c.volumes:
                if vm.type == "volume":
                    used_volumes.add(vm.source)
        for name in list(self.volumes.keys()):
            if name not in used_volumes:
                del self.volumes[name]
                removed_volumes += 1

        # Remove unused networks (except bridge)
        for name in list(self.networks.keys()):
            if name != "bridge" and not self.networks[name].containers:
                del self.networks[name]
                removed_networks += 1

        return (
            f"Deleted Containers: {removed_containers}\n"
            f"Deleted Images: {removed_images}\n"
            f"Deleted Volumes: {removed_volumes}\n"
            f"Deleted Networks: {removed_networks}\n"
            f"Total reclaimed space: 0B\n"
        ), 0

    # ─── Main entry point ──────────────────────────────────────────────

    def execute(self, command_line: str) -> tuple[str, int]:
        """Execute a docker command line string."""
        try:
            tokens = shlex.split(command_line.strip())
        except ValueError as e:
            return f"docker: {e}\n", 1

        if not tokens or tokens[0] != "docker":
            return "docker: invalid command\n", 1

        if len(tokens) < 2:
            return "docker: \"docker\" requires a command\n", 1

        subcmd = tokens[1]
        args = tokens[2:]

        # Handle compose subcommands
        if subcmd == "compose":
            if not args:
                return "docker compose: \"compose\" requires a command\n", 1
            compose_cmd = args[0]
            compose_args = args[1:]
            method_name = f"cmd_compose_{compose_cmd.replace('-', '_')}"
            method = getattr(self, method_name, None)
            if not method:
                return f"docker compose: '{compose_cmd}' is not a docker compose command.\n", 1
            try:
                return method(compose_args)
            except DockerError as e:
                return f"docker: {e.message}\n", 1
            except Exception as e:
                return f"docker: {e}\n", 1

        # Handle subcommands with two-word commands (volume create, network create, system prune, etc.)
        if subcmd in ("volume", "network", "system", "image", "container") and args:
            sub_subcmd = args[0]
            sub_args = args[1:]
            method_name = f"cmd_{subcmd}_{sub_subcmd.replace('-', '_')}"
            method = getattr(self, method_name, None)
            if method:
                try:
                    return method(sub_args)
                except DockerError as e:
                    return f"docker: {e.message}\n", 1
                except Exception as e:
                    return f"docker: {e}\n", 1

        # Regular docker commands
        method_name = f"cmd_{subcmd.replace('-', '_')}"
        method = getattr(self, method_name, None)
        if not method:
            return f"docker: '{subcmd}' is not a docker command.\nSee 'docker --help'.\n", 1

        try:
            return method(args)
        except DockerError as e:
            return f"docker: {e.message}\n", 1
        except Exception as e:
            return f"docker: {e}\n", 1

    # ─── State serialization ───────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize simulator state for sandbox persistence."""
        return {
            "images": {k: {"name": v.name, "tag": v.tag, "size": v.size, "layers": [{"id": l.id, "instruction": l.instruction, "size": l.size, "cached": l.cached} for l in v.layers]} for k, v in self.images.items()},
            "containers": {k: {"id": v.id, "name": v.name, "image": v.image.full_name, "command": v.command, "status": v.status, "ports": [{"host_port": p.host_port, "container_port": p.container_port, "protocol": p.protocol} for p in v.ports], "volumes": [{"source": vm.source, "target": vm.target, "read_only": vm.read_only, "type": vm.type} for vm in v.volumes], "networks": v.networks, "env": v.env, "labels": v.labels, "logs": v.logs, "exit_code": v.exit_code} for k, v in self.containers.items()},
            "networks": {k: {"name": v.name, "driver": v.driver, "containers": v.containers, "subnet": v.subnet, "gateway": v.gateway} for k, v in self.networks.items()},
            "volumes": {k: {"name": v.name, "driver": v.driver, "mountpoint": v.mountpoint, "labels": v.labels} for k, v in self.volumes.items()},
            "used_host_ports": list(self._used_host_ports),
            "disk_usage": self._disk_usage,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DockerSimulator":
        """Deserialize simulator state."""
        sim = cls.__new__(cls)
        sim.images = {}
        for k, v in data.get("images", {}).items():
            img = Image(name=v["name"], tag=v["tag"], size=v["size"])
            img.layers = [ImageLayer(**l) for l in v["layers"]]
            sim.images[k] = img

        sim.containers = {}
        for k, v in data.get("containers", {}).items():
            img = sim.images.get(v["image"])
            if not img:
                img = Image(name=v["image"].split(":")[0], tag=v["image"].split(":")[1] if ":" in v["image"] else "latest")
            c = Container(
                id=v["id"],
                name=v["name"],
                image=img,
                command=v["command"],
                status=v["status"],
                ports=[PortBinding(**p) for p in v["ports"]],
                volumes=[VolumeMount(**vm) for vm in v["volumes"]],
                networks=v["networks"],
                env=v["env"],
                labels=v["labels"],
                logs=v["logs"],
                exit_code=v["exit_code"],
            )
            sim.containers[k] = c

        sim.networks = {}
        for k, v in data.get("networks", {}).items():
            sim.networks[k] = Network(**v)

        sim.volumes = {}
        for k, v in data.get("volumes", {}).items():
            sim.volumes[k] = Volume(**v)

        sim._used_host_ports = set(data.get("used_host_ports", []))
        sim._disk_usage = data.get("disk_usage", 0)
        sim._layer_cache = {}
        return sim


class _RunParser:
    """Parser for docker run arguments."""

    def __init__(self) -> None:
        self.detach = False
        self.name: str | None = None
        self.ports: list[PortBinding] = []
        self.volumes: list[VolumeMount] = []
        self.env: dict[str, str] = {}
        self.labels: dict[str, str] = {}
        self.command: list[str] = []
        self.image: str = ""

    def parse(self, args: list[str]) -> "_RunParser":
        i = 0
        while i < len(args):
            arg = args[i]
            if arg in ("-d", "--detach"):
                self.detach = True
                i += 1
            elif arg in ("--name", "-n"):
                i += 1
                if i < len(args):
                    self.name = args[i]
                i += 1
            elif arg in ("-p", "--publish"):
                i += 1
                if i < len(args):
                    self.ports.append(self._parse_port(args[i]))
                i += 1
            elif arg in ("-v", "--volume"):
                i += 1
                if i < len(args):
                    self.volumes.append(self._parse_volume(args[i]))
                i += 1
            elif arg in ("-e", "--env"):
                i += 1
                if i < len(args):
                    k, _, v = args[i].partition("=")
                    self.env[k] = v
                i += 1
            elif arg in ("--label",):
                i += 1
                if i < len(args):
                    k, _, v = args[i].partition("=")
                    self.labels[k] = v
                i += 1
            elif arg.startswith("-"):
                # Skip unknown flags
                i += 1
            else:
                # First non-flag is image
                self.image = arg
                i += 1
                self.command = args[i:]
                break
        return self

    def _parse_port(self, spec: str) -> PortBinding:
        # Format: [host_ip:]host_port:container_port[/protocol]
        parts = spec.split(":")
        if len(parts) == 2:
            host_port = int(parts[0])
            container_part = parts[1]
        elif len(parts) == 3:
            host_port = int(parts[1])
            container_part = parts[2]
        else:
            raise ValueError(f"Invalid port spec: {spec}")

        if "/" in container_part:
            container_port, protocol = container_part.split("/")
        else:
            container_port, protocol = container_part, "tcp"
        return PortBinding(host_port=host_port, container_port=int(container_port), protocol=protocol)

    def _parse_volume(self, spec: str) -> VolumeMount:
        # Format: [source:]target[:ro]
        parts = spec.split(":")
        if len(parts) == 1:
            return VolumeMount(source=f"vol_{uuid.uuid4().hex[:8]}", target=parts[0], type="volume")
        elif len(parts) == 2:
            source, target = parts
            if source.startswith("/") or source.startswith(".") or source.startswith("~"):
                return VolumeMount(source=source, target=target, type="bind")
            return VolumeMount(source=source, target=target, type="volume")
        else:
            source, target, mode = parts[0], parts[1], parts[2]
            read_only = "ro" in mode
            if source.startswith("/") or source.startswith(".") or source.startswith("~"):
                return VolumeMount(source=source, target=target, read_only=read_only, type="bind")
            return VolumeMount(source=source, target=target, read_only=read_only, type="volume")