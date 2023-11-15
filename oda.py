#!/usr/bin/env python3
"""Odoo Administration Tool
This tool uses a local kubernetes cluster to spin up develompent environments
It manages the Odoo source repositories in the workspace/repo/odoo directory
"""
from shutil import copytree
import json
import base64
import subprocess
import argparse
import os
import sys
import time
from pathlib import Path
import yaml
import toml
from git import Repo
from kubernetes import client, config

SEMVER = "0.1.0"
# paths
config_dir = os.path.join(Path.home(), ".config")
local_dir = os.path.join(Path.home(), ".local")
manifests = os.path.join(config_dir, "oda/manifests")
storage = os.path.join(local_dir, "oda")
repo_dir = os.path.join(Path.home(), "workspace/repos/odoo")
project_dir = os.path.join(Path.home(), "workspace/odoo")
current_working_directory = os.getcwd()

container_image = {"name": "odoobase", "image": "ghcr.io/ppreeper/odoobase:main"}

# load kubernetes config
config.load_kube_config()
v1 = client.CoreV1Api()


#
def get_pod(name):
    """Get Pod from name"""
    ret = v1.list_pod_for_all_namespaces(watch=False)
    for pod in ret.items:
        if pod.metadata.name.startswith(name):
            return pod.metadata.name


# ===================
# ===================
# kubenetes manifest generation
def gen_pv(volume, acl, size, path):
    """Generate a PersistentVolume"""
    cfg = {
        "apiVersion": "v1",
        "kind": "PersistentVolume",
        "metadata": {"name": f"{volume}-pv"},
        "spec": {
            "accessModes": [acl],
            "capacity": {"storage": size},
            "persistentVolumeReclaimPolicy": "Retain",
            "hostPath": {"path": path},
        },
    }
    yaml_string = yaml.dump(cfg)
    return "---\n" + yaml_string


def gen_pvc(volume, acl, size):
    """Generate a PersistentVolumeClaim"""
    cfg = {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {"name": f"{volume}-pvc"},
        "spec": {
            "accessModes": [acl],
            "resources": {"requests": {"storage": size}},
            "volumeName": f"{volume}-pv",
        },
    }
    yaml_string = yaml.dump(cfg)
    return "---\n" + yaml_string


def gen_secret(name, password):
    """Generate a Secrets"""
    cfg = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": f"{name}-secret"},
        "type": "Opaque",
        "data": {
            "password": base64.b64encode(bytes(password, "utf-8")).decode(),
        },
    }
    yaml_string = yaml.dump(cfg)
    return "---\n" + yaml_string


def gen_service(name, port_list):
    """Generate a Service"""
    port_dict = []
    for port_tuple in port_list:
        port_name, port = port_tuple[0], port_tuple[1]
        port_dict.append({"name": port_name, "port": port})

    cfg = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": name,
            "labels": {"app": name},
        },
        "spec": {"selector": {"app": name}, "ports": port_dict, "clusterIP": "None"},
    }
    yaml_string = yaml.dump(cfg)
    return "---\n" + yaml_string


def gen_ingress(name, portpath):
    """Generate Ingress to Service"""
    port_dict = []
    for port_tuple in portpath:
        port_name, port = port_tuple[0], port_tuple[1]
        port_dict.append(
            {
                "path": port,
                "pathType": "Exact",
                "backend": {"service": {"name": name, "port": {"number": port_name}}},
            }
        )
    cfg = {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "metadata": {
            "name": name,
            "annotations": {"ingress.kubernetes.io/rewrite-target": "/"},
        },
        "spec": {"rules": [{"host": f"{name}.local", "http": {"paths": port_dict}}]},
    }
    yaml_string = yaml.dump(cfg)
    return "---\n" + yaml_string


def gen_deployment(name, image, ports, volumes, globalvols):
    """Generate Deployment"""
    port_dict = []
    for port in ports:
        port_dict.append({"containerPort": port})

    volumemount_dict = []
    volume_dict = []
    for volume in volumes:
        volumemount_dict.append({"mountPath": volume[1], "name": f"{name}-{volume[0]}"})
        volume_dict.append(
            {
                "name": f"{name}-{volume[0]}",
                "persistentVolumeClaim": {"claimName": f"{name}-{volume[0]}-pvc"},
            }
        )

    for volume in globalvols:
        volumemount_dict.append({"mountPath": volume[1], "name": f"{volume[0]}"})
        volume_dict.append(
            {
                "name": f"{volume[0]}",
                "persistentVolumeClaim": {"claimName": f"{volume[0]}-pvc"},
            }
        )

    cfg = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": name, "labels": {"app": name}},
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": {"app": name}},
            "template": {
                "metadata": {"labels": {"app": name}},
                "spec": {
                    "containers": [
                        {
                            "name": image["name"],
                            "image": image["image"],
                            "imagePullPolicy": "Always",
                            "ports": port_dict,
                            "volumeMounts": volumemount_dict,
                        }
                    ],
                    "volumes": volume_dict,
                },
            },
        },
    }
    yaml_string = yaml.dump(cfg)
    return "---\n" + yaml_string


