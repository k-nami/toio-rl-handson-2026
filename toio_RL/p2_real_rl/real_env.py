

from typing import Optional, Tuple, Dict, Any
from enum import IntEnum, StrEnum
import logging

import numpy as np
from gymnasium.spaces import Discrete
from gymnasium.utils import seeding
import requests
import time
import readchar

from toio_RL.common.keyboard_input import read_action_async, Key

logger = logging.getLogger(__name__)


class Action(IntEnum):
    UP = 0
    DOWN = 1
    LEFT = 2
    RIGHT = 3


class RealEnv:
    """Real environment for collecting a target on a grid with a Toio cube."""

    # A3開発マットは中央のセルが(0,0)
    # 環境の座標(x,y)は左上(0,0)
    OFFSET_X: int = 3
    OFFSET_Y: int = 2
    API_TIMEOUT_SEC = 30  # サーバー側の再配置待ちを含む

    def __init__(
        self,
        grid_width: int = 7,
        grid_height: int = 5,
        life_range: Tuple[int, int] = (1, 6),
        agent_name: str = "",
        target_name: Optional[str] = None,
        render_mode: Optional[str] = "ansi",
        api_url: str = "http://127.0.0.1:8080",
    ) -> None:
        if not agent_name:
            raise ValueError("agent_nameを設定してください")

        self._use_physical_target = target_name is not None
        self.cubes = [agent_name] + ([target_name] if self._use_physical_target else [])
        self.api_url = api_url.rstrip("/")

        self.observation_space = Discrete((grid_width * grid_height) ** 2)
        self.action_space = Discrete(len(Action))

        #TODO: 初期化処理

        # 乱数生成器
        self._rng: Optional[np.random.Generator] = None
        # デバッグ処理向け
        self._fail_flag: Dict[str, bool] = {}
        self.render_mode = render_mode

    def _api_value(self, response: requests.Response, cube_id: str):
        """失敗時の value=-1 を通常の座標と誤認しない。"""
        response.raise_for_status()
        data = response.json()
        if not data.get("ok", False):
            raise RuntimeError(f"{cube_id}: {data.get('reason', 'API error')}")
        return data["value"]

    def sync_pos(self) -> None:
        def _get_pos(cube_id: str) -> Tuple[int, int]:
            response = requests.get(
                f"{self.api_url}/cubes/{cube_id}/position",
                params={"timeout": self.API_TIMEOUT_SEC},
                timeout=self.API_TIMEOUT_SEC + 5,
            )
            cell = self._api_value(response, cube_id)
            pos = self.matcell_to_pos(tuple(cell))
            logger.info("%s 観測: pos=%s", cube_id, pos)
            return pos

        self._agent_pos = _get_pos(self.cubes[0])
        if self._use_physical_target:
            self._target_pos = _get_pos(self.cubes[1])

    def reset(
        self, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None
    ) -> Tuple[int, Dict]:
        """Returns: observation, info dict."""
        self._rng, _ = seeding.np_random(seed)

        pass #TODO: 環境の初期化（toioから座標を取得，仮想のりんご初期化，初期状態を返す）

    def step(self, action: int) -> Tuple[int, float, bool, bool, Dict]:
        """Returns: observation, reward, terminated, truncated, info dict."""

        pass #TODO: 環境を1step（50Hz）で進める

    def get_observation(self) -> int:
        pass #TODO: 状態の計算

    def get_reward(self) -> float:
        pass #TODO: 報酬の計算

    # ----- utility methods -----

    def pos_to_index(self, xy: Tuple[int, int]) -> int:
        pass #TODO: 座標(x,y)から状態indexへの変換

    def index_to_pos(self, idx: int) -> Tuple[int, int]:
        pass #TODO: 状態indexから座標(x,y)への変換

    def pos_to_matcell(self, xy: Tuple[int, int]) -> Tuple[int, int]:
        """Convert grid coordinate to Toio mat cell coordinate."""
        return (xy[0] - self.OFFSET_X, xy[1] - self.OFFSET_Y)

    def matcell_to_pos(self, cell: Tuple[int, int]) -> Tuple[int, int]:
        """Convert Toio mat cell coordinate back to grid coordinate."""
        return (cell[0] + self.OFFSET_X, cell[1] + self.OFFSET_Y)

    def render(self) -> Optional[str]:
        """Render grid to console as string."""
        if self.render_mode != "ansi":
            return NotImplemented

        grid = [["." for _ in range(self.grid_width)] for _ in range(self.grid_height)]
        ax, ay = self._agent_pos
        tx, ty = self._target_pos
        grid[ay][ax] = "T"
        grid[ty][tx] = "A" if grid[ty][tx] != "T" else "TA"
        output = "\n".join(" ".join(row) for row in grid)
        print(
            f"{output}\nAgent: ({ax},{ay})  Target: ({tx},{ty})  Life: {self._target_life}"
        )
        return output

    def close(self) -> None:
        """BLE接続の所有者はサーバーなので何もしない。"""
        pass

    # ----- private methods -----

    def _respawn_target(self) -> None:
        """Randomly place the virtual target on a free cell and reset its lifetime."""
        free = [
            self.pos_to_index((x, y))
            for x in range(self.grid_width)
            for y in range(self.grid_height)
            if (x, y) not in (self._agent_pos, self._target_pos)
        ]
        assert self._rng is not None
        choice = self._rng.choice(free)
        self._target_pos = self.index_to_pos(choice)
        self._target_life = int(
            self._rng.integers(self.life_range[0], self.life_range[1])
        )


def test_with_keyboard():
    mapping = {
        readchar.key.UP: Action.UP,
        readchar.key.DOWN: Action.DOWN,
        readchar.key.LEFT: Action.LEFT,
        readchar.key.RIGHT: Action.RIGHT,
    }

    env = RealEnv(
        agent_name="toio-b73", 
        api_url="http://127.0.0.1:8080"
    )
    try:
        # 初期化
        env.reset()
        env.render()

        while True:
            key = readchar.readkey()  # キー入力まで待機
            if key == "q":
                break
            action = mapping.get(key)
            if action is None:
                continue

            # 状態遷移
            env.step(action)
            env.render()
    except KeyboardInterrupt:
        print("Interrupted.")
    finally:
        env.close()

if __name__ == "__main__":
    test_with_keyboard()
