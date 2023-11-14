#!/usr/bin/env python3
import yaml
import base64
import subprocess
import argparse
import os
import sys
from pathlib import Path
from git import Repo
from distutils.dir_util import copy_tree

# from kubernetes import client, config

SEMVER = "0.1.0"
config_dir = os.path.join(Path.home(), ".config")
local_dir = os.path.join(Path.home(), ".local")
manifests = os.path.join(config_dir, "oda/manifests")
storage = os.path.join(local_dir, "oda")
repo_dir = os.path.join(Path.home(), "workspace/repos/odoo")
project = os.path.join(Path.home(), "workspace/odoo")

# config.load_kube_config()
# v1 = client.CoreV1Api()


# ===================
# ===================
# kubenetes manifest generation
def gen_pv(volume, acl, size, path):
    """Generate a PersistentVolume"""
    config = {
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
    yaml_string = yaml.dump(config)
    return "---\n" + yaml_string


def gen_pvc(volume, acl, size):
    """Generate a PersistentVolumeClaim"""
    config = {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {"name": f"{volume}-pvc"},
        "spec": {
            "accessModes": [acl],
            "resources": {"requests": {"storage": size}},
            "volumeName": f"{volume}-pv",
        },
    }
    yaml_string = yaml.dump(config)
    return "---\n" + yaml_string


def gen_secret(name, password):
    """Generate a Secrets"""
    config = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": f"{name}-secret"},
        "type": "Opaque",
        "data": {
            "password": base64.b64encode(bytes(password, "utf-8")).decode(),
        },
    }
    yaml_string = yaml.dump(config)
    return "---\n" + yaml_string


def gen_service(name, port_list):
    """Generate a Service"""
    port_dict = []
    for port_tuple in port_list:
        port_name, port = port_tuple[0], port_tuple[1]
        port_dict.append({"name": port_name, "port": port})

    config = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": name,
            "labels": {"app": name},
        },
        "spec": {"selector": {"app": name}, "ports": port_dict, "clusterIP": "None"},
    }
    yaml_string = yaml.dump(config)
    return "---\n" + yaml_string


def gen_ingress(name, portpath):
    """Generate Ingress to Service"""
    # ---
    # apiVersion: networking.k8s.io/v1
    # kind: Ingress
    # metadata:
    #   name: quest17
    #   annotations:
    #     ingress.kubernetes.io/rewrite-target: /
    # spec:
    #   rules:
    #     - host: "quest17.local"
    #       http:
    #         paths:
    #           - path: "/websocket"
    #             pathType: Exact
    #             backend:
    #               service:
    #                 name: quest17
    #                 port:
    #                   number: 8072
    #           - path: "/"
    #             pathType: Prefix
    #             backend:
    #               service:
    #                 name: quest17
    #                 port:
    #                   number: 8069
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
    config = {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "metadata": {
            "name": name,
            "annotations": {"ingress.kubernetes.io/rewrite-target": "/"},
        },
        "spec": {"rules": [{"host": f"{name}.local", "http": {"paths": port_dict}}]},
    }
    yaml_string = yaml.dump(config)
    return "---\n" + yaml_string


def gen_deployment(name, imagename, image, ports, volumes, globalvols):
    """Generate Deployment"""
    # apiVersion: apps/v1
    # kind: Deployment
    # metadata:
    #   name: quest17
    #   labels:
    #     app: quest17
    # spec:
    #   replicas: 1
    #   selector:
    #     matchLabels:
    #       app: quest17
    #   template:
    #     metadata:
    #       labels:
    #         app: quest17
    #     spec:
    #       containers:
    #         - name: odoobase
    #           image: ghcr.io/ppreeper/odoobase:main
    #           imagePullPolicy: Always
    #           resources:
    #             requests:
    #               memory: 256Mi
    #               cpu: 200m
    #             limits:
    #               memory: 512Mi
    #               cpu: 500m
    #           ports:
    #             - containerPort: 8069
    #             - containerPort: 8072
    #           volumeMounts:
    #             - mountPath: /opt/odoo/conf
    #               name: quest17-conf
    #             - mountPath: /opt/odoo/addons
    #               name: quest17-addons
    #             - mountPath: /opt/odoo/data
    #               name: quest17-data
    #             - mountPath: /opt/odoo/backups
    #               name: quest17-backups
    #             - mountPath: /opt/odoo/odoo
    #               name: odoo17
    #             - mountPath: /opt/odoo/enterprise
    #               name: enterprise17
    #       volumes:
    #         - name: quest17-conf
    #           persistentVolumeClaim:
    #             claimName: quest17-conf-pvc
    #         - name: quest17-addons
    #           persistentVolumeClaim:
    #             claimName: quest17-addons-pvc
    #         - name: quest17-data
    #           persistentVolumeClaim:
    #             claimName: quest17-data-pvc
    #         - name: quest17-backups
    #           persistentVolumeClaim:
    #             claimName: quest17-backups-pvc
    #         - name: odoo17
    #           persistentVolumeClaim:
    #             claimName: odoo17-pvc
    #         - name: enterprise17
    #           persistentVolumeClaim:
    #             claimName: enterprise17-pvc
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

    config = {
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
                            "name": imagename,
                            "image": image,
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
    yaml_string = yaml.dump(config)
    return "---\n" + yaml_string


def gen_postgres_statefulset(name, version, image, port_list):
    """Generate StatefulSet"""
    port_dict = []
    for port_tuple in port_list:
        port_name, port = port_tuple[0], port_tuple[1]
        port_dict.append({"name": port_name, "containerPort": port})
    config = {
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
    yaml_string = yaml.dump(config)
    return "---\n" + yaml_string


def gen_configmap(name, kv_list):
    data = {}
    for kv in kv_list:
        data[kv[0]] = kv[1]
    config = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": name,
        },
        "data": data,
    }
    yaml_string = yaml.dump(config)
    return "---\n" + yaml_string