def gen_postgres_statefulset(name, version, image, port_list):
    """Generate StatefulSet"""
    port_dict = []
    for port_tuple in port_list:
        port_name, port = port_tuple[0], port_tuple[1]
        port_dict.append({"name": port_name, "containerPort": port})
    cfg = {
        "apiVersion": "apps/v1",
        "kind": "StatefulSet",
        "metadata": {
            "name": name,
        },
        "spec": {
            "serviceName": name,
            "replicas": 1,
            "selector": {"matchLabels": {"app": name}},
            "template": {
                "metadata": {"labels": {"app": name}},
                "spec": {
                    "containers": [
                        {
                            "name": name,
                            "image": image,
                            "args": ["-c", "config_file=/config/postgresql.conf"],
                            "env": [
                                {"name": "PGDATA", "value": "/data/pgdata"},
                                {"name": "POSTGRES_USER", "value": "postgres"},
                                {
                                    "name": "POSTGRES_PASSWORD",
                                    "valueFrom": {
                                        "secretKeyRef": {
                                            "name": f"{name}",
                                            "key": "password",
                                        }
                                    },
                                },
                            ],
                            "ports": port_dict,
                            "volumeMounts": [
                                {
                                    "name": "config",
                                    "mountPath": "/config",
                                },
                                {
                                    "name": "init",
                                    "mountPath": "/docker-entrypoint-initdb.d",
                                },
                                {
                                    "name": f"{name}-{version}-pvc",
                                    "mountPath": "/data",
                                },
                            ],
                        }
                    ],
                    "volumes": [
                        {
                            "name": "config",
                            "configMap": {
                                "name": f"{name}-config",
                                "defaultMode": "0o755",
                            },
                        },
                        {
                            "name": "init",
                            "configMap": {
                                "name": f"{name}-init",
                                "defaultMode": "0o755",
                            },
                        },
                        {
                            "name": f"{name}-{version}-pvc",
                            "persistentVolumeClaim": {
                                "claimName": f"{name}-{version}-pvc"
                            },
                        },
                    ],
                },
            },
        },
    }
    yaml_string = yaml.dump(cfg)
    return "---\n" + yaml_string


def gen_configmap(name, kv_list):
    """Generate ConfigMap"""
    data = {}
    for kv in kv_list:
        data[kv[0]] = kv[1]
    cfg = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": name,
        },
        "data": data,
    }
    yaml_string = yaml.dump(cfg)
    return "---\n" + yaml_string


# ===================
# ===================
# config
def get_host_paths(manifest):
    """Get PersistenVolume hostPath"""
    host_paths = []
    with open(manifest, "r", encoding="UTF-8") as file:
        docs = yaml.safe_load_all(file)
        for doc in docs:
            if doc["kind"] == "Deployment":
                vols = doc["spec"]["template"]["spec"]["volumes"]
                for vol in vols:
                    if vol["name"].startswith("odoo") or vol["name"].startswith(
                        "enterprise"
                    ):
                        pvc_name = vol["persistentVolumeClaim"]["claimName"]
                        pvcs = v1.list_namespaced_persistent_volume_claim(
                            namespace="default"
                        )
                        pv_name = ""
                        for pvc in pvcs.items:
                            if pvc.metadata.name == pvc_name:
                                pv_name = pvc.spec.volume_name
                        pvs = v1.list_persistent_volume()
                        for pv in pvs.items:
                            if pv.metadata.name == pv_name:
                                host_paths.append(pv.spec.host_path.path)

    return host_paths


# config vscode
def config_vscode():
    """Write the VSCode config"""
    if not os.path.exists(os.path.join(current_working_directory, "conf", "odoo.conf")):
        print("not in a project directory")
        return
    project = os.path.basename(current_working_directory)

    if not os.path.exists(os.path.join(current_working_directory, f"{project}.yaml")):
        print("no project manifest found")
        return

    host_paths = get_host_paths(
        os.path.join(current_working_directory, f"{project}.yaml")
    )

    if not os.path.exists(os.path.join(current_working_directory, ".vscode")):
        os.makedirs(os.path.join(current_working_directory, ".vscode"))

    with open(
        os.path.join(current_working_directory, ".vscode", "launch.json"),
        "w",
        encoding="UTF-8",
    ) as launch:
        launch.write(
            json.dumps(
                {
                    "version": "0.2.0",
                    "configurations": [
                        {
                            "name": "Launch",
                            "type": "python",
                            "request": "launch",
                            "stopOnEntry": False,
                            "python": "${command:python.interpreterPath}",
                            "program": "${workspaceRoot}/odoo/odoo-bin",
                            "args": [
                                "-c",
                                "${workspaceRoot}/conf/odoo.conf",
                                "-p",
                                "$ODOO_PORT",
                            ],
                            "cwd": "${workspaceRoot}",
                            "env": {},
                            "envFile": "${workspaceFolder}/.env",
                            "console": "integratedTerminal",
                        }
                    ],
                },
                indent=4,
            )
        )
    with open(
        os.path.join(current_working_directory, ".vscode", "settings.json"),
        "w",
        encoding="UTF-8",
    ) as settings:
        settings.write(
            json.dumps(
                {
                    "python.analysis.extraPaths": host_paths,
                    "python.linting.pylintEnabled": True,
                    "python.linting.enabled": True,
                    "python.terminal.executeInFileDir": True,
                    "python.formatting.provider": "black",
                },
                indent=4,
            )
        )
    return


