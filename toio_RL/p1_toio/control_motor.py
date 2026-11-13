import asyncio

from toio import *


async def control_motor(cube_id):
    """モーターのスピードを指定して操作"""
    assert cube_id != "", "cube_idを入力してください"

    # cube_idを検索
    dev_list = await BLEScanner.scan_with_id(cube_id={cube_id})
    assert len(dev_list)

    # 接続
    cube = ToioCoreCube(dev_list[0].interface, name=dev_list[0].name)
    await cube.connect()
    print(f"Success connection! {cube.name}")

    #TODO: 5秒回転．停止させてから登録を解除
    
    # 接続解除
    await cube.disconnect()

    return 0


if __name__ == "__main__":
    asyncio.run(control_motor(cube_id=""))
