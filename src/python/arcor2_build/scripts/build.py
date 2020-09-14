#!/usr/bin/env python3

import argparse
import json
import logging
import os
import shutil
import stat
import tempfile
from datetime import datetime, timezone
from typing import Set, Tuple, Union

import humps
from apispec import APISpec  # type: ignore
from apispec_webframeworks.flask import FlaskPlugin  # type: ignore
from flask import Flask, Response, request, send_file
from flask_cors import CORS  # type: ignore
from flask_swagger_ui import get_swaggerui_blueprint  # type: ignore

import arcor2_build
from arcor2.cached import CachedProject, CachedScene
from arcor2.clients import persistent_storage as ps
from arcor2.data.execution import PackageMeta
from arcor2.data.object_type import ObjectModel, ObjectType
from arcor2.helpers import logger_formatter
from arcor2.object_types.utils import base_from_source, built_in_types_names
from arcor2.source import SourceException
from arcor2.source.utils import parse
from arcor2_build.source.logic import program_src
from arcor2_build.source.utils import derived_resources_class, global_action_points_class, global_actions_class
from arcor2_build_data import PORT, SERVICE_NAME

logger = logging.getLogger("build")
ch = logging.StreamHandler()
ch.setFormatter(logger_formatter())
logger.setLevel(logging.INFO)
logger.addHandler(ch)

# Create an APISpec
spec = APISpec(
    title=SERVICE_NAME,
    version=arcor2_build.version(),
    openapi_version="3.0.2",
    plugins=[FlaskPlugin()],
)

app = Flask(__name__)
CORS(app)

RETURN_TYPE = Union[Tuple[str, int], Response]


def make_executable(path_to_file: str) -> None:
    st = os.stat(path_to_file)
    os.chmod(path_to_file, st.st_mode | stat.S_IEXEC)


def get_base(object_types: Set[str], obj_type: ObjectType, ot_path: str) -> None:

    base = base_from_source(obj_type.source, obj_type.id)

    if not base:
        return

    if base not in object_types and base not in built_in_types_names():

        base_obj_type = ps.get_object_type(base)

        with open(os.path.join(ot_path, humps.depascalize(base_obj_type.id)) + ".py", "w") as obj_file:
            obj_file.write(base_obj_type.source)

        object_types.add(base)

        # try to get base of the base
        get_base(object_types, base_obj_type, ot_path)


