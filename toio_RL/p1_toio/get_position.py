import asyncio

from toio import *

"""参考
[PositionID](https://toio.github.io/toio-spec/docs/hardware_position_id/)
"""

CELL_SIZE = 43.43  # セルの辺の長さ


async def get_position(cube_id):
    """toioの座標を取得して表示"""
    assert cube_id != "", "cube_idを入力してください"

    # cube_idを検索
    dev_list = await BLEScanner.scan_with_id(cube_id={cube_id})
    assert len(dev_list)

    # 接続
    cube = ToioCoreCube(dev_list[0].interface, name=dev_list[0].name)
    await cube.connect()
    print(f"Success connection! {cube.name}")

    #TODO: 接続後，位置を知らせる関数（ハンドラー）を登録．30秒sleepしてから接続を解除する
    # 接続解除
    await cube.disconnect()

    return 0


if __name__ == "__main__":
    asyncio.run(get_position(cube_id=""))
