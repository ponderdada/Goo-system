"""Gunicorn 設定：worker 啟動後立即開始背景資料分析。"""

import threading


def post_fork(server, worker):
    """Worker fork 完成後立即啟動背景分析排程。"""
    try:
        import app as flask_app
        if not flask_app._scheduler_started:
            flask_app._scheduler_started = True
            try:
                config = flask_app.load_config()
                interval = config.get("web", {}).get("refresh_interval_seconds", 3600)
            except Exception:
                interval = 3600
            t = threading.Thread(
                target=flask_app.background_scheduler,
                args=(interval,),
                daemon=True,
            )
            t.start()
    except Exception as e:
        server.log.error(f"背景排程啟動失敗：{e}")
