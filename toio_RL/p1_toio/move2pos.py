import asyncio

from toio import *

"""参考情報
[移動タイプ](https://toio.github.io/toio-spec/docs/ble_motor/#移動タイプ)
[モーター速度変更タイプ](https://toio.github.io/toio-spec/docs/ble_motor/#モーターの速度変化タイプ)
[回転オプション](https://toio.github.io/toio-spec/docs/ble_motor/#目標地点でのキューブの角度-θ)
"""


async def move2pos(cube_id):
    """PositionIDへ移動"""
    assert cube_id != "", "cube_idを入力してください"

    # 接続
    dev_list = await BLEScanner.scan_with_id(cube_id={cube_id})
    assert len(dev_list)
    cube = ToioCoreCube(dev_list[0].interface, name=dev_list[0].name)
    await cube.connect()

    # ハンドラーの作成と登録
    def id_notification_handler(payload: bytearray):
        id_info = IdInformation.is_my_data(payload)
        if isinstance(id_info, PositionId):
            print(f"{id_info.center}")

    await cube.api.id_information.register_notification_handler(id_notification_handler)

    #TODO: Motorの通知を表示するハンドラー作成と登録

    await asyncio.sleep(4)

    #TODO: PositionID(200,200)へ移動

    await asyncio.sleep(4)

    # 接続解除
    await cube.disconnect()
    return 0


if __name__ == "__main__":
    asyncio.run(move2pos(cube_id=""))
