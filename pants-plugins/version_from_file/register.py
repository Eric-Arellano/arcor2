import requests
import json
from typing import Union

from packaging.version import parse, LegacyVersion, Version

from pants.backend.python.goals.setup_py import SetupKwargsRequest
from pants.engine.target import Target
from pants.engine.rules import collect_rules
from pants.engine.unions import UnionRule
from pants.backend.python.goals.setup_py import SetupKwargs
from pants.engine.rules import Get, rule
from pants.engine.fs import DigestContents, GlobMatchErrorBehavior, PathGlobs


URL_PATTERN = 'https://pypi.python.org/pypi/{package}/json'


class VersionException(Exception):
    pass


def remove_suffix(v, s):
    return v[:-len(s)] if v.endswith(s) else v


class CustomSetupKwargsRequest(SetupKwargsRequest):
    @classmethod
    def is_applicable(cls, _: Target) -> bool:
        return True


def rules():
    return [
        *collect_rules(),
        UnionRule(SetupKwargsRequest, CustomSetupKwargsRequest),
    ]


@rule
async def setup_kwargs_plugin(request: CustomSetupKwargsRequest) -> SetupKwargs:

    digest_contents = await Get(
        DigestContents,
        PathGlobs(
            [f"{request.target.address.spec_path}/VERSION"],
            description_of_origin="`setup_py()` plugin",
            glob_match_error_behavior=GlobMatchErrorBehavior.error,
        ),
    )
    version = digest_contents[0].content.decode().strip()

    package_name = remove_suffix(request.target.address.target_name, "_dist")  # TODO this is hacky / fragile

    local_version = parse(version)
    if isinstance(local_version, LegacyVersion):
        raise ValueError(f"Version {local_version} of {package_name} is not valid.")

    return SetupKwargs(
        {**request.explicit_kwargs, "version": version},
        address=request.target.address
    )