# config pyright
def config_pyright():
    """Write pyrightconfig.json"""
    if not os.path.exists(os.path.join(current_working_directory, "conf", "odoo.conf")):
        print("not in a project directory")
        return
    project = os.path.basename(current_working_directory)

    if not os.path.exists(os.path.join(current_working_directory, f"{project}.yaml")):
        print("no project manifest found")
        return

    host_paths = get_host_paths(
        os.path.join(current_working_directory, f"{project}.yaml")
    )
    host_paths.append("addons")

    with open(
        os.path.join(current_working_directory, "pyrightconfig.json"),
        "w",
        encoding="UTF-8",
    ) as settings:
        settings.write(
            json.dumps(
                {
                    "venvPath": ".",
                    "venv": ".direnv",
                    "executionEnvironments": [{"root": ".", "extraPaths": host_paths}],
                },
                indent=4,
            )
        )
    return


# ===================
# kube
# kube gen postgres
def kube_gen_postgres(version):
    """Generate PostgreSQL Manifest"""
    print(f"postgres {version} manifest")
    if not os.path.exists(manifests):
        os.makedirs(manifests)
    postgres_manifest = os.path.join(manifests, "postgres.yaml")

    if not os.path.exists(os.path.join(local_dir, "oda", "postgres", version, "data")):
        os.makedirs(os.path.join(local_dir, "oda", "postgres", version, "data"))

    with open(postgres_manifest, "w", encoding="UTF-8") as postgres:
        # secret
        postgres.write(gen_secret("postgres", "postgres"))
        # pv
        postgres.write(
            gen_pv(
                f"postgres-{version}",
                "ReadWriteOnce",
                "10Gi",
                os.path.join(local_dir, "oda", "postgres", version, "data"),
            )
        )
        # pvc
        postgres.write(
            gen_pvc(
                f"postgres-{version}",
                "ReadWriteOnce",
                "10Gi",
            )
        )
        # configmap-config
        postgres.write(
            gen_configmap(
                "postgres-config",
                [
                    [
                        "pg_hba.conf",
                        """    # TYPE  DATABASE        USER            ADDRESS                 METHOD
    # "local" is for Unix domain socket connections only
    local   all             all                                     trust
    # IPv4 local connections:
    host    all             all             127.0.0.1/32            trust
    # IPv6 local connections:
    host    all             all             ::1/128                 trust
    # Allow replication connections from localhost, by a user with the
    # replication privilege.
    local   replication     all                                     trust
    host    replication     all             127.0.0.1/32            trust
    host    replication     all             ::1/128                 trust

    host all all all scram-sha-256
""",
                    ],
                    [
                        "postgresql.conf",
                        """data_directory = '/data/pgdata'
    hba_file = '/config/pg_hba.conf'
    ident_file = '/config/pg_ident.conf'

    port = 5432
    listen_addresses = '*'
    max_connections = 100
    shared_buffers = 128MB
    dynamic_shared_memory_type = posix
    max_wal_size = 1GB
    min_wal_size = 80MB
    log_timezone = 'Etc/UTC'
    datestyle = 'iso, mdy'
    timezone = 'Etc/UTC'

    #locale settings
    lc_messages = 'en_US.utf8'                  # locale for system error message
    lc_monetary = 'en_US.utf8'                  # locale for monetary formatting
    lc_numeric = 'en_US.utf8'                   # locale for number formatting
    lc_time = 'en_US.utf8'                              # locale for time formatting

    default_text_search_config = 'pg_catalog.english'""",
                    ],
                ],
            )
        )
        # configmap-init
        postgres.write(
            gen_configmap(
                "postgres-init",
                [
                    [
                        "createodoouser.sql",
                        "CREATE ROLE odoodev WITH LOGIN CREATEDB PASSWORD 'odooodoo'",
                    ]
                ],
            )
        )
        # statefulset
        postgres.write(
            gen_postgres_statefulset(
                "postgres",
                version,
                f"postgres:{version}-alpine",
                [["postgres", 5432]],
            )
        )
        # service
        postgres.write(gen_service("postgres", [["postgres", 5432]]))
    return


def kube_apply_postgres():
    """Start PostgreSQL"""
    postgres_manifest = os.path.join(manifests, "postgres.yaml")
    subprocess.run(["kubectl", "apply", "-f", postgres_manifest], check=True)
    return


def get_current_odoo_repos():
    """Get Currently Copied Odoo Repos"""
    dirnames = os.listdir(repo_dir)
    dirnames = [dir for dir in dirnames if dir != "odoo"]
    dirnames = [dir for dir in dirnames if dir != "enterprise"]
    return dirnames


# kube gen odoo
def kube_gen_odoo():
    """Generate Odoo Volume Manifest"""
    print("odoo manifest")
    if not os.path.exists(manifests):
        os.makedirs(manifests)
    if not os.path.exists(os.path.join(project_dir, "backups")):
        os.makedirs(os.path.join(project_dir, "backups"))
    odoo_manifest = os.path.join(manifests, "odoo.yaml")
    dirnames = get_current_odoo_repos()
    with open(odoo_manifest, "w", encoding="UTF-8") as odoo:
        for dirname in dirnames:
            dname = dirname.replace(".", "-")
            dirs = os.listdir(os.path.join(repo_dir, dirname))
            for d in dirs:
                odoo.write(
                    gen_pv(
                        f"{d}-{dname}",
                        "ReadOnlyMany",
                        "10Gi",
                        os.path.join(repo_dir, dirname, d),
                    )
                )
                odoo.write(gen_pvc(f"{d}-{dname}", "ReadOnlyMany", "10Gi"))
                odoo.write(
                    gen_pv(
                        "backups",
                        "ReadWriteMany",
                        "10Gi",
                        os.path.join(project_dir, "backups"),
                    )
                )
                odoo.write(gen_pvc("backups", "ReadWriteMany", "10Gi"))
    return


