import docker

docker_client = docker.from_env()

def discover_workers():
    containers = docker_client.containers.list(filters={"label": "role=worker"})
    return [f"http://{c.name}:8080" for c in containers]