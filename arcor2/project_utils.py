from typing import Tuple, Dict, Union

from arcor2.data.common import Project, Action, ActionIOEnum, ProjectObject, ActionPoint
from arcor2.helpers import convert_cc
from arcor2.exceptions import ApNotFound


def get_actions_cache(project: Project) -> Tuple[Dict[str, Action], Union[str, None], Union[str, None]]:

    actions_cache = {}
    first_action_id = None
    last_action_id = None

    for obj in project.objects:
        for aps in obj.action_points:
            for act in aps.actions:
                actions_cache[act.id] = act
                if act.inputs and act.inputs[0].default == ActionIOEnum.FIRST:
                    first_action_id = act.id
                elif act.outputs and act.outputs[0].default == ActionIOEnum.LAST:
                    last_action_id = act.id

    return actions_cache, first_action_id, last_action_id


def get_objects_cache(project: Project, id_to_var: bool = False) -> Dict[str, ProjectObject]:

    cache: Dict[str, ProjectObject] = {}

    for obj in project.objects:
        if id_to_var:
            cache[convert_cc(obj.id)] = obj
        else:
            cache[obj.id] = obj

    return cache


def clear_project_logic(project: Project) -> None:

    for obj in project.objects:
        for act_point in obj.action_points:
            for action in act_point.actions:
                action.inputs.clear()
                action.outputs.clear()


def get_action_point(project: Project, ap_id: str) -> ActionPoint:

    for obj in project.objects:
        for ap in obj.action_points:
            if ap.id == ap_id:
                return ap

    raise ApNotFound