def kube_apply_odoo():
    """Start Odoo Volumes"""
    print("kube_apply_odoo")
    odoo_manifest = os.path.join(manifests, "odoo.yaml")
    subprocess.run(["kubectl", "apply", "-f", odoo_manifest], check=True)
    return


# ===================
# start
def start():
    """Start the instance"""
    if not os.path.exists(os.path.join(current_working_directory, "conf", "odoo.conf")):
        print("not in a project directory")
        return
    project = os.path.basename(current_working_directory)
    if not os.path.exists(os.path.join(current_working_directory, f"{project}.yaml")):
        print("no project manifest found")
        return
    print(f"start {project}")
    subprocess.run(
        [
            "kubectl",
            "apply",
            "-f",
            os.path.join(current_working_directory, f"{project}.yaml"),
        ],
        check=True,
    )
    return


# ===================
# stop
def stop():
    """Stop the instance"""
    if not os.path.exists(os.path.join(current_working_directory, "conf", "odoo.conf")):
        print("not in a project directory")
        return
    project = os.path.basename(current_working_directory)
    if not os.path.exists(os.path.join(current_working_directory, f"{project}.yaml")):
        print("no project manifest found")
        return
    print(f"stop {project}")
    subprocess.run(
        [
            "kubectl",
            "delete",
            "-f",
            os.path.join(current_working_directory, f"{project}.yaml"),
        ],
        check=True,
    )
    return


# ===================
# restart
def restart():
    """Restart the instance"""
    if not os.path.exists(os.path.join(current_working_directory, "conf", "odoo.conf")):
        print("not in a project directory")
        return
    project = os.path.basename(current_working_directory)
    if not os.path.exists(os.path.join(current_working_directory, f"{project}.yaml")):
        print("no project manifest found")
        return
    pod = get_pod(project)
    v1.delete_namespaced_pod(pod, "default")
    print(f"restart {project}")
    return


# ===================
# app
def parse_modules(modules):
    """parse modules list"""
    mod_list = []
    for m in modules:
        mod_list.extend(m.split(","))
    return ",".join(mod_list)


# app install
# app upgrade
def app_install_upgrade(modules, install=True):
    """Install Upgrade modules"""
    iu = "-i" if install else "-u"
    print(f"appinstall {modules}")
    if not os.path.exists(os.path.join(current_working_directory, "conf", "odoo.conf")):
        print("not in a project directory")
        return
    project = os.path.basename(current_working_directory)
    if not os.path.exists(os.path.join(current_working_directory, f"{project}.yaml")):
        print("no project manifest found")
        return
    pod_name = get_pod(project)
    mod_list = parse_modules(modules)
    subprocess.run(
        [
            "kubectl",
            "exec",
            "--stdin",
            "--tty",
            pod_name,
            "--",
            "odoo/odoo-bin",
            "--no-http",
            "--stop-after-init",
            iu,
            f"{mod_list}",
        ],
        check=True,
    )
    return


# ===================
# logs
def logs():
    """Show logs"""
    print("logs")
    if not os.path.exists(os.path.join(current_working_directory, "conf", "odoo.conf")):
        print("not in a project directory")
        return
    project = os.path.basename(current_working_directory)
    if not os.path.exists(os.path.join(current_working_directory, f"{project}.yaml")):
        print("no project manifest found")
        return
    pod_name = get_pod(project)
    subprocess.run(["kubectl", "logs", "-f", pod_name], check=True)
    return


# ===================
# scaffold
def scaffold(module):
    """Scaffold an App"""
    print(f"scaffold {module}")
    if not os.path.exists(os.path.join(current_working_directory, "conf", "odoo.conf")):
        print("not in a project directory")
        return
    project = os.path.basename(current_working_directory)
    if not os.path.exists(os.path.join(current_working_directory, f"{project}.yaml")):
        print("no project manifest found")
        return
    pod_name = get_pod(project)
    subprocess.run(
        [
            "kubectl",
            "exec",
            "--stdin",
            "--tty",
            pod_name,
            "--",
            "odoo/odoo-bin",
            "scaffold",
            f"{module}",
            "/opt/odoo/addons/.",
        ],
        check=True,
    )
    return


# ===================
# psql
def psql():
    """Connect to Database"""
    if not os.path.exists(os.path.join(current_working_directory, "conf", "odoo.conf")):
        print("not in a project directory")
        return
    project = os.path.basename(current_working_directory)
    if not os.path.exists(os.path.join(current_working_directory, f"{project}.yaml")):
        print("no project manifest found")
        return
    print(f"psql {project}")
    db = get_odoo_conf("db_name")
    subprocess.run(
        [
            "kubectl",
            "exec",
            "--stdin",
            "--tty",
            "postgres-0",
            "--",
            "su",
            "postgres",
            "-c",
            f"/usr/local/bin/psql {db}",
        ],
        check=True,
    )
    return


