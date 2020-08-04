"""
    tests.integration.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Integration tests PyTest configuration/fixtures
"""
# pylint: disable=unused-argument,redefined-outer-name


import logging

import pytest
from tests.support.pytest.fixtures import *  # pylint: disable=unused-wildcard-import

log = logging.getLogger(__name__)


@pytest.fixture(scope="package", autouse=True)
def bridge_pytest_and_runtests_integration(
    bridge_pytest_and_runtests,
    # salt_syndic_master,
    # salt_syndic,
    salt_master,
    salt_minion,
):

    yield
