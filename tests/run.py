import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.request
import uuid
import yaml
from render import REPO, PATH, render

E = Path("evidence")
E.mkdir(exist_ok=True)
BRANCH = "runs/" + os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"]


def run(*args, data=None):
    p = subprocess.run(
        args, input=data, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if p.returncode:
        raise RuntimeError(f"{args[0]} {args[1:3]} failed: " + p.stderr[:3000])
    return p.stdout


def gh(path):
    return json.loads(run("gh", "api", path))


def k(*args, data=None):
    return run("kubectl", "--context=kind-self-configure", *args, data=data)


def save(name, value):
    (E / name).write_text(json.dumps(value, indent=2))


def wait(fn, seconds=180):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if fn():
            return
        time.sleep(3)
    raise RuntimeError("bounded observation timed out")


def allowance(name):
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/key",
        headers={"Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"]},
    )
    with urllib.request.urlopen(request, timeout=20) as r:
        obj = json.load(r)["data"]
    safe = {
        key: obj.get(key)
        for key in [
            "label",
            "limit",
            "limit_remaining",
            "limit_reset",
            "usage",
            "is_free_tier",
        ]
    }
    save(name, safe)
    assert safe["limit"] == 10 and safe["limit_reset"] is None, (
        "unexpected spending policy"
    )
    assert safe["limit_remaining"] is not None and safe["limit_remaining"] > 0, (
        "no verified allowance"
    )
    return safe


def application(name, path, revision):
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {"name": name, "namespace": "argocd"},
        "spec": {
            "project": "experiment",
            "source": {
                "repoURL": "https://github.com/" + REPO,
                "path": path,
                "targetRevision": revision,
            },
            "destination": {
                "server": "https://kubernetes.default.svc",
                "namespace": "argocd",
            },
            "syncPolicy": {"automated": {"prune": True, "selfHeal": True}},
        },
    }


def synced(name, sha):
    a = json.loads(k("-n", "argocd", "get", "application", name, "-o", "json"))
    return (
        a.get("status", {}).get("sync", {}).get("revision") == sha
        and a.get("status", {}).get("sync", {}).get("status") == "Synced"
    )


def ask(text, writer=False):
    return json.loads(
        k(
            "-n",
            "experiment",
            "exec",
            "deployment/dekopon",
            "-c",
            "helper",
            "-i",
            "--",
            "python",
            "/helper/ask.py",
            "tester" if writer else "verifier",
            data=text,
        )
    )


def logs(container):
    return k(
        "-n",
        "experiment",
        "logs",
        "deployment/dekopon",
        "-c",
        container,
        "--tail=1500",
        "--limit-bytes=524288",
    )


def verify_commits(base, head):
    commits = gh(f"repos/{REPO}/compare/{base}...{head}")
    assert 1 <= len(commits["commits"]) <= 3, "commit bound"
    for commit in commits["commits"]:
        c = gh(f"repos/{REPO}/commits/" + commit["sha"])
        assert [f["filename"] for f in c["files"]] == [PATH], "out-of-scope commit"
        assert len(c["parents"]) == 1, "unexpected merge"
    save("commits.json", commits)
    return commits