# ===================
# query
def query():
    """Query Odoo"""
    # TODO: query
    print("query")
    return


# ===================
# backup
def backup():
    """Backup to file"""
    print("backup")
    if not os.path.exists(os.path.join(current_working_directory, "conf", "odoo.conf")):
        print("not in a project directory")
        return
    project = os.path.basename(current_working_directory)
    if not os.path.exists(os.path.join(current_working_directory, f"{project}.yaml")):
        print("no project manifest found")
        return
    pod_name = get_pod(project)
    subprocess.run(
        ["kubectl", "exec", "--stdin", "--tty", pod_name, "--", "oda_db.py", "-b"],
        check=True,
    )
    return


# ===================
# restore
def restore(backup_files):
    """Restore from backup file"""
    # TODO: restore
    print(f"restore {backup_files}")
    return


# ===================
# manifest
# manifest export
def manifest_export():
    """Odoo Manifest Export"""
    # TODO: manifest_export
    print("manifest_export")
    return


# manifest import
def manifest_import(manifest):
    """Odoo Manifest Import"""
    # TODO: manifest_import
    print(f"manifest_import {manifest}")
    return


# manifest remote
def manifest_remote(remote):
    """Odoo Manifest Import from remote"""
    # TODO: manifest_remote
    print(f"manifest_remote {remote}")
    return


# ===================
# admin
# admin user
def admin_user(username):
    """Set Admin username"""
    # TODO: admin_user
    print(f"admin_user {username}")
    return


# admin password
def admin_password(password):
    """Set Admin password"""
    # TODO: admin_password
    print(f"admin_password {password}")
    return


# ===================
# project


def get_odoo_conf(key):
    """get key value from odoo.conf"""
    with open(
        os.path.join(current_working_directory, "conf", "odoo.conf"),
        "r",
        encoding="UTF-8",
    ) as f:
        lines = f.readlines()
        for line in lines:
            if line.startswith(key):
                return line.split("=")[1].strip()
    return


def gen_odoo_conf(dbname, epoch, enterprise=True):
    """Generate and write the project odoo.conf file"""
    enterprise_dir = ""
    if enterprise:
        enterprise_dir = "/opt/odoo/enterprise,"
    return {
        "addons_path": f"/opt/odoo/odoo/addons,{enterprise_dir}/opt/odoo/addons",
        "data_dir": "/opt/odoo/data",
        "admin_passwd": "adminadmin",
        "without_demo": "all",
        "csv_internal_sep": ";",
        "reportgz": False,
        "server_wide_modules": "base,web",
        "db_host": "postgres",
        "db_port": 5432,
        "db_maxconn": 8,
        "db_user": "odoodev",
        "db_password": "odooodoo",
        "db_name": f"{dbname}_{epoch}",
        "db_template": "template0",
        "db_sslmode": "disable",
        "list_db": False,
        "proxy": True,
        "proxy_mode": True,
        "logfile": "/dev/stderr",
        "log_level": "debug",
        "log_handler": "odoo.tools.convert:DEBUG",
        "workers": 0,
    }


# project init
def project_init(edition, version, projectname):
    # TODO: project_init
    """Initialize Project"""
    print("project_init", edition, version, projectname)
    if os.path.exists(os.path.join(project_dir, projectname)):
        print(f"project {projectname} already exists")
        return
    os.makedirs(os.path.join(project_dir, projectname))
    for pdir in ["addons", "conf", "data"]:
        os.makedirs(os.path.join(project_dir, projectname, pdir))

    t = time.strftime("%Y%m%d%H%M%S", time.localtime(time.time()))

    with open(
        os.path.join(project_dir, projectname, "conf", "odoo.conf"),
        "w",
        encoding="UTF-8",
    ) as odoo_conf:
        if edition == "community":
            oconf = gen_odoo_conf(projectname, epoch=t, enterprise=False)
        else:
            oconf = gen_odoo_conf(projectname, epoch=t, enterprise=True)
        odoo_conf.write("[options]" + "\n")
        for k, v in oconf.items():
            odoo_conf.write(f"{k} = {v}" + "\n")
    volumes = [
        {
            "name": "conf",
            "acl": "ReadOnlyMany",
            "size": "1Mi",
        },
        {
            "name": "addons",
            "acl": "ReadWriteOnce",
            "size": "10Gi",
        },
        {
            "name": "data",
            "acl": "ReadWriteOnce",
            "size": "10Gi",
        },
    ]
    dep_vols = []
    for vol in volumes:
        dep_vols.append([vol["name"], f"/opt/odoo/{vol['name']}"])
    with open(
        os.path.join(project_dir, projectname, f"{projectname}.yaml"),
        "w",
        encoding="UTF-8",
    ) as manifest:
        for vol in volumes:
            manifest.write(
                gen_pv(
                    f"{projectname}-{vol['name']}",
                    vol["acl"],
                    vol["size"],
                    os.path.join(project_dir, projectname, vol["name"]),
                )
            )
            manifest.write(
                gen_pvc(f"{projectname}-{vol['name']}", vol["acl"], vol["size"])
            )
        vers = version.replace(".", "-")
        manifest.write(
            gen_deployment(
                projectname,
                container_image,
                [8069, 8072],
                dep_vols,
                [
                    ["backups", "/opt/odoo/backups"],
                    [f"odoo-{vers}", "/opt/odoo/odoo"],
                    [f"enterprise-{vers}", "/opt/odoo/enterprise"],
                ],
            )
        )
        manifest.write(gen_service(projectname, [["odoo", 8069], ["websocket", 8072]]))
        manifest.write(gen_ingress(projectname, [[8069, "/"], [8072, "/websocket"]]))

    return


