import requests
import os
import json
import asyncio

from arcor2.data.common import Project, Scene, ProjectSources, ObjectType, DataClassEncoder, IdDescList
from arcor2.exceptions import Arcor2Exception

URL = os.getenv("ARCOR2_PERSISTENT_STORAGE_URL", "http://127.0.0.1:5001")

# TODO handle errors
# TODO cache?
# TODO poll changes?


class PersistentStorageClientException(Arcor2Exception):
    pass


class PersistentStorageClient:

    def get_project(self, project_id: str) -> Project:

        resp = requests.get(f"{URL}/project/{project_id}")
        return Project.from_dict(json.loads(resp.text))

    def get_project_sources(self, project_id: str) -> ProjectSources:

        resp = requests.get(f"{URL}/project/{project_id}/sources")
        return ProjectSources.from_dict(json.loads(resp.text))

    def get_scene(self, scene_id: str) -> Scene:

        resp = requests.get(f"{URL}/scene/{scene_id}")
        return Scene.from_dict(json.loads(resp.text))

    def get_object_type(self, object_type_id: str) -> ObjectType:

        resp = requests.get(f"{URL}/object_type/{object_type_id}")
        return ObjectType.from_dict(json.loads(resp.text))

    def get_object_type_ids(self) -> IdDescList:
        resp = requests.get(f"{URL}/object_types")
        return IdDescList.from_dict(json.loads(resp.text))

    def update_project(self, project: Project):

        assert project.id
        requests.post(f"{URL}/project", json=json.dumps(project, cls=DataClassEncoder))

    def update_scene(self, scene: Scene):

        assert scene.id
        requests.post(f"{URL}/scene", json=json.dumps(scene, cls=DataClassEncoder))

    def update_project_sources(self, project_sources: ProjectSources):

        assert project_sources.id
        requests.post(f"{URL}/project/sources",
                      json=json.dumps(project_sources, cls=DataClassEncoder))

    def update_object_type(self, object_type: ObjectType):

        assert object_type.id
        requests.post(f"{URL}/object_type", json=json.dumps(object_type, cls=DataClassEncoder))


loop = asyncio.get_event_loop()


class AioPersistentStorageClient(PersistentStorageClient):

    async def get_project(self, project_id: str) -> Project:

        res: Project = await loop.run_in_executor(None, super(AioPersistentStorageClient, self).get_project, project_id)
        return res

    async def get_project_sources(self, project_id: str) -> ProjectSources:
        return await loop.run_in_executor(None, super(AioPersistentStorageClient, self).get_project_sources, project_id)

    async def get_scene(self, scene_id: str) -> Scene:
        return await loop.run_in_executor(None, super(AioPersistentStorageClient, self).get_scene, scene_id)

    async def get_object_type(self, object_type_id: str) -> ObjectType:
        return await loop.run_in_executor(None, super(AioPersistentStorageClient, self).get_object_type, object_type_id)

    async def get_object_type_ids(self) -> IdDescList:
        return await loop.run_in_executor(None, super(AioPersistentStorageClient, self).get_object_type_ids)

    async def update_project(self, project: Project):
        return await loop.run_in_executor(None, super(AioPersistentStorageClient, self).update_project, project)

    async def update_scene(self, scene: Scene):
        return await loop.run_in_executor(None, super(AioPersistentStorageClient, self).update_scene, scene)

    async def update_project_sources(self, project_sources: ProjectSources):
        return await loop.run_in_executor(None,
                                          super(AioPersistentStorageClient, self).update_project_sources,
                                          project_sources)

    async def update_object_type(self, object_type: ObjectType):
        return await loop.run_in_executor(None, super(AioPersistentStorageClient, self).update_object_type, object_type)
