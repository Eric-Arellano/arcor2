import inspect
import os
from typing import List, Optional, Set, Type, Union

from horast import parse

from typed_ast.ast3 import AST

import arcor2.helpers as hlp
from arcor2.data import common, events, robot
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types import Generic, Robot
from arcor2.server import globals as glob, notifications as notif, objects_services_actions as osa
from arcor2.services.robot_service import RobotService
from arcor2.source.utils import function_implemented


class RobotPoseException(Arcor2Exception):
    pass


# TODO how to prevent execution of robot (move) action and e.g. moveToAp?
move_in_progress: Set[str] = set()  # set of robot IDs that are moving right now


async def collision(obj: Generic,
                    rs: Optional[RobotService] = None, *, add: bool = False, remove: bool = False) -> None:
    """

    :param obj: Instance of the object.
    :param add:
    :param remove:
    :param rs:
    :return:
    """

    assert add ^ remove

    if not obj.collision_model:
        return

    if rs is None:
        rs = osa.find_robot_service()
    if rs:
        try:
            # TODO notify user somehow when something went wrong?
            await hlp.run_in_executor(rs.add_collision if add else rs.remove_collision, obj)
        except Arcor2Exception as e:
            await glob.logger.error(e)


async def get_end_effectors(robot_id: str) -> Set[str]:
    """
    :param robot_id:
    :return: IDs of existing end effectors.
    """

    robot_inst = await osa.get_robot_instance(robot_id)

    if isinstance(robot_inst, Robot):
        return await hlp.run_in_executor(robot_inst.get_end_effectors_ids)
    else:
        return await hlp.run_in_executor(robot_inst.get_end_effectors_ids, robot_id)


async def get_grippers(robot_id: str) -> Set[str]:
    """
    :param robot_id:
    :return: IDs of existing grippers.
    """

    robot_inst = await osa.get_robot_instance(robot_id)

    if isinstance(robot_inst, Robot):
        return await hlp.run_in_executor(robot_inst.grippers)
    else:
        return await hlp.run_in_executor(robot_inst.grippers, robot_id)


async def get_suctions(robot_id: str) -> Set[str]:
    """
    :param robot_id:
    :return: IDs of existing suctions.
    """

    robot_inst = await osa.get_robot_instance(robot_id)

    if isinstance(robot_inst, Robot):
        return await hlp.run_in_executor(robot_inst.suctions)
    else:
        return await hlp.run_in_executor(robot_inst.suctions, robot_id)


async def get_end_effector_pose(robot_id: str, end_effector: str) -> common.Pose:
    """
    :param robot_id:
    :param end_effector:
    :return: Global pose
    """

    robot_inst = await osa.get_robot_instance(robot_id, end_effector)

    if isinstance(robot_inst, Robot):
        return await hlp.run_in_executor(robot_inst.get_end_effector_pose, end_effector)
    else:
        return await hlp.run_in_executor(robot_inst.get_end_effector_pose, robot_id, end_effector)


async def get_robot_joints(robot_id: str) -> List[common.Joint]:
    """
    :param robot_id:
    :return: List of joints
    """

    robot_inst = await osa.get_robot_instance(robot_id)

    if isinstance(robot_inst, Robot):
        return await hlp.run_in_executor(robot_inst.robot_joints)
    else:
        return await hlp.run_in_executor(robot_inst.robot_joints, robot_id)


def feature(tree: AST, robot_type: Union[Type[Robot], Type[RobotService]], func_name: str) -> bool:

    if not function_implemented(tree, func_name):  # TODO what if the function is implemented in predecessor?
        return False

    sign = inspect.signature(getattr(robot_type, func_name))

    if issubclass(robot_type, Robot):
        return inspect.signature(getattr(Robot, func_name)) == sign
    elif issubclass(robot_type, RobotService):
        return inspect.signature(getattr(RobotService, func_name)) == sign
    else:
        raise Arcor2Exception("Unknown robot type.")


async def get_robot_meta(robot_type: Union[Type[Robot], Type[RobotService]], source: str) -> None:

    # TODO use inspect.getsource(robot_type) instead of source parameters
    #  once we will get rid of type_def_from_source / temp. module

    meta = robot.RobotMeta(robot_type.__name__)
    meta.features.focus = hasattr(robot_type, "focus")  # TODO more sophisticated test? (attr(s) and return value?)

    tree = parse(source)
    meta.features.move_to_pose = feature(tree, robot_type, Robot.move_to_pose.__name__)
    meta.features.move_to_joints = feature(tree, robot_type, Robot.move_to_joints.__name__)
    meta.features.stop = feature(tree, robot_type, Robot.stop.__name__)

    if issubclass(robot_type, Robot) and robot_type.urdf_package_path:
        meta.urdf_package_filename = os.path.split(robot_type.urdf_package_path)[1]

    glob.ROBOT_META[robot_type.__name__] = meta


async def stop(robot_id: str) -> None:

    global move_in_progress

    if robot_id not in move_in_progress:
        raise Arcor2Exception("Robot is not moving.")

    robot_inst = await osa.get_robot_instance(robot_id)

    try:
        if isinstance(robot_inst, Robot):
            await hlp.run_in_executor(robot_inst.stop)
        elif isinstance(robot_inst, RobotService):
            await hlp.run_in_executor(robot_inst.stop, robot_id)
    except NotImplementedError as e:
        raise Arcor2Exception from e

    move_in_progress.remove(robot_id)