# project branch
def project_branch(edition, version, projectname, branch, url):
    """Initialize Project"""
    # TODO: project_branch
    print("project_branch")
    print(edition, version, projectname, branch, url)
    return


# project reset
def project_reset():
    """Project Reset: drop database and clear the data directory"""
    # TODO: project_reset
    print("project_reset")
    if not os.path.exists(os.path.join(current_working_directory, "conf", "odoo.conf")):
        print("not in a project directory")
        return
    project = os.path.basename(current_working_directory)
    if not os.path.exists(os.path.join(current_working_directory, f"{project}.yaml")):
        print("no project manifest found")
        return
    # rm -f data/*
    # drop db
    return


# project rebuild
def project_rebuild():
    """Rebuild project with db and filestore of another project but with current addons"""
    print("project_rebuild")
    # TODO: project rebuild from one project to current project
    return


# ===================
# repo
# repo base
# repo base clone
def repo_base_clone():
    """repo base clone"""
    print("repo base clone")
    if not os.path.exists(repo_dir):
        os.makedirs(repo_dir)

    # community
    if os.path.exists(os.path.join(repo_dir, "odoo", ".git")):
        print("odoo community already exists")
    else:
        repo_url = "https://github.com/odoo/odoo"
        Repo.clone_from(repo_url, os.path.join(repo_dir, "odoo"))

    # enterprise
    if os.path.exists(os.path.join(repo_dir, "enterprise", ".git")):
        print("odoo enterprise already exists")
    else:
        repo_url = "https://github.com/odoo/enterprise"
        Repo.clone_from(repo_url, os.path.join(repo_dir, "odoo"))

    return


# repo base update
def repo_base_update():
    """repo base update"""
    print("repo base update")

    # community
    repo = Repo(os.path.join(repo_dir, "odoo"))
    for remote in repo.remotes:
        remote.fetch()
    refs = [
        ref.reference.name
        for ref in repo.remotes.origin.refs
        if ref.name == "origin/HEAD"
    ]
    branch_ref = refs[0] if len(refs) > 0 else ""
    branch = branch_ref.split("/")[1] if len(branch_ref.split("/")) == 2 else ""
    repo.git.checkout(branch)
    repo.remotes.origin.pull()

    # enterprise
    repo = Repo(os.path.join(repo_dir, "enterprise"))
    for remote in repo.remotes:
        remote.fetch()
    refs = [
        ref.reference.name
        for ref in repo.remotes.origin.refs
        if ref.name == "origin/HEAD"
    ]
    branch_ref = refs[0] if len(refs) > 0 else ""
    branch = branch_ref.split("/")[1] if len(branch_ref.split("/")) == 2 else ""
    repo.git.checkout(branch)
    repo.remotes.origin.pull()

    return


# repo branch
# repo branch clone
def repo_branch_clone(version):
    """repo branch clone"""
    print("repo branch clone")
    # branch
    if os.path.exists(os.path.join(repo_dir, version)):
        print(f"odoo {version} already exists")
    else:
        branch_dir = os.path.join(repo_dir, version)
        os.makedirs(branch_dir)

    # community
    if not os.path.exists(os.path.join(repo_dir, version, "odoo")):
        copytree(
            os.path.join(repo_dir, "odoo"),
            os.path.join(repo_dir, version, "odoo"),
        )
        repo = Repo(os.path.join(repo_dir, version, "odoo"))
        repo.git.checkout(version)
        repo.remotes.origin.pull()

    # enterprise
    if not os.path.exists(os.path.join(repo_dir, version, "enterprise")):
        copytree(
            os.path.join(repo_dir, "enterprise"),
            os.path.join(repo_dir, version, "enterprise"),
        )
        repo = Repo(os.path.join(repo_dir, version, "enterprise"))
        for remote in repo.remotes:
            remote.fetch()
        repo.git.checkout(version)
        repo.remotes.origin.pull()
    return


# repo branch update
def repo_branch_update(version):
    """repo branch update"""
    print("repo branch update")

    if not os.path.exists(os.path.join(repo_dir, version)):
        print(f"branch {version} does not exist, please clone the branch")
        return

    # community
    repo = Repo(os.path.join(repo_dir, "odoo"))
    for remote in repo.remotes:
        remote.fetch()
    repo.git.checkout(version)
    repo.remotes.origin.pull()

    # enterprise
    repo = Repo(os.path.join(repo_dir, "enterprise"))
    for remote in repo.remotes:
        remote.fetch()
    repo.git.checkout(version)
    repo.remotes.origin.pull()
    return


class ArgParser(argparse.ArgumentParser):
    """ArgParser modified to output help on error"""

    def error(self, message):
        print(f"error: {message}\n")
        self.print_help()


