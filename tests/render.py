import json
import pathlib
import subprocess
import sys
import yaml

REPO = "dekopon-agents-integration-testing/self-configure"
PATH = "config/mutable/agent.yaml"
IMAGE = "ghcr.io/dekopon-agents/dekopon@sha256:0675042964e3d35673aa652e90ccdbe914013fbdcc067c177895b93f24907f6a"
PYTHON = "python:3.13-alpine@sha256:7984cf56ceaddebe4fefeb75d64000b9f45d8b77b11a09b24524da6cdc3af0c8"
WASM = "8fe93ef36199e3689f7a260c505343beb9dd4b7a8c0b0edaa3f5adadd7d3ceed"


def dump(value):
    return yaml.safe_dump(value, sort_keys=False)


def render(branch, chart):
    policy = """permit(principal == Dekopon::Principal::"tester", action == Dekopon::Action::"agent.prompt", resource == Dekopon::Agent::"self-configure") when { context.via == "dekopon-gatewayd" };
permit(principal == Dekopon::Principal::"tester", action in [Dekopon::Action::"gh.content.read", Dekopon::Action::"gh.content.write"], resource == Dekopon::Provider::"gh") when { context.via == "dekopon-gatewayd" && context.agent == "self-configure" };
"""
    policy += 'permit(principal == Dekopon::Principal::"verifier", action == Dekopon::Action::"agent.prompt", resource == Dekopon::Agent::"self-configure") when { context.via == "dekopon-gatewayd" };\n'
    policy += 'permit(principal == Dekopon::Principal::"verifier", action == Dekopon::Action::"gh.content.read", resource == Dekopon::Provider::"gh") when { context.via == "dekopon-gatewayd" && context.agent == "self-configure" };\n'
    for action, method, extra in [
        (
            "write",
            "PUT",
            f'!(context.request.url has query) && context.request has body && context.request.body has branch && context.request.body.branch == "{branch}"',
        ),
        (
            "read",
            "GET",
            f'context.request.url has query && context.request.url.query == "ref={branch.replace("/", "%2F")}"',
        ),
    ]:
        policy += f'''forbid(principal, action == Dekopon::Action::"gh.content.{action}", resource) when {{ context has request }} unless {{ context.request.method == "{method}" && context.request.url.host == "api.github.com" && context.request.url.path == "/repos/{REPO}/contents/{PATH}" && {extra} }};\n'''
    policy = (
        "\n".join(
            f'@id("rule-{i}")\n' + line
            for i, line in enumerate(policy.splitlines())
            if line.strip()
        )
        + "\n"
    )
    caps = {}
    for name, method in [("read", "GET"), ("write", "PUT")]:
        caps["gh.content." + name] = {
            "constraints": {
                "timeoutMs": 10000,
                "http": {
                    "allowedHosts": ["api.github.com"],
                    "allowedMethods": [method],
                    "maxRequests": 1,
                    "maxRequestBytes": 16384,
                    "maxResponseBytes": 16384,
                    "allowPlaintextLoopback": False,
                },
            }
        }
    broker = {
        "apiVersion": "dekopon.dev/brokerd/v1alpha1",
        "socketPath": "/run/dekopon/broker.sock",
        "policiesPath": "/etc/dekopon/policies.cedar",
        "secretMapPath": "/etc/dekopon/secret-map.yaml",
        "providers": ["/providers/gh.wasm"],
        "identities": [
            {
                "uid": 65532,
                "principal": "probe",
                "actor": {"type": "service", "principal": "probe"},
            },
            {
                "uid": 65533,
                "principal": "dekopon-gatewayd",
                "actor": {"type": "service", "principal": "dekopon-gatewayd"},
                "attestor": {"namespaces": ["drn:tel:*:*:*"]},
            },
        ],
        "principals": {
            "tester": {"subjects": ["drn:tel:number::16035550101"]},
            "verifier": {"subjects": ["drn:tel:number::16035550102"]},
        },
        "capabilities": {
            "gh": {
                "defaultSecretUse": {
                    "drn": "drn:secret:github/app",
                    "sink": "httpBearer",
                },
                "capabilities": caps,
            }
        },
    }
    secretmap = {
        "apiVersion": "dekopon.dev/secret-map/v1alpha1",
        "mapRevision": "1",
        "secrets": [
            {
                "drn": "drn:secret:github/app",
                "destinations": ["api.github.com"],
                "source": {"kind": "secureFile", "path": "/etc/dekopon/token"},
                "bindings": [
                    {
                        "id": "gh",
                        "capabilities": list(caps),
                        "sink": "httpBearer",
                        "allowedHosts": ["api.github.com"],
                        "allowedMethods": ["GET", "PUT"],
                        "allowedPaths": [
                            {"match": "exact", "path": f"/repos/{REPO}/contents/{PATH}"}
                        ],
                    }
                ],
            }
        ],
    }
    bindings = secretmap["secrets"][0]["bindings"]
    template = bindings.pop()
    for name, method in [("read", "GET"), ("write", "PUT")]:
        bindings.append(
            dict(
                template,
                id="gh-" + name,
                capabilities=["gh.content." + name],
                allowedMethods=[method],
            )
        )
    gateway = {
        "apiVersion": "dekopon.dev/gatewayd/v1alpha1",
        "catalogPath": "/etc/dekopon-catalog/dekopon.yaml",
        "broker": {"socketPath": "/run/dekopon/broker.sock", "serverUid": 65532},
        "transports": [
            {
                "name": "local",
                "kind": "local",
                "socketPath": "/tmp/chat.sock",
                "indicators": {"mode": "off"},
            }
        ],
        "models": [
            {
                "name": "terra",
                "kind": "openrouter",
                "model": "openai/gpt-6.1-terra",
                "apiKeyEnv": "OPENROUTER_API_KEY",
                "timeoutMs": 120000,
                "classes": ["reasoning"],
                "generation": {"maxOutputTokens": 4096},
                "routing": {"allowFallbacks": False},
            }
        ],
        "routes": [
            {
                "transport": "local",
                "conversation": {"kind": ["directMessage"]},
                "agent": "self-configure",
                "memory": {"mode": "oneShot"},
                "limits": {"maxSteps": 16, "maxCapabilityCalls": 3},
            }
        ],
        "sessions": {"maxConcurrent": 1, "replyOnBusy": True, "maxConversations": 4},
    }
    values = {
        "fullnameOverride": "dekopon",
        "image": {"digest": IMAGE.split("@")[1]},
        "broker": {
            "config": {"inline": dump(broker)},
            "policies": {"inline": policy},
            "secretMap": {"inline": dump(secretmap)},
            "secretBootstrapFiles": [
                {
                    "file": "token",
                    "existingSecret": "app-token",
                    "existingSecretKey": "token",
                }
            ],
            "env": [{"name": "RUST_LOG", "value": "info"}],
        },
        "gateway": {
            "enabled": True,
            "config": {"inline": dump(gateway)},
            "catalog": {"existingConfigMap": "agent-catalog"},
            "env": [
                {
                    "name": "OPENROUTER_API_KEY",
                    "valueFrom": {"secretKeyRef": {"name": "model-key", "key": "key"}},
                },
                {"name": "RUST_LOG", "value": "info"},
            ],
        },
        "state": {"storageClassName": "standard", "size": "1Gi"},
    }
    pathlib.Path("/tmp/values.yaml").write_text(dump(values))
    docs = list(
        yaml.safe_load_all(
            subprocess.check_output(
                [
                    "helm",
                    "template",
                    "dekopon",
                    chart,
                    "--namespace",
                    "experiment",
                    "--kube-version",
                    "1.34.0",
                    "-f",
                    "/tmp/values.yaml",
                ],
                text=True,
            )
        )
    )
    for doc in docs:
        if doc["kind"] != "Deployment":
            continue
        spec = doc["spec"]["template"]["spec"]
        spec["volumes"].extend(
            [
                {"name": "gh-provider", "emptyDir": {}},
                {"name": "helper", "configMap": {"name": "helper"}},
            ]
        )
        spec["initContainers"].insert(
            1,
            {
                "name": "fetch-gh",
                "image": PYTHON,
                "securityContext": {
                    "runAsUser": 0,
                    "runAsGroup": 0,
                    "runAsNonRoot": False,
                },
                "command": [
                    "python",
                    "-c",
                    f'import urllib.request,hashlib,os; p="/providers/gh.wasm"; b=urllib.request.urlopen("https://github.com/dekopon-agents/dekopon-provider-gh/releases/download/v0.13.0/gh-provider.wasm",timeout=60).read(); assert hashlib.sha256(b).hexdigest()=="{WASM}"; open(p,"wb").write(b); os.chown(p,65532,65532); os.chmod(p,0o600); os.chmod("/providers",0o700); os.chown("/providers",65532,65532); os.chmod("/gateway-tmp",0o700); os.chown("/gateway-tmp",65533,65533)',
                ],
                "volumeMounts": [{"name": "gh-provider", "mountPath": "/providers"}, {"name": "gateway-tmp", "mountPath": "/gateway-tmp"}],
            },
        )
        for container in spec["initContainers"]:
            if container["name"] == "broker":
                container["volumeMounts"].append(
                    {"name": "gh-provider", "mountPath": "/providers", "readOnly": True}
                )
        spec["containers"].append(
            {
                "name": "helper",
                "image": PYTHON,
                "command": ["python", "-c", "import time; time.sleep(1800)"],
                "securityContext": {
                    "runAsUser": 65533,
                    "runAsGroup": 65533,
                    "allowPrivilegeEscalation": False,
                    "capabilities": {"drop": ["ALL"]},
                },
                "volumeMounts": [
                    {"name": "gateway-tmp", "mountPath": "/tmp"},
                    {"name": "helper", "mountPath": "/helper", "readOnly": True},
                    {"name": "catalog", "mountPath": "/catalog", "readOnly": True},
                ],
            }
        )
    docs.append(
        {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "helper"},
            "data": {"ask.py": pathlib.Path("tests/ask.py").read_text()},
        }
    )
    out = pathlib.Path("runtime")
    out.mkdir(exist_ok=True)
    (out / "resources.yaml").write_text(yaml.safe_dump_all(docs, sort_keys=False))
    (out / "kustomization.yaml").write_text(dump({"resources": ["resources.yaml"]}))
    pathlib.Path("config/mutable/kustomization.yaml").write_text(
        dump(
            {
                "configMapGenerator": [
                    {"name": "agent-catalog", "files": ["dekopon.yaml=agent.yaml"]}
                ],
                "generatorOptions": {"disableNameSuffixHash": True},
            }
        )
    )
    apps = []
    for name, path in [("runtime", "runtime"), ("catalog", "config/mutable")]:
        apps.append(
            {
                "apiVersion": "argoproj.io/v1alpha1",
                "kind": "Application",
                "metadata": {"name": name, "namespace": "argocd"},
                "spec": {
                    "project": "experiment",
                    "source": {
                        "repoURL": f"https://github.com/{REPO}",
                        "targetRevision": branch,
                        "path": path,
                    },
                    "destination": {
                        "server": "https://kubernetes.default.svc",
                        "namespace": "experiment",
                    },
                    "syncPolicy": {"automated": {"prune": True, "selfHeal": True}},
                },
            }
        )
    pathlib.Path("apps").mkdir(exist_ok=True)
    pathlib.Path("apps/children.yaml").write_text(yaml.safe_dump_all(apps))


if __name__ == "__main__":
    render(*sys.argv[1:])
