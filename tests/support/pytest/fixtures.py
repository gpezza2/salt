"""
    tests.support.pytest.fixtures
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    The purpose of this fixtures module is provide the same set of available fixture for the old unittest
    test suite under ``test/integration``, ``tests/multimaster`` and ``tests/unit``.

    Please refrain from adding fixtures to this module and instead add them to the appropriate
    ``conftest.py`` file.
"""
import logging
import os
import shutil
import stat
import sys
import textwrap

import pytest
import salt.utils.files
import saltfactories.utils.ports
from salt.serializers import yaml
from salt.utils.immutabletypes import freeze
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


def _get_virtualenv_binary_path():
    try:
        return _get_virtualenv_binary_path.__virtualenv_binary__
    except AttributeError:
        # Under windows we can't seem to properly create a virtualenv off of another
        # virtualenv, we can on linux but we will still point to the virtualenv binary
        # outside the virtualenv running the test suite, if that's the case.
        try:
            real_prefix = sys.real_prefix
            # The above attribute exists, this is a virtualenv
            if salt.utils.platform.is_windows():
                virtualenv_binary = os.path.join(
                    real_prefix, "Scripts", "virtualenv.exe"
                )
            else:
                # We need to remove the virtualenv from PATH or we'll get the virtualenv binary
                # from within the virtualenv, we don't want that
                path = os.environ.get("PATH")
                if path is not None:
                    path_items = path.split(os.pathsep)
                    for item in path_items[:]:
                        if item.startswith(sys.base_prefix):
                            path_items.remove(item)
                    os.environ["PATH"] = os.pathsep.join(path_items)
                virtualenv_binary = salt.utils.path.which("virtualenv")
                if path is not None:
                    # Restore previous environ PATH
                    os.environ["PATH"] = path
                if not virtualenv_binary.startswith(real_prefix):
                    virtualenv_binary = None
            if virtualenv_binary and not os.path.exists(virtualenv_binary):
                # It doesn't exist?!
                virtualenv_binary = None
        except AttributeError:
            # We're not running inside a virtualenv
            virtualenv_binary = None
        _get_virtualenv_binary_path.__virtualenv_binary__ = virtualenv_binary
        return virtualenv_binary


@pytest.fixture(scope="session")
def salt_ssh_sshd_port():
    return saltfactories.utils.ports.get_unused_localhost_port()


@pytest.fixture(scope="session")
def integration_files_dir(salt_factories):
    """
    Fixture which returns the salt integration files directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = salt_factories.root_dir / "integration-files"
    dirname.mkdir(exist_ok=True)
    return dirname


@pytest.fixture(scope="session")
def state_tree_root_dir(integration_files_dir):
    """
    Fixture which returns the salt state tree root directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = integration_files_dir / "state-tree"
    dirname.mkdir(exist_ok=True)
    return dirname


@pytest.fixture(scope="session")
def pillar_tree_root_dir(integration_files_dir):
    """
    Fixture which returns the salt pillar tree root directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = integration_files_dir / "pillar-tree"
    dirname.mkdir(exist_ok=True)
    return dirname


@pytest.fixture(scope="session")
def base_env_state_tree_root_dir(state_tree_root_dir):
    """
    Fixture which returns the salt base environment state tree directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = state_tree_root_dir / "base"
    dirname.mkdir(exist_ok=True)
    RUNTIME_VARS.TMP_STATE_TREE = str(dirname.resolve())
    RUNTIME_VARS.TMP_BASEENV_STATE_TREE = RUNTIME_VARS.TMP_STATE_TREE
    return dirname


@pytest.fixture(scope="session")
def prod_env_state_tree_root_dir(state_tree_root_dir):
    """
    Fixture which returns the salt prod environment state tree directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = state_tree_root_dir / "prod"
    dirname.mkdir(exist_ok=True)
    RUNTIME_VARS.TMP_PRODENV_STATE_TREE = str(dirname.resolve())
    return dirname


@pytest.fixture(scope="session")
def base_env_pillar_tree_root_dir(pillar_tree_root_dir):
    """
    Fixture which returns the salt base environment pillar tree directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = pillar_tree_root_dir / "base"
    dirname.mkdir(exist_ok=True)
    RUNTIME_VARS.TMP_PILLAR_TREE = str(dirname.resolve())
    RUNTIME_VARS.TMP_BASEENV_PILLAR_TREE = RUNTIME_VARS.TMP_PILLAR_TREE
    return dirname


