"""FastAPI server (座標キャッシュあり)

### start
```
python server_min.py --cube-id toio-b73
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
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from toio import *

logger = logging.getLogger(__name__)

CELL_SIZE = 43.43
MOVE_TIMEOUT_SEC = 10
POLL_INTERVAL_SEC = 0.05
CACHE_SEC = 1.0  # 最後の座標を有効とみなす時間
API_TIMEOUT_SEC = 30.0  # /position で座標を待つ既定時間


class Cube:
    def __init__(self, cube_id):
        self.cube_id = cube_id
        self._cube = None

        self._rel_cell = (0, 0)
        self._mat = ToioMat.SimpleMat
        self._coord = ToioRelativeCoordinateSystem(origin=self._mat.center())
        self._last_seen = None

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

        #TODO: self._last_seenに観測タイミングを記録
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

    def _position_age(self):
        pass #TODO: self._last_seenからの経過時間を返す．未観測なら-1を返す．

    async def get_position(self):
        """CACHE_SEC 以内に観測した座標が得られるまで待って返す。"""
        pass #TODO: CACHE_SEC以内の観測があればその値を返し，なければ観測があるまで待機（POLL_INTERVAL_SEC間隔で確認）

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

    @app.get("/cubes/{cube_id}/position")
    async def position(cube_id: str, timeout: float = Query(API_TIMEOUT_SEC, gt=0)):
        cube = get_cube(cube_id)
        try:
            cell = await asyncio.wait_for(cube.get_position(), timeout)
        except asyncio.TimeoutError:
            return reply(False, reason="timeout")
        except Exception as exc:
            return reply(False, reason=repr(exc))
        if cell is None:
            return reply(False, reason="position_unavailable")
        return reply(True, cell)

    @app.post("/cubes/{cube_id}/move")
    async def move(cube_id: str, body: MoveRequest):
        cube = get_cube(cube_id)
        try:
            await cube.move(body.rel_cell_x, body.rel_cell_y, body.speed)
        except Exception as exc:
            return reply(False, reason=repr(exc))
        return reply(True, [body.rel_cell_x, body.rel_cell_y])

    return app


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cube-id", action="append", required=True, help="複数回指定可"
    )
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    cubes = {cid: Cube(cid) for cid in args.cube_id}
    uvicorn.run(create_app(cubes), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