async def check_robot_before_move(robot_id: str) -> None:

    if robot_id in move_in_progress:
        raise Arcor2Exception("Robot is moving.")

    if glob.RUNNING_ACTION:

        assert glob.PROJECT
        action = glob.PROJECT.action(glob.RUNNING_ACTION)
        obj_id_str, _ = action.parse_type()

        if robot_id == obj_id_str:
            raise Arcor2Exception("Robot is executing action.")


async def _move_to_pose(robot_id: str, end_effector_id: str, pose: common.Pose, speed: float) -> None:
    # TODO newly connected interface should be notified somehow (general solution for such cases would be great!)

    robot_inst = await osa.get_robot_instance(robot_id, end_effector_id)
    move_in_progress.add(robot_id)

    try:

        if isinstance(robot_inst, Robot):
            await hlp.run_in_executor(robot_inst.move_to_pose, end_effector_id, pose, speed)
        elif isinstance(robot_inst, RobotService):
            await hlp.run_in_executor(robot_inst.move_to_pose, robot_id, end_effector_id, pose, speed)

    except (NotImplementedError, Arcor2Exception) as e:
        await glob.logger.error(f"Robot movement failed with: {str(e)}")
        move_in_progress.remove(robot_id)
        raise Arcor2Exception from e

    move_in_progress.remove(robot_id)


async def move_to_pose(robot_id: str, end_effector_id: str, pose: common.Pose, speed: float) -> None:

    await notif.broadcast_event(events.RobotMoveToPoseEvent(
        data=events.RobotMoveToPoseData(events.MoveEventType.START, robot_id, end_effector_id, pose)))

    try:
        await _move_to_pose(robot_id, end_effector_id, pose, speed)

    except Arcor2Exception as e:
        await notif.broadcast_event(events.RobotMoveToPoseEvent(
            data=events.RobotMoveToPoseData(events.MoveEventType.FAILED, robot_id, end_effector_id, pose,
                                            message=str(e))))
        return

    await notif.broadcast_event(events.RobotMoveToPoseEvent(
        data=events.RobotMoveToPoseData(events.MoveEventType.END, robot_id, end_effector_id, pose)))


async def move_to_ap_orientation(robot_id: str, end_effector_id: str, pose: common.Pose, speed: float,
                                 orientation_id: str) -> None:

    await notif.broadcast_event(events.RobotMoveToActionPointOrientationEvent(
        data=events.RobotMoveToActionPointOrientationData(
            events.MoveEventType.START, robot_id, end_effector_id, orientation_id)))

    try:
        await _move_to_pose(robot_id, end_effector_id, pose, speed)

    except Arcor2Exception as e:
        await notif.broadcast_event(events.RobotMoveToActionPointOrientationEvent(
            data=events.RobotMoveToActionPointOrientationData(
                events.MoveEventType.FAILED, robot_id, end_effector_id, orientation_id, message=str(e))))
        return

    await notif.broadcast_event(events.RobotMoveToActionPointOrientationEvent(
        data=events.RobotMoveToActionPointOrientationData(
            events.MoveEventType.END, robot_id, end_effector_id, orientation_id)))


async def _move_to_joints(robot_id: str, joints: List[common.Joint], speed: float) -> None:

    # TODO newly connected interface should be notified somehow (general solution for such cases would be great!)

    robot_inst = await osa.get_robot_instance(robot_id)

    move_in_progress.add(robot_id)

    try:

        if isinstance(robot_inst, Robot):
            await hlp.run_in_executor(robot_inst.move_to_joints, joints, speed)
        elif isinstance(robot_inst, RobotService):
            await hlp.run_in_executor(robot_inst.move_to_joints, robot_id, joints, speed)

    except (NotImplementedError, Arcor2Exception) as e:
        await glob.logger.error(f"Robot movement failed with: {str(e)}")

        move_in_progress.remove(robot_id)
        raise Arcor2Exception from e

    move_in_progress.remove(robot_id)


async def move_to_joints(robot_id: str, joints: List[common.Joint], speed: float) -> None:

    await notif.broadcast_event(events.RobotMoveToJointsEvent(
        data=events.RobotMoveToJointsData(events.MoveEventType.START, robot_id, joints)))

    try:

        await _move_to_joints(robot_id, joints, speed)

    except Arcor2Exception as e:

        await notif.broadcast_event(events.RobotMoveToJointsEvent(
            data=events.RobotMoveToJointsData(events.MoveEventType.FAILED, robot_id, joints, message=str(e))))

        return

    await notif.broadcast_event(events.RobotMoveToJointsEvent(
        data=events.RobotMoveToJointsData(events.MoveEventType.END, robot_id, joints)))


async def move_to_ap_joints(robot_id: str, joints: List[common.Joint], speed: float, joints_id: str) -> None:

    await notif.broadcast_event(events.RobotMoveToActionPointJointsEvent(
        data=events.RobotMoveToActionPointJointsData(events.MoveEventType.START, robot_id, joints_id)))

    try:

        await _move_to_joints(robot_id, joints, speed)

    except Arcor2Exception as e:

        await notif.broadcast_event(events.RobotMoveToActionPointJointsEvent(
            data=events.RobotMoveToActionPointJointsData(events.MoveEventType.FAILED, robot_id, joints_id,
                                                         message=str(e))))

        return

    await notif.broadcast_event(events.RobotMoveToActionPointJointsEvent(
        data=events.RobotMoveToActionPointJointsData(events.MoveEventType.END, robot_id, joints_id)))
