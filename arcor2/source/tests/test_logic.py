#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import copy
import pytest  # type: ignore

from arcor2.data.common import Project, Scene
from arcor2.source.logic import program_src, get_logic_from_source
from arcor2.source import SourceException
from arcor2.project_utils import clear_project_logic
from arcor2.object_types_utils import built_in_types_names


def copy_wo_logic(source_project: Project) -> Project:

    project = copy.deepcopy(source_project)
    clear_project_logic(project)
    return project


VALID_PROJECT = Project.from_dict(
    {'id': 'demo_v0',
     'scene_id': 'scene1',
     'objects': [
         {'id': 'BoxIN',
          'action_points': [
              {'id': 'transfer',
               'pose': {'position': {'x': 0.5, 'y': 0.6, 'z': 0}, 'orientation': {'x': 0, 'y': 0, 'z': 0, 'w': 1}},
               'actions': [
                   {'id': 'MoveToBoxIN',
                    'type': 'robot/move_to',
                    'parameters': [
                        {'id': 'end_effector', 'type': 'string', 'value_string': 'gripper1'},
                        {'id': 'target', 'type': 'ActionPoint', 'value_string': 'BoxIN.transfer'},
                        {'id': 'speed', 'type': 'double', 'value_double': 15}],
                    'inputs': [{'default': 'start'}],
                    'outputs': [{'default': 'MoveToTester'}]}]}]},
         {'id': 'Tester',
          'action_points': [
              {'id': 'input',
               'pose': {'position': {'x': 0.5, 'y': 0.6, 'z': 0}, 'orientation': {'x': 0, 'y': 0, 'z': 0, 'w': 1}},
               'actions': [
                   {'id': 'MoveToTester',
                    'type': 'robot/move_to',
                    'parameters': [
                        {'id': 'end_effector', 'type': 'string', 'value_string': 'gripper1'},
                        {'id': 'target', 'type': 'ActionPoint', 'value_string': 'Tester.input'},
                        {'id': 'speed', 'type': 'double', 'value_double': 15}],
                    'inputs': [{'default': 'MoveToBoxIN'}],
                    'outputs': [{'default': 'MoveToBoxOUT'}]}]}]},
         {'id': 'BoxOUT',
          'action_points': [
              {'id': 'transfer',
               'pose': {'position': {'x': 0.5, 'y': 0.6, 'z': 0}, 'orientation': {'x': 0, 'y': 0, 'z': 0, 'w': 1}},
               'actions': [
                   {'id': 'MoveToBoxOUT',
                    'type': 'robot/move_to',
                    'parameters': [
                        {'id': 'end_effector', 'type': 'string', 'value_string': 'suction1'},
                        {'id': 'target', 'type': 'ActionPoint', 'value_string': 'Tester.input'},
                        {'id': 'speed', 'type': 'double', 'value_double': 15}],
                    'inputs': [{'default': 'MoveToTester'}],
                    'outputs': [{'default': 'end'}]}]}]}]
     }
)


VALID_PROJECT_WO_LOGIC = copy_wo_logic(VALID_PROJECT)

VALID_SCENE = Scene.from_dict(
    {'id': 'scene1',
     'robot_system_id': 'test',
     'objects': [
         {'id': 'Robot',
          'type': 'Robot',
          'pose': {'position': {'x': 0.1, 'y': 0.2, 'z': 0}, 'orientation': {'x': 0, 'y': 0, 'z': 0, 'w': 1}}},
         {'id': 'Tester',
          'type': 'Tester',
          'pose': {'position': {'x': 0.5, 'y': 0.6, 'z': 0}, 'orientation': {'x': 0, 'y': 0, 'z': 0, 'w': 1}}},
         {'id': 'BoxIN',
          'type': 'Box',
          'pose': {'position': {'x': 0.8, 'y': 1.2, 'z': 0}, 'orientation': {'x': 0, 'y': 0, 'z': 0, 'w': 1}}},
         {'id': 'BoxOUT',
          'type': 'Box',
          'pose': {'position': {'x': 1.8, 'y': 1.2, 'z': 0}, 'orientation': {'x': 0, 'y': 0, 'z': 0, 'w': 1}}}]
     }
)

VALID_PROJECTS = (VALID_PROJECT, VALID_PROJECT_WO_LOGIC)

VALID_SOURCE = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from object_types.box import Box
from object_types.tester import Tester
from arcor2.object_types import Robot
from resources import Resources
from arcor2.exceptions import Arcor2Exception, print_exception


def main() -> None:
    res = Resources()
    robot: Robot = res.objects['Robot']
    tester: Tester = res.objects['Tester']
    box_in: Box = res.objects['BoxIN']
    box_out: Box = res.objects['BoxOUT']
    try:
        while True:
            robot.move_to(res.MoveToBoxIN)
            robot.move_to(res.MoveToTester)
            robot.move_to(res.MoveToBoxOUT)
    except Arcor2Exception as e:
        print_exception(e)


if (__name__ == '__main__'):
    try:
        main()
    except Exception as e:
        print_exception(e)
"""

VALID_SOURCE_WITH_DIFFERENT_ACTION_ORDER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from object_types.box import Box
from object_types.tester import Tester
from arcor2.object_types import Robot
from resources import Resource
from arcor2.exceptions import Arcor2Exception, print_exception


def main() -> None:

    res = Resources()
    robot: Robot = res.objects['Robot']
    tester: Tester = res.objects['Tester']
    box_in: Box = res.objects['BoxIN']
    box_out: Box = res.objects['BoxOUT']

    try:
        while True:
            robot.move_to(res.MoveToBoxOUT)
            robot.move_to(res.MoveToBoxIN)
            robot.move_to(res.MoveToTester)
    except Arcor2Exception as e:
        print_exception(e)


if (__name__ == '__main__'):
    try:
        main()
    except Exception as e:
        print_exception(e)
"""


@pytest.fixture(params=list(VALID_PROJECTS))
def valid_project(request):

    return copy.deepcopy(request.param)


def delete_first_action_found(project: Project):

    for obj in project.objects:
        for act_point in obj.action_points:
            if act_point.actions:
                del act_point.actions[0]
                return


def test_valid(valid_project):

    get_logic_from_source(VALID_SOURCE, valid_project)
    assert VALID_PROJECT == valid_project


def test_unknown_action(valid_project):

    invalid_source = VALID_SOURCE.replace("MoveToTester", "MoveToSomewhereElse")

    with pytest.raises(SourceException):
        get_logic_from_source(invalid_source, valid_project)


def test_totally_invalid_source(valid_project):

    with pytest.raises(SourceException):
        get_logic_from_source("", valid_project)


def test_valid_with_different_logic(valid_project):

    project = copy.deepcopy(valid_project)
    get_logic_from_source(VALID_SOURCE_WITH_DIFFERENT_ACTION_ORDER, project)
    assert valid_project != project


def test_missing_action(valid_project):

    delete_first_action_found(valid_project)

    with pytest.raises(SourceException):
        get_logic_from_source(VALID_SOURCE, valid_project)


def test_duplicate_action(valid_project):

    invalid_source = VALID_SOURCE.replace("MoveToTester", "MoveToBoxOUT")

    with pytest.raises(SourceException):
        get_logic_from_source(invalid_source, valid_project)


def test_from_source_to_json_and_back():

    source = program_src(VALID_PROJECT, VALID_SCENE, built_in_types_names())
    assert source == VALID_SOURCE
    project = copy.deepcopy(VALID_PROJECT_WO_LOGIC)
    get_logic_from_source(source, project)
    assert VALID_PROJECT == project
