# -*- coding: utf-8 -*-
'''
    tests.pytests.integration.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    PyTest fixtures
'''
# pylint: disable=unused-argument,redefined-outer-name

from __future__ import absolute_import, unicode_literals

import pytest
from tests.support.pytest.fixtures import *  # pylint: disable=unused-wildcard-import


@pytest.fixture(scope="package")
def salt_master(request, salt_factories):
    return salt_factories.spawn_master(request, "master")


@pytest.fixture(scope="package")
def salt_minion(request, salt_factories, salt_master):
    proc = salt_factories.spawn_minion(request, "minion", master_id="master")
    # Sync All
    salt_call_cli = salt_factories.get_salt_call_cli("minion")
    ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
    assert ret.exitcode == 0, ret
    return proc


@pytest.fixture(scope="package")
def salt_sub_minion(request, salt_factories, salt_master):
    proc = salt_factories.spawn_minion(request, "sub_minion", master_id="master")
    # Sync All
    salt_call_cli = salt_factories.get_salt_call_cli("sub_minion")
    ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
    assert ret.exitcode == 0, ret
    return proc


@pytest.fixture(scope="package", autouse=True)
def bridge_pytest_and_runtests_(bridge_pytest_and_runtests):
    # We really just want to override this fixture in order not to automatically start daemons
    # and rely on fixtures
    yield


@pytest.fixture(scope="package")
def salt_cli(salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_cli(salt_master.config["id"])


@pytest.fixture(scope="package")
def salt_cp_cli(salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_cp_cli(salt_master.config["id"])


@pytest.fixture(scope="package")
def salt_key_cli(salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_key_cli(salt_master.config["id"])


@pytest.fixture(scope="package")
def salt_run_cli(salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_run_cli(salt_master.config["id"])


@pytest.fixture(scope="package")
def salt_call_cli(salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_call_cli(salt_minion.config["id"])