@pytest.fixture(scope="session")
def prod_env_pillar_tree_root_dir(pillar_tree_root_dir):
    """
    Fixture which returns the salt prod environment pillar tree directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = pillar_tree_root_dir / "prod"
    dirname.mkdir(exist_ok=True)
    RUNTIME_VARS.TMP_PRODENV_PILLAR_TREE = str(dirname.resolve())
    return dirname


@pytest.fixture(scope="session")
def salt_syndic_master(request, salt_factories, salt_ssh_sshd_port):
    root_dir = salt_factories._get_root_dir_for_daemon("syndic_master")
    conf_dir = root_dir / "conf"
    conf_dir.mkdir(exist_ok=True)

    with salt.utils.files.fopen(
        os.path.join(RUNTIME_VARS.CONF_DIR, "syndic_master")
    ) as rfh:
        config_defaults = yaml.deserialize(rfh.read())

        tests_known_hosts_file = str(root_dir / "salt_ssh_known_hosts")
        with salt.utils.files.fopen(tests_known_hosts_file, "w") as known_hosts:
            known_hosts.write("")

    config_defaults["root_dir"] = str(root_dir)
    config_defaults["known_hosts_file"] = tests_known_hosts_file
    config_defaults["syndic_master"] = "localhost"
    config_defaults["transport"] = request.config.getoption("--transport")

    config_overrides = {}
    ext_pillar = []
    if salt.utils.platform.is_windows():
        ext_pillar.append(
            {"cmd_yaml": "type {}".format(os.path.join(RUNTIME_VARS.FILES, "ext.yaml"))}
        )
    else:
        ext_pillar.append(
            {"cmd_yaml": "cat {}".format(os.path.join(RUNTIME_VARS.FILES, "ext.yaml"))}
        )

    # We need to copy the extension modules into the new master root_dir or
    # it will be prefixed by it
    extension_modules_path = str(root_dir / "extension_modules")
    if not os.path.exists(extension_modules_path):
        shutil.copytree(
            os.path.join(RUNTIME_VARS.FILES, "extension_modules"),
            extension_modules_path,
        )

    # Copy the autosign_file to the new  master root_dir
    autosign_file_path = str(root_dir / "autosign_file")
    shutil.copyfile(
        os.path.join(RUNTIME_VARS.FILES, "autosign_file"), autosign_file_path
    )
    # all read, only owner write
    autosign_file_permissions = (
        stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR
    )
    os.chmod(autosign_file_path, autosign_file_permissions)

    config_overrides.update(
        {
            "ext_pillar": ext_pillar,
            "extension_modules": extension_modules_path,
            "file_roots": {
                "base": [
                    RUNTIME_VARS.TMP_STATE_TREE,
                    os.path.join(RUNTIME_VARS.FILES, "file", "base"),
                ],
                # Alternate root to test __env__ choices
                "prod": [
                    RUNTIME_VARS.TMP_PRODENV_STATE_TREE,
                    os.path.join(RUNTIME_VARS.FILES, "file", "prod"),
                ],
            },
            "pillar_roots": {
                "base": [
                    RUNTIME_VARS.TMP_PILLAR_TREE,
                    os.path.join(RUNTIME_VARS.FILES, "pillar", "base"),
                ],
                "prod": [RUNTIME_VARS.TMP_PRODENV_PILLAR_TREE],
            },
        }
    )

    # We also need a salt-ssh roster config file
    roster_path = str(conf_dir / "roster")
    roster_contents = textwrap.dedent(
        """\
        localhost:
          host: 127.0.0.1
          port: {}
          user: {}
          mine_functions:
            test.arg: ['itworked']
        """.format(
            salt_ssh_sshd_port, RUNTIME_VARS.RUNNING_TESTS_USER
        )
    )
    log.debug(
        "Writing to configuration file %s. Configuration:\n%s",
        roster_path,
        roster_contents,
    )
    with salt.utils.files.fopen(roster_path, "w") as wfh:
        wfh.write(roster_contents)

    factory = salt_factories.get_salt_master_daemon(
        "syndic_master",
        order_masters=True,
        config_defaults=config_defaults,
        config_overrides=config_overrides,
    )
    # We don't yet want the syndic machinery to start
    # with factory.started():
    #    yield factory
    return factory


@pytest.fixture(scope="session")
def salt_syndic(request, salt_factories, salt_syndic_master):
    config_defaults = {"master": None, "minion": None, "syndic": None}
    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "syndic")) as rfh:
        opts = yaml.deserialize(rfh.read())

        opts["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
        opts["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
        opts["transport"] = request.config.getoption("--transport")
        config_defaults["syndic"] = opts
    factory = salt_syndic_master.get_salt_syndic_daemon(
        "syndic", config_defaults=config_defaults
    )
    # We don't yet want the syndic machinery to start
    # with factory.started():
    #    yield factory
    return factory


@pytest.fixture(scope="session")
def salt_master(request, salt_factories, salt_syndic_master, salt_ssh_sshd_port):
    root_dir = salt_factories._get_root_dir_for_daemon("master")
    conf_dir = root_dir / "conf"
    conf_dir.mkdir(exist_ok=True)

    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "master")) as rfh:
        config_defaults = yaml.deserialize(rfh.read())

        tests_known_hosts_file = str(root_dir / "salt_ssh_known_hosts")
        with salt.utils.files.fopen(tests_known_hosts_file, "w") as known_hosts:
            known_hosts.write("")

    config_defaults["root_dir"] = str(root_dir)
    config_defaults["known_hosts_file"] = tests_known_hosts_file
    config_defaults["syndic_master"] = "localhost"
    config_defaults["transport"] = request.config.getoption("--transport")
    config_defaults["reactor"] = [
        {"salt/test/reactor": [os.path.join(RUNTIME_VARS.FILES, "reactor-test.sls")]}
    ]

    config_overrides = {}
    ext_pillar = []
    if salt.utils.platform.is_windows():
        ext_pillar.append(
            {"cmd_yaml": "type {}".format(os.path.join(RUNTIME_VARS.FILES, "ext.yaml"))}
        )
    else:
        ext_pillar.append(
            {"cmd_yaml": "cat {}".format(os.path.join(RUNTIME_VARS.FILES, "ext.yaml"))}
        )
    ext_pillar.append(
        {
            "file_tree": {
                "root_dir": os.path.join(RUNTIME_VARS.PILLAR_DIR, "base", "file_tree"),
                "follow_dir_links": False,
                "keep_newline": True,
            }
        }
    )
    config_overrides["pillar_opts"] = True

    # We need to copy the extension modules into the new master root_dir or
    # it will be prefixed by it
    extension_modules_path = str(root_dir / "extension_modules")
    if not os.path.exists(extension_modules_path):
        shutil.copytree(
            os.path.join(RUNTIME_VARS.FILES, "extension_modules"),
            extension_modules_path,
        )

    # Copy the autosign_file to the new  master root_dir
    autosign_file_path = str(root_dir / "autosign_file")
    shutil.copyfile(
        os.path.join(RUNTIME_VARS.FILES, "autosign_file"), autosign_file_path
    )
    # all read, only owner write
    autosign_file_permissions = (
        stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR
    )
    os.chmod(autosign_file_path, autosign_file_permissions)

    config_overrides.update(
        {
            "ext_pillar": ext_pillar,
            "extension_modules": extension_modules_path,
            "file_roots": {
                "base": [
                    RUNTIME_VARS.TMP_STATE_TREE,
                    os.path.join(RUNTIME_VARS.FILES, "file", "base"),
                ],
                # Alternate root to test __env__ choices
                "prod": [
                    RUNTIME_VARS.TMP_PRODENV_STATE_TREE,
                    os.path.join(RUNTIME_VARS.FILES, "file", "prod"),
                ],
            },
            "pillar_roots": {
                "base": [
                    RUNTIME_VARS.TMP_PILLAR_TREE,
                    os.path.join(RUNTIME_VARS.FILES, "pillar", "base"),
                ],
                "prod": [RUNTIME_VARS.TMP_PRODENV_PILLAR_TREE],
            },
        }
    )

    # Let's copy over the test cloud config files and directories into the running master config directory
    for entry in os.listdir(RUNTIME_VARS.CONF_DIR):
        if not entry.startswith("cloud"):
            continue
        source = os.path.join(RUNTIME_VARS.CONF_DIR, entry)
        dest = str(conf_dir / entry)
        if os.path.isdir(source):
            shutil.copytree(source, dest)
        else:
            shutil.copyfile(source, dest)

    # We also need a salt-ssh roster config file
    roster_path = str(conf_dir / "roster")
    roster_contents = textwrap.dedent(
        """\
        localhost:
          host: 127.0.0.1
          port: {}
          user: {}
          mine_functions:
            test.arg: ['itworked']
        """.format(
            salt_ssh_sshd_port, RUNTIME_VARS.RUNNING_TESTS_USER
        )
    )
    log.debug(
        "Writing to configuration file %s. Configuration:\n%s",
        roster_path,
        roster_contents,
    )
    with salt.utils.files.fopen(roster_path, "w") as wfh:
        wfh.write(roster_contents)

    factory = salt_syndic_master.get_salt_master_daemon(
        "master", config_defaults=config_defaults, config_overrides=config_overrides,
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="session")
def salt_minion(request, salt_master):
    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "minion")) as rfh:
        config_defaults = yaml.deserialize(rfh.read())
    config_defaults["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
    config_defaults["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
    config_defaults["transport"] = request.config.getoption("--transport")

    config_overrides = {
        "file_roots": {
            "base": [
                RUNTIME_VARS.TMP_STATE_TREE,
                os.path.join(RUNTIME_VARS.FILES, "file", "base"),
            ],
            # Alternate root to test __env__ choices
            "prod": [
                RUNTIME_VARS.TMP_PRODENV_STATE_TREE,
                os.path.join(RUNTIME_VARS.FILES, "file", "prod"),
            ],
        },
        "pillar_roots": {
            "base": [
                RUNTIME_VARS.TMP_PILLAR_TREE,
                os.path.join(RUNTIME_VARS.FILES, "pillar", "base"),
            ],
            "prod": [RUNTIME_VARS.TMP_PRODENV_PILLAR_TREE],
        },
    }
    virtualenv_binary = _get_virtualenv_binary_path()
    if virtualenv_binary:
        config_overrides["venv_bin"] = virtualenv_binary
    factory = salt_master.get_salt_minion_daemon(
        "minion", config_defaults=config_defaults, config_overrides=config_overrides,
    )
    with factory.started():
        # Sync All
        salt_call_cli = factory.get_salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.exitcode == 0, ret
        yield factory


@pytest.fixture(scope="session")
def salt_sub_minion(request, salt_master):
    with salt.utils.files.fopen(
        os.path.join(RUNTIME_VARS.CONF_DIR, "sub_minion")
    ) as rfh:
        config_defaults = yaml.deserialize(rfh.read())
    config_defaults["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
    config_defaults["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
    config_defaults["transport"] = request.config.getoption("--transport")

    config_overrides = {
        "file_roots": {
            "base": [
                RUNTIME_VARS.TMP_STATE_TREE,
                os.path.join(RUNTIME_VARS.FILES, "file", "base"),
            ],
            # Alternate root to test __env__ choices
            "prod": [
                RUNTIME_VARS.TMP_PRODENV_STATE_TREE,
                os.path.join(RUNTIME_VARS.FILES, "file", "prod"),
            ],
        },
        "pillar_roots": {
            "base": [
                RUNTIME_VARS.TMP_PILLAR_TREE,
                os.path.join(RUNTIME_VARS.FILES, "pillar", "base"),
            ],
            "prod": [RUNTIME_VARS.TMP_PRODENV_PILLAR_TREE],
        },
    }
    virtualenv_binary = _get_virtualenv_binary_path()
    if virtualenv_binary:
        config_overrides["venv_bin"] = virtualenv_binary
    factory = salt_master.get_salt_minion_daemon(
        "sub_minion",
        config_defaults=config_defaults,
        config_overrides=config_overrides,
    )
    with factory.started():
        # Sync All
        salt_call_cli = factory.get_salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.exitcode == 0, ret
        yield factory


@pytest.fixture(scope="package")
def salt_proxy(request, salt_factories, salt_master):
    proxy_minion_id = "proxytest"
    root_dir = salt_factories._get_root_dir_for_daemon(proxy_minion_id)
    conf_dir = root_dir / "conf"
    conf_dir.mkdir(parents=True, exist_ok=True)
    RUNTIME_VARS.TMP_PROXY_CONF_DIR = str(conf_dir)

    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "proxy")) as rfh:
        config_defaults = yaml.deserialize(rfh.read())

    config_defaults["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
    config_defaults["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
    config_defaults["transport"] = request.config.getoption("--transport")
    config_defaults["root_dir"] = str(root_dir)

    def remove_stale_key(proxy_key_file):
        log.debug("Proxy minion %r KEY FILE: %s", proxy_minion_id, proxy_key_file)
        if os.path.exists(proxy_key_file):
            os.unlink(proxy_key_file)
        else:
            log.warning("The proxy minion key was not found at %s", proxy_key_file)

    factory = salt_master.get_proxy_minion_daemon(
        proxy_minion_id, config_defaults=config_defaults
    )
    proxy_key_file = os.path.join(
        salt_master.config["pki_dir"], "minions", proxy_minion_id
    )
    factory.register_after_terminate_callback(remove_stale_key, proxy_key_file)
    with factory.started():
        yield factory


@pytest.fixture(scope="package")
def salt_cli(salt_master):
    return salt_master.get_salt_cli()


@pytest.fixture(scope="package")
def salt_cp_cli(salt_master):
    return salt_master.get_salt_cp_cli()


@pytest.fixture(scope="package")
def salt_key_cli(salt_master):
    return salt_master.get_salt_key_cli()


@pytest.fixture(scope="package")
def salt_run_cli(salt_master):
    return salt_master.get_salt_run_cli()


@pytest.fixture(scope="package")
def salt_call_cli(salt_minion):
    return salt_minion.get_salt_call_cli()


@pytest.fixture(scope="session", autouse=True)
def bridge_pytest_and_runtests(
    reap_stray_processes,
    base_env_state_tree_root_dir,
    prod_env_state_tree_root_dir,
    base_env_pillar_tree_root_dir,
    prod_env_pillar_tree_root_dir,
    salt_factories,
    salt_syndic_master,
    salt_syndic,
    salt_master,
    salt_minion,
    salt_sub_minion,
    sshd_config_dir,
):
    # Make sure unittest2 uses the pytest generated configuration
    RUNTIME_VARS.RUNTIME_CONFIGS["master"] = freeze(salt_master.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["minion"] = freeze(salt_minion.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["sub_minion"] = freeze(salt_sub_minion.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["syndic_master"] = freeze(salt_syndic_master.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["syndic"] = freeze(salt_syndic.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["client_config"] = freeze(
        salt.config.client_config(salt_master.config["conf_file"])
    )

    # Make sure unittest2 classes know their paths
    RUNTIME_VARS.TMP_ROOT_DIR = str(salt_factories.root_dir.resolve())
    RUNTIME_VARS.TMP_CONF_DIR = os.path.dirname(salt_master.config["conf_file"])
    RUNTIME_VARS.TMP_MINION_CONF_DIR = os.path.dirname(salt_minion.config["conf_file"])
    RUNTIME_VARS.TMP_SUB_MINION_CONF_DIR = os.path.dirname(
        salt_sub_minion.config["conf_file"]
    )
    RUNTIME_VARS.TMP_SYNDIC_MASTER_CONF_DIR = os.path.dirname(
        salt_syndic_master.config["conf_file"]
    )
    RUNTIME_VARS.TMP_SYNDIC_MINION_CONF_DIR = os.path.dirname(
        salt_syndic.config["conf_file"]
    )
    RUNTIME_VARS.TMP_SSH_CONF_DIR = sshd_config_dir


@pytest.fixture(scope="session")
def sshd_config_dir(salt_factories):
    config_dir = salt_factories._get_root_dir_for_daemon("sshd")
    yield config_dir
    shutil.rmtree(str(config_dir), ignore_errors=True)


@pytest.fixture(scope="session")
def sshd_server(salt_factories, salt_ssh_sshd_port, sshd_config_dir):
    sshd_config_dict = {
        "Protocol": "2",
        # Turn strict modes off so that we can operate in /tmp
        "StrictModes": "no",
        # Logging
        "SyslogFacility": "AUTH",
        "LogLevel": "INFO",
        # Authentication:
        "LoginGraceTime": "120",
        "PermitRootLogin": "without-password",
        "PubkeyAuthentication": "yes",
        # Don't read the user's ~/.rhosts and ~/.shosts files
        "IgnoreRhosts": "yes",
        "HostbasedAuthentication": "no",
        # To enable empty passwords, change to yes (NOT RECOMMENDED)
        "PermitEmptyPasswords": "no",
        # Change to yes to enable challenge-response passwords (beware issues with
        # some PAM modules and threads)
        "ChallengeResponseAuthentication": "no",
        # Change to no to disable tunnelled clear text passwords
        "PasswordAuthentication": "no",
        "X11Forwarding": "no",
        "X11DisplayOffset": "10",
        "PrintMotd": "no",
        "PrintLastLog": "yes",
        "TCPKeepAlive": "yes",
        "AcceptEnv": "LANG LC_*",
        "Subsystem": "sftp /usr/lib/openssh/sftp-server",
        "UsePAM": "yes",
    }
    factory = salt_factories.get_sshd_daemon(
        "sshd",
        listen_port=salt_ssh_sshd_port,
        sshd_config_dict=sshd_config_dict,
        config_dir=sshd_config_dir,
    )
    with factory.started():
        yield factory


# Only allow star importing the functions defined in this module
__all__ = [
    name
    for (name, func) in locals().items()
    if getattr(func, "__module__", None) == __name__
]