def _publish(project_id: str, package_name: str) -> RETURN_TYPE:

    with tempfile.TemporaryDirectory() as pkg_tmp_dir:

        try:
            project = ps.get_project(project_id)
            cached_project = CachedProject(project)
            scene = ps.get_scene(project.scene_id)
            cached_scene = CachedScene(scene)

            project_dir = os.path.join(pkg_tmp_dir, "arcor2_project")

            data_path = os.path.join(project_dir, "data")
            ot_path = os.path.join(project_dir, "object_types")

            os.makedirs(data_path)
            os.makedirs(os.path.join(data_path, "models"))
            os.makedirs(ot_path)

            with open(os.path.join(ot_path, "__init__.py"), "w"):
                pass

            with open(os.path.join(data_path, "project.json"), "w") as project_file:
                project_file.write(project.to_json())

            with open(os.path.join(data_path, "scene.json"), "w") as scene_file:
                scene_file.write(scene.to_json())

            obj_types = set(cached_scene.object_types)
            obj_types_with_models: Set[str] = set()

            for scene_obj in scene.objects:

                obj_type = ps.get_object_type(scene_obj.type)

                if obj_type.model and obj_type.id not in obj_types_with_models:
                    obj_types_with_models.add(obj_type.id)

                    model = ps.get_model(obj_type.model.id, obj_type.model.type)
                    obj_model = ObjectModel(obj_type.model.type, **{model.type().value.lower(): model})  # type: ignore

                    with open(
                        os.path.join(data_path, "models", humps.depascalize(obj_type.id) + ".json"), "w"
                    ) as model_file:
                        model_file.write(obj_model.to_json())

                with open(os.path.join(ot_path, humps.depascalize(obj_type.id)) + ".py", "w") as obj_file:
                    obj_file.write(obj_type.source)

                # handle inheritance
                get_base(obj_types, obj_type, ot_path)

        except ps.PersistentStorageException as e:
            logger.exception("Failed to get something from the project service.")
            return str(e), 404

        script_path = os.path.join(project_dir, "script.py")

        try:

            with open(script_path, "w") as script_file:

                if project.has_logic:
                    script_file.write(program_src(cached_project, cached_scene, built_in_types_names(), True))
                else:
                    try:
                        script = ps.get_project_sources(project.id).script

                        # check if it is a valid Python code
                        try:
                            parse(script)
                        except SourceException:
                            logger.exception("Failed to parse code of the uploaded script.")
                            return "Invalid code.", 501

                        script_file.write(script)

                    except ps.PersistentStorageException:

                        logger.info("Script not found on project service, creating one from scratch.")

                        # write script without the main loop
                        script_file.write(program_src(cached_project, cached_scene, built_in_types_names(), False))

            with open(os.path.join(project_dir, "resources.py"), "w") as res:
                res.write(derived_resources_class(cached_project))

            with open(os.path.join(project_dir, "actions.py"), "w") as act:
                act.write(global_actions_class(cached_project))

            with open(os.path.join(project_dir, "action_points.py"), "w") as aps:
                aps.write(global_action_points_class(cached_project))

            with open(os.path.join(project_dir, "package.json"), "w") as pkg:
                pkg.write(PackageMeta(package_name, datetime.now(tz=timezone.utc)).to_json())

        except SourceException as e:
            logger.exception("Failed to generate script.")
            return str(e), 501

        make_executable(script_path)
        archive_path = os.path.join(pkg_tmp_dir, "arcor2_project")
        shutil.make_archive(archive_path, "zip", project_dir)
        return send_file(archive_path + ".zip", as_attachment=True, cache_timeout=0)


@app.route("/project/<string:project_id>/publish", methods=["GET"])
def project_publish(project_id: str) -> RETURN_TYPE:
    """Publish project
    ---
    get:
      description: Get zip file with execution package. To be used by the Execution service.
      parameters:
        - in: path
          name: project_id
          schema:
            type: string
          required: true
          description: unique ID
        - in: query
          name: PackageName
          schema:
            type: string
            default: Package
          required: false
          description: Package name
      responses:
        200:
          description: Ok
          content:
            application/zip:
                schema:
                  type: string
                  format: binary
                  example: The archive of execution package (.zip)
        404:
            description: Project ID or some of the required items was not found.
        501:
            description: Project invalid.
    """

    return _publish(project_id, request.args.get("PackageName", default="N/A"))


@app.route("/project/<string:project_id>/script", methods=["PUT"])
def project_script(project_id: str):
    """Project script
    ---
    put:
      description: Add or update project main script (DOES NOT WORK YET).
      parameters:
        - in: path
          name: project_id
          schema:
            type: string
          required: true
          description: unique ID
      requestBody:
          content:
            text/x-python:
              schema:
                type: string
                format: binary
      responses:
        200:
          description: Ok
    """
    # TODO use get_logic_from_source
    pass


@app.route("/swagger/api/swagger.json", methods=["GET"])
def get_swagger() -> str:
    return json.dumps(spec.to_dict())


with app.test_request_context():
    spec.path(view=project_publish)
    spec.path(view=project_script)


def main() -> None:

    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)
    args = parser.parse_args()

    if args.swagger:
        print(spec.to_yaml())
        return

    SWAGGER_URL = "/swagger"

    swaggerui_blueprint = get_swaggerui_blueprint(
        SWAGGER_URL, "./api/swagger.json"  # Swagger UI static files will be mapped to '{SWAGGER_URL}/dist/'
    )

    # Register blueprint at URL
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

    app.run(host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()