def main():
    """Odoo Administration Tool"""
    parser = ArgParser(
        prog="oda",
        description="Odoo Administration Tool",
        epilog="thanks for using %(prog)s!",
    )
    subparsers = parser.add_subparsers(
        dest="command", title="commands", help="commands"
    )

    # ===================
    # config        additional config options
    config_parser = subparsers.add_parser("config", help="additional config options")
    config_subparser = config_parser.add_subparsers(
        dest="config", title="config", help="additional config options", required=True
    )

    # config vscode
    config_subparser.add_parser(
        "vscode", help="Setup vscode settings and launch json files"
    )

    # config pyright
    config_subparser.add_parser("pyright", help="Setup pyright settings")

    # ===================
    # completions   Generate bash completions

    # ===================
    # kube
    kube_parser = subparsers.add_parser("kube", help="kubernetes management")
    kube_subparser = kube_parser.add_subparsers(
        dest="kube", title="kube", help="kubernetes management", required=True
    )

    # kube gen
    kube_gen_parser = kube_subparser.add_parser("gen", help="generate manifest")
    kube_gen_subparser = kube_gen_parser.add_subparsers(
        dest="gen",
        title="gen",
        help="generate manifest",
        required=True,
    )

    # kube gen postgres
    postgres_parser = kube_gen_subparser.add_parser("postgres", help="Postgresql Setup")
    postgres_parser.add_argument("version", help="PostgreSQL version")

    # kube gen odoo
    kube_gen_subparser.add_parser("odoo", help="Odoo Volume Manifest")

    # kube apply
    kube_apply_parser = kube_subparser.add_parser("apply", help="apply manifest")
    kube_apply_subparser = kube_apply_parser.add_subparsers(
        dest="apply",
        title="apply",
        help="apply manifest",
        required=True,
    )

    # kube apply postgres
    postgres_parser = kube_apply_subparser.add_parser(
        "postgres", help="Postgresql Start"
    )

    # kube apply odoo
    kube_apply_subparser.add_parser("odoo", help="Odoo Volume Start")

    # ===================
    # start         Start the instance
    subparsers.add_parser("start", help="Start the instance")

    # ===================
    # stop          Stop the instance
    subparsers.add_parser("stop", help="Stop the instance")

    # ===================
    # restart       Restart the instance
    subparsers.add_parser("restart", help="Restart the instance")

    # ===================
    # app management
    app_parser = subparsers.add_parser("app", help="app management")
    app_subparser = app_parser.add_subparsers(
        dest="app", title="app", help="app management", required=True
    )

    # app install
    install_parser = app_subparser.add_parser("install", help="Install module(s)")
    install_parser.add_argument("module", help="modules to install", nargs="+")

    # app upgrade
    upgrade_parser = app_subparser.add_parser("upgrade", help="Upgrade module(s)")
    upgrade_parser.add_argument(
        "module", help="modules to upgrade", default=["all"], nargs="*"
    )

    # ===================
    # logs          Follow the logs
    subparsers.add_parser("logs", help="Follow the logs")

    # ===================
    # scaffold      Generates an Odoo module skeleton in addons
    scaffold_parser = subparsers.add_parser(
        "scaffold", help="Generates an Odoo module skeleton in addons"
    )
    scaffold_parser.add_argument("module", help="%(prog)s module")

    # ===================
    # psql          Access the raw database
    subparsers.add_parser("psql", help="Access the raw database")

    # ===================
    # query         Query the database
    subparsers.add_parser("query", help="Query the database")

    # ===================
    # backup        Backup database filestore and addons
    subparsers.add_parser("backup", help="Backup database filestore and addons")

    # ===================
    # restore       Restore database and filestore or addons
    restore_parser = subparsers.add_parser(
        "restore", help="Restore database and filestore or addons"
    )
    restore_parser.add_argument("file", help="Path to backup file", nargs="+")

    # ===================
    # manifest      export import module manifest
    manifest_parser = subparsers.add_parser(
        "manifest", help="export import module manifest"
    )
    manifest_subparser = manifest_parser.add_subparsers(
        dest="manifest",
        title="manifest",
        help="export import module manifest",
        required=True,
    )

    # manifest export
    manifest_subparser.add_parser("export", help="export manifest.json")

    # manifest import
    manifest_import_parser = manifest_subparser.add_parser(
        "import", help="import manifest.json"
    )
    manifest_import_parser.add_argument("file", help="manifest file to read")

    # manifest remote
    manifest_remote_parser = manifest_subparser.add_parser(
        "remote", help="import manifest.json from backup file"
    )
    manifest_remote_parser.add_argument("file", help="backup file to read")

    # ===================
    # admin         Admin user management
    admin_parser = subparsers.add_parser("admin", help="Admin user management")
    admin_subparser = admin_parser.add_subparsers(
        dest="admin", title="admin", help="Admin user management", required=True
    )

    # admin user
    admin_user_parser = admin_subparser.add_parser("user", help="Odoo Admin username")
    admin_user_parser.add_argument("username", help="Odoo Admin username")

    # admin password
    admin_password_parser = admin_subparser.add_parser(
        "password", help="Odoo Admin password"
    )
    admin_password_parser.add_argument("password", help="Odoo Admin password")

    # ===================
    # project       Project level commands [CAUTION]
    project_parser = subparsers.add_parser(
        "project", help="Project level commands [CAUTION]"
    )
    project_subparser = project_parser.add_subparsers(
        dest="project",
        title="project",
        help="Project level commands [CAUTION]",
        required=True,
    )

    # project init
    project_init_parser = project_subparser.add_parser("init", help="init")
    project_init_parser.add_argument(
        "edition",
        choices=["community", "enterprise"],
        help="community or enterprise",
    )
    project_init_parser.add_argument(
        "version",
        help="Odoo Branch",
        choices=get_current_odoo_repos(),
    )
    project_init_parser.add_argument("projectname", help="Project Name")

    # project branch
    project_branch_parser = project_subparser.add_parser("branch", help="branch")
    project_branch_parser.add_argument(
        "edition",
        help="community or enterprise",
        choices=["community", "enterprise"],
    )
    project_branch_parser.add_argument("version", help="Odoo Branch")
    project_branch_parser.add_argument(
        "projectname",
        help="Project Name",
        choices=get_current_odoo_repos(),
    )
    project_branch_parser.add_argument("branch", help="Project Branch")
    project_branch_parser.add_argument("url", help="Project URL")

    # project reset
    project_subparser.add_parser("reset", help="reset")

    # ===================
    # repo          Odoo community and enterprise repository management
    repo_parser = subparsers.add_parser(
        "repo", help="Odoo community and enterprise repository management"
    )
    repo_subparser = repo_parser.add_subparsers(
        dest="repo",
        title="repo",
        help="Odoo community and enterprise repository management",
        required=True,
    )

    # repo base
    repo_base_parser = repo_subparser.add_parser("base", help="base")
    repo_base_subparser = repo_base_parser.add_subparsers(
        dest="base",
        title="base",
        help="Odoo community and enterprise repository management",
        required=True,
    )

    # repo base clone
    repo_base_subparser.add_parser("clone", help="clone the Odoo source repository")

    # repo base update
    repo_base_subparser.add_parser("update", help="update the Odoo source repository")

    # repo branch
    repo_branch_parser = repo_subparser.add_parser("branch", help="branch")
    repo_branch_subparser = repo_branch_parser.add_subparsers(
        dest="odoobranch",
        title="branch",
        help="Odoo community and enterprise branch management",
        required=True,
    )

    # repo branch clone
    repo_branch_clone_parser = repo_branch_subparser.add_parser(
        "clone", help="clone Odoo source repository"
    )
    repo_branch_clone_parser.add_argument("branch", help="branch name")

    # repo branch update
    repo_branch_update_parser = repo_branch_subparser.add_parser(
        "update", help="update Odoo version repository"
    )
    repo_branch_update_parser.add_argument("branch", help="branch name")

    parser.add_argument("--version", action="version", version=f"%(prog)s {SEMVER}")

    # ===================
    # process arguments
    args = parser.parse_args(args=None if sys.argv[1:] else ["--help"])

    if args.command == "config":
        if args.config == "vscode":
            config_vscode()
        elif args.config == "pyright":
            config_pyright()
    elif args.command == "kube":
        if args.kube == "gen":
            if args.gen == "postgres" and args.version:
                kube_gen_postgres(args.version)
            elif args.gen == "odoo":
                kube_gen_odoo()
        elif args.kube == "apply":
            if args.apply == "postgres":
                kube_apply_postgres()
            elif args.apply == "odoo":
                kube_apply_odoo()
    elif args.command == "start":
        start()
    elif args.command == "stop":
        stop()
    elif args.command == "restart":
        restart()
    elif args.command == "app":
        if args.app == "install" and args.module:
            app_install_upgrade(args.module, install=True)
        elif args.app == "upgrade" and args.module:
            app_install_upgrade(args.module, install=False)
    elif args.command == "logs":
        logs()
    elif args.command == "scaffold" and args.module:
        scaffold(args.module)
    elif args.command == "psql":
        psql()
    elif args.command == "query":
        query()
    elif args.command == "backup":
        backup()
    elif args.command == "restore" and args.file:
        restore(args.file)
    elif args.command == "manifest":
        if args.manifest == "export":
            manifest_export()
        elif args.manifest == "import" and args.file:
            manifest_import(args.file)
        elif args.manifest == "remote" and args.file:
            manifest_remote(args.file)
    elif args.command == "admin":
        if args.admin == "admin" and args.username:
            admin_user(args.username)
        elif args.admin == "password" and args.password:
            admin_password(args.password)
    elif args.command == "project":
        print(args.command, args)
        if (
            args.project == "init"
            and args.edition
            and args.version
            and args.projectname
        ):
            project_init(args.edition, args.version, args.projectname)
        elif (
            args.project == "branch"
            and args.edition
            and args.version
            and args.projectname
            and args.branch
            and args.url
        ):
            project_branch(
                args.edition, args.version, args.projectname, args.branch, args.url
            )
        elif args.project == "reset":
            project_reset()
    elif args.command == "repo":
        if args.repo == "base":
            if args.base == "clone":
                repo_base_clone()
            elif args.base == "update":
                repo_base_update()
        elif args.repo == "branch":
            if args.odoobranch == "clone":
                repo_branch_clone(args.branch)
            elif args.odoobranch == "update":
                repo_branch_update(args.branch)


if __name__ == "__main__":
    main()