# ===================
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


# kube gen odoo
def kube_gen_odoo():
    """Generate Odoo Volume Manifest"""
    print("odoo manifest")
    if not os.path.exists(manifests):
        os.makedirs(manifests)
    odoo_manifest = os.path.join(manifests, "odoo.yaml")
    dirnames = os.listdir(repo_dir)
    dirnames = [dir for dir in dirnames if dir != "odoo"]
    dirnames = [dir for dir in dirnames if dir != "enterprise"]
    with open(odoo_manifest, "w", encoding="UTF-8") as odoo:
        for dirname in dirnames:
            dirs = os.listdir(os.path.join(repo_dir, dirname))
            for d in dirs:
                odoo.write(
                    gen_pv(
                        f"{d}-{dirname}",
                        "ReadOnlyMany",
                        "10Gi",
                        os.path.join(repo_dir, dirname, d),
                    )
                )
                odoo.write(
                    gen_pvc(
                        f"{d}-{dirname}",
                        "ReadOnlyMany",
                        "10Gi",
                    )
                )
    return


def kube_apply_odoo():
    """Start Odoo Volumes"""
    print("kube_apply_odoo")
    odoo_manifest = os.path.join(manifests, "odoo.yaml")
    subprocess.run(["kubectl", "apply", "-f", odoo_manifest], check=True)
    return


def project_init(project, edition, branch, projectname):
    """Initialize Project"""
    return


def project_branch(project, edition, branch, projectname):
    """Initialize Project"""
    return


def project_reset():
    """Project Reset: drop database and clear the data directory"""
    return


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
        copy_tree(
            os.path.join(repo_dir, "odoo"),
            os.path.join(repo_dir, version, "odoo"),
        )
        repo = Repo(os.path.join(repo_dir, version, "odoo"))
        repo.git.checkout(version)
        repo.remotes.origin.pull()

    # enterprise
    if not os.path.exists(os.path.join(repo_dir, version, "enterprise")):
        copy_tree(
            os.path.join(repo_dir, "enterprise"),
            os.path.join(repo_dir, version, "enterprise"),
        )
        repo = Repo(os.path.join(repo_dir, version, "enterprise"))
        for remote in repo.remotes:
            remote.fetch()
        repo.git.checkout(version)
        repo.remotes.origin.pull()
    return


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

    # app init
    app_subparser.add_parser("init", help="initialize the database")

    # app install
    install_parser = app_subparser.add_parser("install", help="Install module(s)")
    install_parser.add_argument("module", help="modules to install", nargs="+")

    # app upgrade
    upgrade_parser = app_subparser.add_parser("upgrade", help="Upgrade module(s)")
    upgrade_parser.add_argument(
        "module", help="modules to upgrade", default="all", nargs="*"
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
    project_init_parser.add_argument("version", help="Odoo Branch")
    project_init_parser.add_argument("projectname", help="Project Name")

    # project branch
    project_branch_parser = project_subparser.add_parser("branch", help="branch")
    project_branch_parser.add_argument(
        "edition",
        choices=["community", "enterprise"],
        help="community or enterprise",
    )
    project_branch_parser.add_argument("version", help="Odoo Branch")
    project_branch_parser.add_argument("projectname", help="Project Name")
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
        print(args.command, args)
        if args.config == "vscode":
            print(args.config)
        elif args.config == "pyright":
            print(args.config)
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
        print(args.command, args)
    elif args.command == "stop":
        print(args.command, args)
    elif args.command == "restart":
        print(args.command, args)
    elif args.command == "app":
        print(args.command, args)
        if args.app == "init":
            print(args.app)
        elif args.app == "install":
            print(args.app)
        elif args.app == "upgrade":
            print(args.app)
    elif args.command == "logs":
        print(args.command, args)
    elif args.command == "scaffold":
        print(args.command, args)
    elif args.command == "psql":
        print(args.command, args)
    elif args.command == "query":
        print(args.command, args)
    elif args.command == "backup":
        print(args.command, args)
    elif args.command == "restore":
        print(args.command, args)
    elif args.command == "manifest":
        print(args.command, args)
        if args.manifest == "export":
            print(args.manifest)
        elif args.manifest == "import":
            print(args.manifest)
        elif args.manifest == "remote":
            print(args.manifest)
    elif args.command == "admin":
        print(args.command, args)
        if args.admin == "admin":
            print(args.admin, args.username)
        elif args.admin == "password":
            print(args.admin, args.password)
    elif args.command == "project":
        print(args.command, args)
        if args.project == "init":
            print(args.project, args.edition, args.branch, args.projectname)
        elif args.project == "branch":
            print(args.project)
        elif args.project == "reset":
            print(args.project)
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
