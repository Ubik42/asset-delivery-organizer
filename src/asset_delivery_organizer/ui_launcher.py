from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="启动 Asset Delivery Organizer 中文工作台。")
    value.add_argument("--root", type=Path, help="预先载入的交付目录。")
    value.add_argument("--profile", type=Path, help="预先载入的 Profile JSON。")
    value.add_argument("--screenshot", type=Path, help="完成审计后保存界面截图并退出。")
    value.add_argument(
        "--page",
        choices=("setup", "files", "issues", "organization", "history", "report"),
        default="issues",
        help="截图模式要展示的工作区。",
    )
    value.add_argument("--width", type=int, default=1440, help="启动窗口宽度。")
    value.add_argument("--height", type=int, default=900, help="启动窗口高度。")
    value.add_argument("--organization-output", type=Path, help="预先载入的归档与收据目录。")
    value.add_argument(
        "--execute-organization",
        action="store_true",
        help="截图自动化专用：生成并执行整理计划。只可用于可变演示副本。",
    )
    value.add_argument(
        "--simulate-plan-collision",
        action="store_true",
        help="截图自动化专用：将一个目标改为已存在文件，展示冲突拦截。",
    )
    value.add_argument(
        "--background-smoke",
        action="store_true",
        help="Windows 生命周期测试：使用真实窗口后端但移出屏幕并禁止抢焦点。",
    )
    return value


def run(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    if args.screenshot and not args.background_smoke:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtWidgets import QApplication

        from .ui.fonts import configure_application_font
        from .ui.main_window import MainWindow
    except ImportError:
        sys.stderr.write("缺少图形界面依赖。请运行：pip install 'asset-delivery-organizer[ui]'\n")
        return 1

    app = QApplication(sys.argv[:1])
    app.setApplicationName("Asset Delivery Organizer")
    configure_application_font(app)
    window = MainWindow()
    window.resize(max(args.width, 1080), max(args.height, 680))
    if args.background_smoke:
        window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        window.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
        window.move(-20_000, -20_000)
    window.show()
    if args.root or args.profile or args.organization_output:
        window.configure(
            profile_path=args.profile,
            delivery_root=args.root,
            organization_output=args.organization_output,
        )
    if args.screenshot:
        if not args.root or not args.profile:
            sys.stderr.write("截图模式必须同时提供 --root 和 --profile。\n")
            return 1
        if (args.page == "organization" or args.execute_organization) and not args.organization_output:
            sys.stderr.write("整理截图必须提供 --organization-output。\n")
            return 1

        def capture() -> None:
            window.navigation.setCurrentRow(
                {
                    "setup": 0,
                    "files": 1,
                    "issues": 2,
                    "organization": 3,
                    "history": 4,
                    "report": 5,
                }[args.page]
            )
            app.processEvents()
            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            if not window.grab().save(str(args.screenshot)):
                app.exit(1)
                return
            app.exit(0)

        def after_audit() -> None:
            if args.page == "organization" or args.execute_organization:
                window._generate_organization_plan()
            if args.simulate_plan_collision and window.plan_table.rowCount():
                window.plan_table.item(window.plan_table.rowCount() - 1, 3).setText(
                    "Meshes/SM_BrokenStatue_v004.fbx"
                )
            if args.execute_organization:
                window.organization_worker = None
                window._execute_organization_plan(confirm=False)
                return
            QTimer.singleShot(250, capture)

        if args.execute_organization:
            window.organization_ready.connect(lambda: QTimer.singleShot(250, capture))
        window.audit_ready.connect(after_audit)
        window.audit_failed.connect(lambda _message: app.exit(1))
        QTimer.singleShot(100, window.start_audit)
    return app.exec()


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
