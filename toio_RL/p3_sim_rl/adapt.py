
from env import Env
from q_learning import QTableAgent
from toio_RL.common.q_plotter import QPlotter


def test_agent(
    env,
    agent,
    q_plot_interval,
):
    q_plotter = QPlotter(env)

    try:
        state, _ = env.reset()
        env.render()
        q_plotter.plot_q(Q=agent.Q)

        for step in range(1000):
            print(f"\n--- ステップ {step + 1} ---")
            action = agent.greedy(state)
            state, reward, _, _, _ = env.step(action)
            env.render()
            if step % q_plot_interval == 0:
                q_plotter.plot_q(Q=agent.Q)
            print(f"状態:{state}, 報酬:{reward}")
    except KeyboardInterrupt:
        print("\nCtrl+C を受け取りました。終了します。")
    finally:
        env.close()


if __name__ == "__main__":
    pass #TODO: 学習済みQを読み込んで実機環境に適用
