import argparse
import asyncio
import logging
import time

from toio import *

logger = logging.getLogger(__name__)

CELL_SIZE = 43.43
MOVE_TIMEOUT_SEC = 10
MOTOR_RES_TIMEOUT_SEC = 60


class Cube:
    def __init__(self, cube_id):
        self.cube_id = cube_id
        self._cube = None

        self._rel_cell = (0, 0)
        self._mat = ToioMat.SimpleMat
        self._coord = ToioRelativeCoordinateSystem(origin=self._mat.center())

        self._lock = asyncio.Lock()
        self._motor_future = None  # motorの通知受け取り

    async def connect(self):
        dev_list = await BLEScanner.scan_with_id(cube_id={self.cube_id})
        if len(dev_list) != 1:
            raise ConnectionError(f"複数検出されました: {len(dev_list)=}")
        self._cube = ToioCoreCube(dev_list[0].interface, name=dev_list[0].name)

        try:
            await self._cube.connect()
            await self._cube.api.id_information.register_notification_handler(
                self._id_notification_handler
            )
            await self._cube.api.motor.register_notification_handler(
                self._motor_notification_handler
            )
            logger.info(f"[{self.cube_id}] 接続しました")
        except Exception as exc:
            logger.info(f"[{self.cube_id}] 初期化に失敗")

    def _id_notification_handler(self, payload):
        id_info = IdInformation.is_my_data(payload)

        if not isinstance(id_info, PositionId):
            return
        if not id_info.center.point in self._mat:
            return

        rel_point = self._coord.from_native_point(id_info.center.point)
        self._rel_cell = (
            round(rel_point.x / CELL_SIZE),
            round(rel_point.y / CELL_SIZE),
        )

    async def close(self):
        if self._cube is None:
            return

        try:
            await self._cube.api.motor.motor_control(0, 0)
            await self._cube.disconnect()
        except Exception as exc:
            logger.warning(f"[{self.cube_id}] 切断処理: {exc}")

    async def get_position(self):
        return self._rel_cell

    async def _motor_notification_handler(self, payload):
        response = Motor.is_my_data(payload)
        if not isinstance(response, ResponseMotorControlTarget):
            return

        future = self._motor_future
        if future is None or future.done():
            return

        code = response.response_code
        future.set_result(code)

    async def send_move(self, rel_cell_x, rel_cell_y, speed):
        """移動コマンドの送信のみ"""
        async with self._lock:
            try:
                rel_point = Point(
                    round(rel_cell_x * CELL_SIZE), round(rel_cell_y * CELL_SIZE)
                )
                naive_point = self._coord.to_native_point(rel_point)
                await self._cube.api.motor.motor_control_target(
                    timeout=MOVE_TIMEOUT_SEC,
                    movement_type=MovementType.Linear,
                    speed=Speed(max=speed),
                    target=TargetPosition(
                        cube_location=CubeLocation(naive_point, 0),
                        rotation_option=RotationOption.WithoutRotation,
                    ),
                )
            finally:
                pass

    async def wait_move(self, rel_cell_x, rel_cell_y, speed):
        """移動完了を待つ"""
        async with self._lock:
            try:
                #TODO: Motor通知を受け取るfutureを作成

                rel_point = Point(
                    round(rel_cell_x * CELL_SIZE), round(rel_cell_y * CELL_SIZE)
                )
                naive_point = self._coord.to_native_point(rel_point)
                await self._cube.api.motor.motor_control_target(
                    timeout=MOVE_TIMEOUT_SEC,
                    movement_type=MovementType.Linear,
                    speed=Speed(max=speed),
                    target=TargetPosition(
                        cube_location=CubeLocation(naive_point, 0),
                        rotation_option=RotationOption.WithoutRotation,
                    ),
                )
                #TODO: Motorの通知を待機
            finally:
                pass


def steps(x, n):
    pass #TODO: 相対セルで端(3, -3)へ向かって1マスずつ進むxを順に返す


async def shuttle_wait(cube, n, hz, speed):
    pass #TODO: 仮想の推論周期hzでn回マットを往復（同期）


async def shuttle_send(cube, n, hz, speed):
    pass #TODO: 仮想の推論周期hzでn回マットを往復（非同期）


async def main(cube_id, mode):
    # 接続
    cube = Cube(cube_id=cube_id)
    await cube.connect()
    await asyncio.sleep(1)

    # パラメータ
    n = 3  # 往復回数
    hz = 10  # 仮想の推論周期（Hz）
    speed = 30  # 移動速度

    try:
        if mode == "sync":
            await shuttle_wait(cube, n, hz, speed)
        if mode == "async":
            await shuttle_send(cube, n, hz, speed)
    finally:
        await cube.close()


if __name__ == "__main__":
    # 実行例: python cube.py --cube-id toio-XXX --mode sync
    parser = argparse.ArgumentParser()
    parser.add_argument("--cube-id")
    parser.add_argument("--mode")
    args = parser.parse_args()
    asyncio.run(main(args.cube_id, args.mode))