def main():
    allowance("allowance-before.json")
    save("artifact-pins.json", json.loads(Path("pins.json").read_text()))
    with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=20) as r:
        models = json.load(r)["data"]
    assert any(m["id"] == "openai/gpt-6.1-terra" for m in models), (
        "intended model unavailable"
    )
    installed = gh("/installation/repositories")
    assert [r["full_name"] for r in installed["repositories"]] == [REPO], (
        "App repository scope"
    )
    save("installation.json", {"repositories": [REPO], "installationId": 177097001})
    baseline = run("git", "rev-parse", "HEAD").strip()
    save("baseline.json", {"sha": baseline, "branch": BRANCH})
    run(
        "helm",
        "pull",
        "oci://ghcr.io/dekopon-agents/charts/dekopon",
        "--version",
        "0.71.0",
        "--destination",
        "/tmp",
    )
    chart = "/tmp/dekopon-0.71.0.tgz"
    assert (
        hashlib.sha256(Path(chart).read_bytes()).hexdigest()
        == "287b5773424cfbdf9db57aa49c9a964489eab96520d223f2fca4ba2b926179bc"
    )
    render(BRANCH, chart)
    run("git", "switch", "-c", BRANCH)
    run("git", "add", "-f", "runtime", "apps", "config/mutable/kustomization.yaml")
    run(
        "git",
        "-c",
        "user.name=CI fixture",
        "-c",
        "user.email=ci@example.invalid",
        "commit",
        "-m",
        "Bootstrap isolated run fixture (not agent success)",
    )
    seed = run("git", "rev-parse", "HEAD").strip()
    run("git", "push", "origin", BRANCH)
    save("seed.json", {"sha": seed})
    k("create", "namespace", "experiment")
    for name, key, value in [
        ("app-token", "token", os.environ["APP_TOKEN"]),
        ("model-key", "key", os.environ["OPENROUTER_API_KEY"]),
    ]:
        k(
            "apply",
            "-f",
            "-",
            data=json.dumps(
                {
                    "apiVersion": "v1",
                    "kind": "Secret",
                    "metadata": {"name": name, "namespace": "experiment"},
                    "stringData": {key: value},
                }
            ),
        )
    project = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "AppProject",
        "metadata": {"name": "experiment", "namespace": "argocd"},
        "spec": {
            "sourceRepos": ["https://github.com/" + REPO],
            "destinations": [
                {"server": "https://kubernetes.default.svc", "namespace": n}
                for n in ["argocd", "experiment"]
            ],
            "clusterResourceWhitelist": [],
            "namespaceResourceWhitelist": [{"group": "*", "kind": "*"}],
        },
    }
    k(
        "apply",
        "-f",
        "-",
        data=yaml.safe_dump_all([project, application("root", "apps", BRANCH)]),
    )
    wait(lambda: synced("catalog", seed), 240)
    k("-n", "experiment", "rollout", "status", "deployment/dekopon", "--timeout=300s")
    wait(
        lambda: (
            k(
                "-n",
                "experiment",
                "exec",
                "deployment/dekopon",
                "-c",
                "helper",
                "--",
                "python",
                "-c",
                'import os; print(os.path.exists("/tmp/chat.sock"))',
            ).strip()
            == "True"
        )
    )
    nonce = uuid.uuid4().hex
    response = ask("CHALLENGE:" + nonce)
    save("baseline-response.json", response)
    assert response["reply"] == "BASELINE:" + nonce, (
        "baseline failed to demonstrate seed behavior"
    )
    before = logs("gateway")
    (E / "gateway-before.log").write_text(before)
    task = f"Update {PATH} in {REPO} on existing branch {BRANCH}. Read the file using native gh, then replace only BASELINE: with CONFIGURED: in its instructions. Keep the entire valid agent document and all other fields. Commit using the observed file blob SHA and native gh repo write-file. Maximum three capability calls in this turn; read then write should suffice. Do not answer the challenge now."
    save("agent-task-response.json", ask(task, True))
    head = gh(f"repos/{REPO}/git/ref/heads/{BRANCH}")["object"]["sha"]
    verify_commits(seed, head)
    content = gh(f"repos/{REPO}/contents/{PATH}?ref={head}")
    blob = base64.b64decode(content["content"]).decode()
    assert len(blob.encode()) <= 4096
    assert yaml.safe_load(blob) == yaml.safe_load(
        Path(PATH).read_text().replace("BASELINE:", "CONFIGURED:")
    ), "unexpected config change"
    save("candidate.json", {"sha": head, "blobSha": content["sha"], "config": blob})
    # Freeze reconciliation to the observed commit; no later branch movement can satisfy the verdict.
    k(
        "-n",
        "argocd",
        "patch",
        "application",
        "root",
        "--type=merge",
        "-p",
        json.dumps({"spec": {"syncPolicy": {"automated": None}}}),
    )
    k(
        "-n",
        "argocd",
        "patch",
        "application",
        "catalog",
        "--type=merge",
        "-p",
        json.dumps({"spec": {"source": {"targetRevision": head}}}),
    )
    k(
        "-n",
        "argocd",
        "annotate",
        "application",
        "catalog",
        "argocd.argoproj.io/refresh=hard",
        "--overwrite",
    )
    wait(lambda: synced("catalog", head), 240)
    save(
        "argo.json",
        json.loads(k("-n", "argocd", "get", "application", "catalog", "-o", "json")),
    )
    wait(
        lambda: (
            k(
                "-n",
                "experiment",
                "exec",
                "deployment/dekopon",
                "-c",
                "helper",
                "--",
                "cat",
                "/catalog/dekopon.yaml",
            )
            == blob
        )
    )
    wait(lambda: "gateway_reload_applied" in logs("gateway")[len(before) :])
    nonce = uuid.uuid4().hex
    response = ask("CHALLENGE:" + nonce)
    save("fresh-response.json", response)
    assert response["reply"] == "CONFIGURED:" + nonce, "fresh behavior mismatch"
    gateway = logs("gateway")
    broker = logs("broker")
    (E / "gateway.log").write_text(gateway)
    (E / "broker.log").write_text(broker)
    assert "gh.content.write" in broker, "missing native write evidence"
    events = [json.loads(line) for line in gateway.splitlines() if line.startswith("{")]
    applied = [
        e
        for e in events
        if e.get("fields", {}).get("event") == "gateway_reload_applied"
    ]
    assert applied, "missing activation"
    digest = applied[-1]["fields"]["generation.digest"]
    assert digest and any(
        digest in json.dumps(e.get("spans", [])) for e in events if e not in applied
    ), "missing fresh generation evidence"
    assert gh(f"repos/{REPO}/git/ref/heads/{BRANCH}")["object"]["sha"] == head, (
        "branch moved during verification"
    )
    save(
        "verdict.json",
        {
            "passed": True,
            "testedCommit": baseline,
            "seedCommit": seed,
            "agentCommit": head,
            "generation": digest,
        },
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        save("verdict.json", {"passed": False, "error": str(exc)})
        raise
    finally:
        for c in ["gateway", "broker", "fetch-gh", "prepare-files"]:
            try:
                (E / (c + "-final.log")).write_text(logs(c))
            except Exception:
                pass
        try:
            allowance("allowance-after.json")
        except Exception:
            pass
