"""FastAPI server

### start
```
python server.py --cube-id toio-b73
```

### request
```bash
curl http://127.0.0.1:8080/cubes/toio-b73/position
curl -X POST http://127.0.0.1:8080/cubes/toio-b73/move -H "Content-Type: application/json" -d '{"rel_cell_x":1,"rel_cell_y":0}'
```

``powershell
curl.exe -X GET "http://127.0.0.1:8080/cubes/toio-b73/position"
curl.exe -X POST "http://127.0.0.1:8080/cubes/toio-b73/move" -H "Content-Type: application/json" -d '{\"rel_cell_x\":1,\"rel_cell_y\":0}'
```

### 返り値
- 成功時: ok=true, value=[x,y]
- 失敗時: ok=false, value=-1, reason=理由

### その他
- 座標: マット中心が(0,0), 右が+x, 下が+y (1セル=43.43)
"""

import argparse
import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from toio import *

logger = logging.getLogger(__name__)

CELL_SIZE = 43.43
MOVE_TIMEOUT_SEC = 10


class Cube:
    def __init__(self, cube_id):
        self.cube_id = cube_id
        self._cube = None

        self._rel_cell = (0, 0)
        self._mat = ToioMat.SimpleMat
        self._coord = ToioRelativeCoordinateSystem(origin=self._mat.center())

        self._lock = asyncio.Lock()

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

    async def move(self, rel_cell_x, rel_cell_y, speed):
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


def create_app(cubes) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        for cube in cubes.values():
            try:
                await cube.connect()
            except Exception as exc:
                logger.error(f"[{cube.cube_id}] 接続できません: {exc}")
        yield
        for cube in cubes.values():
            await cube.close()

    def get_cube(cube_id):
        if cube_id not in cubes:
            raise HTTPException(404, "unknown cube_id")
        return cubes[cube_id]

    class MoveRequest(BaseModel):
        rel_cell_x: int
        rel_cell_y: int
        speed: int = Field(default=50, ge=8, le=255)
        timeout: float | None = None  # dummy

    def reply(ok, value=-1, reason=None):
        return {"ok": ok, "value": value, "reason": reason}

    app = FastAPI(title="Minimal toio server", lifespan=lifespan)

    #TODO: APIを定義

    return app


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    #TODO: 起動オプションの作成とサーバー立ち上げ


if __name__ == "__main__":
    main()
