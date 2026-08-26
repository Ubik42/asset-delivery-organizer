from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QSettings, Qt, QThread, Signal, Slot
from PySide6.QtGui import QColor, QFont, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..audit import audit_delivery, load_profile
from ..contracts import DeliveryAuditReport, DeliveryIssue, DeliveryProfile
from ..history import DeliveryMetadata, HistoryStore
from ..organization import (
    OrganizationOperation,
    OrganizationPlan,
    OrganizationReceipt,
    PlanExecutionError,
    PlanValidationError,
    execute_organization_plan,
    generate_organization_plan,
    validate_organization_plan,
)
from ..presentation import (
    MEDIA_LABELS,
    RULE_LABELS,
    SEVERITY_LABELS,
    FileReviewRow,
    build_file_rows,
    filter_file_rows,
    human_size,
    profile_with_rule_selection,
)
from ..report_io import atomic_write_report
from ..scanner import ScanError
from .theme import APP_STYLE


class AuditWorker(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, root: Path, profile: DeliveryProfile, digest: str) -> None:
        super().__init__()
        self.root = root
        self.profile = profile
        self.digest = digest

    @Slot()
    def run(self) -> None:
        try:
            self.succeeded.emit(audit_delivery(self.root, self.profile, self.digest))
        except (OSError, ValueError, ScanError) as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class OrganizationWorker(QObject):
    succeeded = Signal(object, object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, plan: OrganizationPlan, profile: DeliveryProfile) -> None:
        super().__init__()
        self.plan = plan
        self.profile = profile

    @Slot()
    def run(self) -> None:
        try:
            receipt, report = execute_organization_plan(self.plan, self.profile)
            self.succeeded.emit(receipt, report)
        except (OSError, ValueError, PlanExecutionError, PlanValidationError) as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class MainWindow(QMainWindow):
    audit_ready = Signal()
    audit_failed = Signal(str)
    organization_ready = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Asset Delivery Organizer")
        self.setMinimumSize(1080, 680)
        self.resize(1440, 900)
        self.setStyleSheet(APP_STYLE)
        self.settings = QSettings("AIToolTA", "AssetDeliveryOrganizer")
        self.profile: DeliveryProfile | None = None
        self.effective_profile: DeliveryProfile | None = None
        self.profile_digest = ""
        self.profile_path: Path | None = None
        self.delivery_root: Path | None = None
        self.report: DeliveryAuditReport | None = None
        self.file_rows: list[FileReviewRow] = []
        self.rule_checks: dict[str, QCheckBox] = {}
        self.organization_plan: OrganizationPlan | None = None
        self.history_store = HistoryStore()
        self.worker_thread: QThread | None = None
        self.worker: AuditWorker | None = None
        self.organization_thread: QThread | None = None
        self.organization_worker: OrganizationWorker | None = None
        self._build_ui()
        self._restore_paths()

    def _build_ui(self) -> None:
        root = QWidget(objectName="AppRoot")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())
        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_setup_page())
        self.pages.addWidget(self._build_files_page())
        self.pages.addWidget(self._build_issues_page())
        self.pages.addWidget(self._build_organization_page())
        self.pages.addWidget(self._build_history_page())
        self.pages.addWidget(self._build_report_page())
        body.addWidget(self.pages, 1)
        body_widget = QWidget()
        body_widget.setLayout(body)
        outer.addWidget(body_widget, 1)

        self.status_message = QLabel("先选择交付目录和规则 Profile。", objectName="StatusMessage")
        outer.addWidget(self.status_message)
        self.setCentralWidget(root)

    def _build_header(self) -> QWidget:
        frame = QFrame(objectName="TopBar")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(22, 13, 22, 13)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        product_name = QLabel("Asset Delivery Organizer", objectName="ProductName")
        product_name.setMinimumWidth(300)
        title_box.addWidget(product_name)
        title_box.addWidget(QLabel("资产交付审阅台", objectName="ProductSubtitle"))
        layout.addLayout(title_box)
        layout.addStretch()
        self.header_context = QLabel("尚未载入交付", objectName="Muted")
        layout.addWidget(self.header_context)
        layout.addSpacing(16)
        layout.addWidget(QLabel("审计只读 · 整理需批准", objectName="ReadOnlyBadge"))
        return frame

    def _build_sidebar(self) -> QWidget:
        frame = QFrame(objectName="Sidebar")
        frame.setFixedWidth(220)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 18, 10, 14)
        label = QLabel("工作流程", objectName="Muted")
        label.setContentsMargins(10, 0, 0, 6)
        layout.addWidget(label)
        self.navigation = QListWidget(objectName="Navigation")
        self.navigation.addItems(
            [
                "① 交付设置",
                "② 文件浏览",
                "③ 问题审查",
                "④ 整理方案",
                "⑤ 审计记录",
                "⑥ 报告导出",
            ]
        )
        self.navigation.setCurrentRow(0)
        self.navigation.currentRowChanged.connect(self._change_page)
        layout.addWidget(self.navigation)
        layout.addStretch()
        note = QLabel("审计不写入；整理只执行已预览且已批准的计划。", objectName="Muted")
        note.setWordWrap(True)
        note.setContentsMargins(10, 8, 10, 4)
        layout.addWidget(note)
        return frame

    def _page_shell(self, title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)
        layout.addWidget(QLabel(title, objectName="PageTitle"))
        subtitle_label = QLabel(subtitle, objectName="Muted")
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)
        return page, layout

    def _path_row(self, target: QLineEdit, button_text: str, callback) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(target, 1)
        button = QPushButton(button_text)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return widget

    def _build_setup_page(self) -> QWidget:
        page, layout = self._page_shell(
            "交付设置", "选择本次交付及项目规则。扫描只读取文件事实，不会在交付目录中生成任何内容。"
        )
        source_box = QGroupBox("输入范围")
        source_layout = QGridLayout(source_box)
        source_layout.setHorizontalSpacing(12)
        source_layout.setVerticalSpacing(12)
        source_layout.addWidget(QLabel("交付目录"), 0, 0)
        self.root_edit = QLineEdit()
        self.root_edit.setPlaceholderText("选择供应商交付目录")
        source_layout.addWidget(self._path_row(self.root_edit, "选择目录", self._choose_root), 0, 1)
        source_layout.addWidget(QLabel("规则 Profile"), 1, 0)
        self.profile_edit = QLineEdit()
        self.profile_edit.setPlaceholderText("选择 art-delivery-profile/1 JSON")
        source_layout.addWidget(self._path_row(self.profile_edit, "选择 Profile", self._choose_profile), 1, 1)
        self.profile_summary = QLabel("尚未载入 Profile", objectName="Muted")
        source_layout.addWidget(self.profile_summary, 2, 1)
        source_layout.setColumnStretch(1, 1)
        layout.addWidget(source_box)

        metadata_box = QGroupBox("交付记录")
        metadata_layout = QGridLayout(metadata_box)
        metadata_layout.setHorizontalSpacing(12)
        metadata_layout.setVerticalSpacing(10)
        self.role_combo = QComboBox()
        self.role_combo.addItems(["审核人员", "供应商"])
        self.company_edit = QLineEdit()
        self.company_edit.setPlaceholderText("例如 NW")
        self.person_edit = QLineEdit()
        self.person_edit.setPlaceholderText("例如 TA042")
        self.project_edit = QLineEdit()
        self.project_edit.setPlaceholderText("项目代码")
        self.asset_edit = QLineEdit()
        self.asset_edit.setPlaceholderText("资产代码")
        self.stage_combo = QComboBox()
        self.stage_combo.addItems(["模型", "材质", "绑定", "动画", "审核", "交付"])
        self.stage_combo.setCurrentText("审核")
        self.review_combo = QComboBox()
        self.review_combo.addItems(["待复核", "需修改", "已通过"])
        fields = [
            ("当前角色", self.role_combo),
            ("公司代码", self.company_edit),
            ("人员代码", self.person_edit),
            ("项目代码", self.project_edit),
            ("资产代码", self.asset_edit),
            ("制作阶段", self.stage_combo),
            ("审核状态", self.review_combo),
        ]
        for index, (label, widget) in enumerate(fields):
            row, pair = divmod(index, 4)
            column = pair * 2
            metadata_layout.addWidget(QLabel(label), row, column)
            metadata_layout.addWidget(widget, row, column + 1)
        for column in (1, 3, 5, 7):
            metadata_layout.setColumnStretch(column, 1)
        layout.addWidget(metadata_box)

        rules_box = QGroupBox("本次启用的检查")
        self.rules_layout = QVBoxLayout(rules_box)
        self.rules_hint = QLabel("载入 Profile 后可选择本次需要执行的规则。", objectName="Muted")
        self.rules_layout.addWidget(self.rules_hint)
        layout.addWidget(rules_box)
        layout.addStretch()

        actions = QHBoxLayout()
        self.scan_progress = QProgressBar()
        self.scan_progress.setVisible(False)
        self.scan_progress.setRange(0, 0)
        actions.addWidget(self.scan_progress, 1)
        self.scan_button = QPushButton("扫描并检查", objectName="PrimaryButton")
        self.scan_button.clicked.connect(self.start_audit)
        actions.addWidget(self.scan_button)
        layout.addLayout(actions)
        return page

    def _build_files_page(self) -> QWidget:
        page, layout = self._page_shell(
            "文件浏览", "筛选本次扫描得到的稳定文件事实，选择一项查看路径、大小、解析字段和内容预览。"
        )
        filters = QHBoxLayout()
        self.file_search = QLineEdit()
        self.file_search.setPlaceholderText("搜索文件名或路径")
        self.file_search.textChanged.connect(self._refresh_files)
        self.kind_filter = QComboBox()
        self.kind_filter.addItems(["全部", "模型", "贴图", "文档/其他"])
        self.kind_filter.currentTextChanged.connect(self._refresh_files)
        self.file_status_filter = QComboBox()
        self.file_status_filter.addItems(["全部", "仅有问题", "仅通过"])
        self.file_status_filter.currentTextChanged.connect(self._refresh_files)
        filters.addWidget(self.file_search, 1)
        filters.addWidget(self.kind_filter)
        filters.addWidget(self.file_status_filter)
        layout.addLayout(filters)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.files_table = QTableWidget(0, 5)
        self.files_table.setHorizontalHeaderLabels(["状态", "文件", "类型", "大小", "问题"])
        self.files_table.setAlternatingRowColors(True)
        self.files_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.files_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.files_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.files_table.verticalHeader().setVisible(False)
        self.files_table.horizontalHeader().setStretchLastSection(False)
        self.files_table.setColumnWidth(0, 82)
        self.files_table.setColumnWidth(1, 430)
        self.files_table.setColumnWidth(2, 130)
        self.files_table.setColumnWidth(3, 85)
        self.files_table.horizontalHeader().setStretchLastSection(True)
        self.files_table.itemSelectionChanged.connect(self._show_file_details)
        splitter.addWidget(self.files_table)

        detail = QFrame(objectName="Panel")
        detail.setMinimumWidth(300)
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(16, 16, 16, 16)
        detail_layout.addWidget(QLabel("文件详情", objectName="SectionTitle"))
        self.file_detail = QPlainTextEdit()
        self.file_detail.setReadOnly(True)
        self.file_detail.setPlaceholderText("选择文件后显示元数据。")
        self.file_detail.setFont(QFont("Cascadia Mono", 10))
        detail_layout.addWidget(self.file_detail, 1)
        self.preview_label = QLabel("选择图片或文本文件以预览内容。", objectName="Muted")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumHeight(180)
        detail_layout.addWidget(self.preview_label, 1)
        splitter.addWidget(detail)
        splitter.setSizes([850, 330])
        layout.addWidget(splitter, 1)
        return page

    def _build_issues_page(self) -> QWidget:
        page, layout = self._page_shell(
            "问题审查", "按严重级别和规则定位问题。每条结果都包含观测值、期望值和处理建议。"
        )
        summary = QHBoxLayout()
        self.summary_passed = QLabel("等待扫描", objectName="SummaryPassed")
        self.summary_warning = QLabel("警告 0", objectName="SummaryWarning")
        self.summary_error = QLabel("错误/阻断 0", objectName="SummaryError")
        summary.addWidget(self.summary_passed)
        summary.addWidget(self.summary_warning)
        summary.addWidget(self.summary_error)
        summary.addStretch()
        layout.addLayout(summary)

        filters = QHBoxLayout()
        self.issue_search = QLineEdit()
        self.issue_search.setPlaceholderText("搜索受影响文件")
        self.issue_search.textChanged.connect(self._refresh_issues)
        self.severity_filter = QComboBox()
        self.severity_filter.addItems(["全部级别", "阻断", "错误", "警告", "提示"])
        self.severity_filter.currentTextChanged.connect(self._refresh_issues)
        self.rule_filter = QComboBox()
        self.rule_filter.addItem("全部规则")
        self.rule_filter.currentTextChanged.connect(self._refresh_issues)
        filters.addWidget(self.issue_search, 1)
        filters.addWidget(self.severity_filter)
        filters.addWidget(self.rule_filter)
        layout.addLayout(filters)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.issues_table = QTableWidget(0, 4)
        self.issues_table.setHorizontalHeaderLabels(["级别", "规则", "受影响文件", "问题"])
        self.issues_table.setAlternatingRowColors(True)
        self.issues_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.issues_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.issues_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.issues_table.verticalHeader().setVisible(False)
        self.issues_table.setColumnWidth(0, 75)
        self.issues_table.setColumnWidth(1, 150)
        self.issues_table.setColumnWidth(2, 360)
        self.issues_table.horizontalHeader().setStretchLastSection(True)
        self.issues_table.itemSelectionChanged.connect(self._show_issue_details)
        splitter.addWidget(self.issues_table)
        evidence = QFrame(objectName="Panel")
        evidence.setMinimumWidth(320)
        evidence_layout = QVBoxLayout(evidence)
        evidence_layout.setContentsMargins(16, 16, 16, 16)
        evidence_layout.addWidget(QLabel("证据与建议", objectName="SectionTitle"))
        self.issue_detail = QPlainTextEdit()
        self.issue_detail.setReadOnly(True)
        self.issue_detail.setPlaceholderText("选择问题后显示规则证据。")
        evidence_layout.addWidget(self.issue_detail)
        splitter.addWidget(evidence)
        splitter.setSizes([840, 350])
        layout.addWidget(splitter, 1)
        return page

    def _build_organization_page(self) -> QWidget:
        page, layout = self._page_shell(
            "整理方案",
            "先生成并检查计划，再明确批准执行。命名错误可编辑目标名，旧版本归档到交付目录之外；缺失贴图不会被自动伪造。",
        )
        output_box = QGroupBox("安全输出")
        output_layout = QGridLayout(output_box)
        output_layout.addWidget(QLabel("归档与收据目录"), 0, 0)
        self.organization_output_edit = QLineEdit()
        self.organization_output_edit.setPlaceholderText("必须位于交付目录之外")
        output_layout.addWidget(
            self._path_row(
                self.organization_output_edit,
                "选择输出目录",
                self._choose_organization_output,
            ),
            0,
            1,
        )
        output_layout.setColumnStretch(1, 1)
        layout.addWidget(output_box)

        toolbar = QHBoxLayout()
        self.plan_status = QLabel("完成一次检查后生成整理方案。", objectName="Muted")
        toolbar.addWidget(self.plan_status, 1)
        self.generate_plan_button = QPushButton("生成整理方案")
        self.generate_plan_button.setEnabled(False)
        self.generate_plan_button.clicked.connect(self._generate_organization_plan)
        toolbar.addWidget(self.generate_plan_button)
        layout.addLayout(toolbar)

        self.plan_table = QTableWidget(0, 5)
        self.plan_table.setHorizontalHeaderLabels(["执行", "动作", "源文件", "目标", "原因"])
        self.plan_table.setAlternatingRowColors(True)
        self.plan_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.plan_table.verticalHeader().setVisible(False)
        self.plan_table.setColumnWidth(0, 58)
        self.plan_table.setColumnWidth(1, 78)
        self.plan_table.setColumnWidth(2, 330)
        self.plan_table.setColumnWidth(3, 390)
        self.plan_table.horizontalHeader().setStretchLastSection(True)
        self.plan_table.itemChanged.connect(self._validate_plan_table)
        layout.addWidget(self.plan_table, 1)

        actions = QHBoxLayout()
        self.plan_safety = QLabel("尚未生成计划。", objectName="Muted")
        self.plan_safety.setWordWrap(True)
        actions.addWidget(self.plan_safety, 1)
        self.execute_plan_button = QPushButton("批准并执行整理", objectName="PrimaryButton")
        self.execute_plan_button.setEnabled(False)
        self.execute_plan_button.clicked.connect(self._execute_organization_plan)
        actions.addWidget(self.execute_plan_button)
        layout.addLayout(actions)
        return page

    def _build_history_page(self) -> QWidget:
        page, layout = self._page_shell(
            "审计记录", "本机保存审计和整理收据索引，便于复核版本、负责人和处理结果。原始交付内容不会写入数据库。"
        )
        audit_box = QGroupBox("最近审计")
        audit_layout = QVBoxLayout(audit_box)
        self.history_audits = QTableWidget(0, 7)
        self.history_audits.setHorizontalHeaderLabels(
            ["时间", "项目", "资产", "角色", "状态", "文件", "问题"]
        )
        self.history_audits.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_audits.setAlternatingRowColors(True)
        self.history_audits.verticalHeader().setVisible(False)
        self.history_audits.horizontalHeader().setStretchLastSection(True)
        audit_layout.addWidget(self.history_audits)
        layout.addWidget(audit_box, 2)

        receipt_box = QGroupBox("整理收据")
        receipt_layout = QVBoxLayout(receipt_box)
        self.history_receipts = QTableWidget(0, 5)
        self.history_receipts.setHorizontalHeaderLabels(
            ["时间", "收据", "执行操作", "复检问题", "收据路径"]
        )
        self.history_receipts.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_receipts.setAlternatingRowColors(True)
        self.history_receipts.verticalHeader().setVisible(False)
        self.history_receipts.horizontalHeader().setStretchLastSection(True)
        receipt_layout.addWidget(self.history_receipts)
        layout.addWidget(receipt_box, 1)
        self._refresh_history()
        return page

    def _build_report_page(self) -> QWidget:
        page, layout = self._page_shell(
            "报告导出", "确认本次审计范围和统计后，将标准 JSON 报告保存到交付目录之外。"
        )
        box = QGroupBox("本次审计")
        box_layout = QVBoxLayout(box)
        self.report_summary = QPlainTextEdit()
        self.report_summary.setReadOnly(True)
        self.report_summary.setPlaceholderText("完成扫描后显示报告摘要。")
        self.report_summary.setMaximumHeight(280)
        box_layout.addWidget(self.report_summary)
        layout.addWidget(box)

        safety = QFrame(objectName="Panel")
        safety_layout = QHBoxLayout(safety)
        safety_layout.setContentsMargins(16, 14, 16, 14)
        safety_layout.addWidget(QLabel("输入目录写入次数：0。报告目标若位于交付目录内会被拒绝。"))
        safety_layout.addStretch()
        layout.addWidget(safety)
        layout.addStretch()
        action = QHBoxLayout()
        action.addStretch()
        self.export_button = QPushButton("导出 JSON 报告", objectName="PrimaryButton")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self._export_report)
        action.addWidget(self.export_button)
        layout.addLayout(action)
        return page

    def _restore_paths(self) -> None:
        profile = self.settings.value("lastProfile", "")
        root = self.settings.value("lastRoot", "")
        output = self.settings.value("organizationOutput", "")
        if profile and Path(str(profile)).is_file():
            self.configure(profile_path=Path(str(profile)))
        if root and Path(str(root)).is_dir():
            self.configure(delivery_root=Path(str(root)))
        if output:
            self.organization_output_edit.setText(str(output))

    def configure(
        self,
        *,
        profile_path: Path | None = None,
        delivery_root: Path | None = None,
        organization_output: Path | None = None,
    ) -> None:
        if delivery_root is not None:
            self.delivery_root = delivery_root.resolve(strict=True)
            self.root_edit.setText(str(self.delivery_root))
            self.settings.setValue("lastRoot", str(self.delivery_root))
            if not self.asset_edit.text():
                self.asset_edit.setText(self.delivery_root.name)
        if profile_path is not None:
            profile, digest = load_profile(profile_path.resolve(strict=True))
            self.profile_path = profile_path.resolve(strict=True)
            self.profile = profile
            self.profile_digest = digest
            self.profile_edit.setText(str(self.profile_path))
            self.settings.setValue("lastProfile", str(self.profile_path))
            self._populate_rules()
            if not self.project_edit.text():
                self.project_edit.setText(profile.project_id)
        if organization_output is not None:
            resolved_output = organization_output.resolve(strict=False)
            self.organization_output_edit.setText(str(resolved_output))
            self.settings.setValue("organizationOutput", str(resolved_output))
        self._update_context()

    def _delivery_metadata(self) -> DeliveryMetadata:
        return DeliveryMetadata(
            role=self.role_combo.currentText(),
            company_code=self.company_edit.text().strip(),
            person_code=self.person_edit.text().strip(),
            project_code=self.project_edit.text().strip(),
            asset_code=self.asset_edit.text().strip(),
            stage=self.stage_combo.currentText(),
            review_status=self.review_combo.currentText(),
        )

    def _populate_rules(self) -> None:
        while self.rules_layout.count():
            item = self.rules_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.rule_checks.clear()
        if self.profile is None:
            self.rules_layout.addWidget(QLabel("尚未载入 Profile", objectName="Muted"))
            return
        for rule in self.profile.rules:
            check = QCheckBox(f"{RULE_LABELS.get(rule.rule_id, rule.rule_id)}  ·  {SEVERITY_LABELS[rule.severity]}")
            check.setChecked(rule.enabled)
            check.setToolTip(f"{rule.rule_id}@{rule.rule_version}")
            self.rule_checks[rule.rule_id] = check
            self.rules_layout.addWidget(check)
        self.profile_summary.setText(
            f"项目 {self.profile.project_id}  ·  Profile {self.profile.profile_id}@{self.profile.profile_version}  ·  {len(self.profile.rules)} 条规则"
        )

    def _update_context(self) -> None:
        root_name = self.delivery_root.name if self.delivery_root else "尚未选择交付"
        profile_name = self.profile.profile_id if self.profile else "尚未载入规则"
        self.header_context.setText(f"{root_name}  ·  {profile_name}")

    @Slot()
    def _choose_root(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "选择交付目录", self.root_edit.text())
        if selected:
            try:
                self.configure(delivery_root=Path(selected))
            except (OSError, ValueError) as exc:
                self._show_error("无法载入交付目录", str(exc))

    @Slot()
    def _choose_profile(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self, "选择规则 Profile", self.profile_edit.text(), "JSON Profile (*.json)"
        )
        if selected:
            try:
                self.configure(profile_path=Path(selected))
            except (OSError, ValueError) as exc:
                self._show_error("Profile 无效", str(exc))

    @Slot()
    def start_audit(self) -> None:
        try:
            root = Path(self.root_edit.text()).resolve(strict=True)
            if not root.is_dir():
                raise ValueError("交付目录必须是文件夹")
            profile_path = Path(self.profile_edit.text()).resolve(strict=True)
            profile, _ = load_profile(profile_path)
            selected = {rule_id for rule_id, check in self.rule_checks.items() if check.isChecked()}
            if not self.rule_checks:
                self.configure(profile_path=profile_path)
                selected = {rule_id for rule_id, check in self.rule_checks.items() if check.isChecked()}
            effective, digest = profile_with_rule_selection(profile, selected)
            self.delivery_root = root
            self.profile_path = profile_path
            self.profile = profile
            self.effective_profile = effective
        except (OSError, ValueError) as exc:
            self._show_error("无法开始检查", f"{exc}\n\n没有读取或修改任何交付文件。")
            self.audit_failed.emit(str(exc))
            return

        self.scan_button.setEnabled(False)
        self.scan_button.setText("正在扫描…")
        self.scan_progress.setVisible(True)
        self.navigation.setEnabled(False)
        self.status_message.setText("正在计算稳定文件事实并执行规则，请稍候…")
        self.worker_thread = QThread(self)
        self.worker = AuditWorker(root, effective, digest)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.succeeded.connect(self._audit_succeeded)
        self.worker.failed.connect(self._audit_failed)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self._audit_finished)
        self.worker_thread.start()

    @Slot(object)
    def _audit_succeeded(self, report: DeliveryAuditReport) -> None:
        self.report = report
        self.file_rows = build_file_rows(report)
        self._refresh_files()
        self._populate_rule_filter()
        self._refresh_issues()
        self._refresh_summary()
        self.export_button.setEnabled(True)
        self.generate_plan_button.setEnabled(True)
        self.organization_plan = None
        self.plan_table.setRowCount(0)
        self.execute_plan_button.setEnabled(False)
        self.plan_status.setText("检查完成，可以生成本次整理方案。")
        if self.delivery_root is not None:
            self.history_store.record_audit(
                report, self.delivery_root, self._delivery_metadata()
            )
            self._refresh_history()
        self.navigation.setCurrentRow(2 if report.issues else 1)
        self.status_message.setText(
            f"检查完成：{report.summary.file_count} 个文件，{report.summary.issue_count} 个问题，输入写入 0 次。"
        )
        self.audit_ready.emit()

    @Slot(str)
    def _audit_failed(self, message: str) -> None:
        self.report = None
        self.export_button.setEnabled(False)
        self.generate_plan_button.setEnabled(False)
        self.execute_plan_button.setEnabled(False)
        self.status_message.setText("检查失败，输入目录保持不变。")
        self._show_error("检查未完成", f"{message}\n\n没有修改任何交付文件，请修正输入后重试。")
        self.audit_failed.emit(message)

    @Slot()
    def _audit_finished(self) -> None:
        self.scan_button.setEnabled(True)
        self.scan_button.setText("扫描并检查")
        self.scan_progress.setVisible(False)
        self.navigation.setEnabled(True)
        self.worker = None
        self.worker_thread = None

    @Slot(int)
    def _change_page(self, index: int) -> None:
        if index >= 0:
            self.pages.setCurrentIndex(index)

    @Slot()
    def _refresh_files(self) -> None:
        rows = filter_file_rows(
            self.file_rows,
            query=self.file_search.text(),
            kind=self.kind_filter.currentText(),
            status=self.file_status_filter.currentText(),
        )
        self.files_table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            status_label = {
                "passed": "通过",
                "info": "提示",
                "warning": "警告",
                "error": "错误",
                "blocker": "阻断",
            }[row.status]
            values = [
                status_label,
                row.fact.relative_path,
                MEDIA_LABELS.get(row.fact.media_type, row.fact.media_type),
                human_size(row.fact.size_bytes),
                str(len(row.issues)),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, row.fact.relative_path)
                if column == 0:
                    item.setForeground(
                        QColor({"passed": "#74C897", "warning": "#F1C66D", "error": "#EF8B78", "blocker": "#FF7766", "info": "#7CB8E2"}[row.status])
                    )
                self.files_table.setItem(index, column, item)
        if rows:
            self.files_table.selectRow(0)
        else:
            self.file_detail.clear()
            self.preview_label.setText("当前筛选条件下没有文件。")
            self.preview_label.setPixmap(QPixmap())

    @Slot()
    def _show_file_details(self) -> None:
        selected = self.files_table.selectedItems()
        if not selected or self.delivery_root is None:
            return
        relative_path = selected[0].data(Qt.ItemDataRole.UserRole)
        row = next((item for item in self.file_rows if item.fact.relative_path == relative_path), None)
        if row is None:
            return
        fact = row.fact
        tokens = "、".join(f"{key}={value}" for key, value in fact.parsed_tokens.items()) or "未解析"
        self.file_detail.setPlainText(
            f"相对路径\n{fact.relative_path}\n\n媒体类型\n{fact.media_type}\n\n大小\n{human_size(fact.size_bytes)}\n\n解析字段\n{tokens}\n\nSHA-256\n{fact.sha256}\n\n关联问题\n{len(row.issues)}"
        )
        self._preview_path(self.delivery_root / Path(fact.relative_path))

    def _preview_path(self, path: Path) -> None:
        self.preview_label.setPixmap(QPixmap())
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"}:
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self.preview_label.setPixmap(
                    pixmap.scaled(300, 240, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                )
                return
        if path.suffix.lower() in {".txt", ".md", ".csv", ".json", ".usd", ".usda", ".obj", ".ma", ".fbx"}:
            try:
                data = path.read_bytes()[:32_768]
                if b"\x00" not in data:
                    text = data.decode("utf-8", errors="replace")
                    self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                    self.preview_label.setText(text[:4000] or "文件为空。")
                    return
            except OSError:
                pass
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setText("该格式暂不支持内容预览，文件事实仍已完成检查。")

    def _populate_rule_filter(self) -> None:
        current = self.rule_filter.currentText()
        self.rule_filter.blockSignals(True)
        self.rule_filter.clear()
        self.rule_filter.addItem("全部规则")
        if self.report:
            for rule in self.report.rules_evaluated:
                self.rule_filter.addItem(RULE_LABELS.get(rule.rule_id, rule.rule_id), rule.rule_id)
        index = self.rule_filter.findText(current)
        self.rule_filter.setCurrentIndex(max(index, 0))
        self.rule_filter.blockSignals(False)

    @Slot()
    def _refresh_issues(self) -> None:
        issues = list(self.report.issues) if self.report else []
        query = self.issue_search.text().strip().casefold()
        severity_map = {value: key for key, value in SEVERITY_LABELS.items()}
        severity = severity_map.get(self.severity_filter.currentText())
        rule_id = self.rule_filter.currentData()
        issues = [
            issue
            for issue in issues
            if (not query or query in issue.affected_file.casefold())
            and (not severity or issue.severity == severity)
            and (not rule_id or issue.rule_id == rule_id)
        ]
        self.issues_table.setRowCount(len(issues))
        for index, issue in enumerate(issues):
            values = [
                SEVERITY_LABELS[issue.severity],
                RULE_LABELS.get(issue.rule_id, issue.rule_id),
                issue.affected_file,
                self._localized_issue_message(issue),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, issue.issue_id)
                if column == 0:
                    item.setForeground(QColor({"blocker": "#FF7766", "error": "#EF8B78", "warning": "#F1C66D", "info": "#7CB8E2"}[issue.severity]))
                self.issues_table.setItem(index, column, item)
        if issues:
            self.issues_table.selectRow(0)
        else:
            self.issue_detail.setPlainText("当前筛选条件下没有问题。")

    def _localized_issue_message(self, issue: DeliveryIssue) -> str:
        return {
            "filename.pattern": "文件名不符合当前项目规则",
            "texture.required-channels": "贴图集合缺少必需通道",
            "version.latest-only": "目录中仍保留旧版本",
        }.get(issue.rule_id, issue.message)

    @Slot()
    def _show_issue_details(self) -> None:
        if self.report is None:
            return
        selected = self.issues_table.selectedItems()
        if not selected:
            return
        issue_id = selected[0].data(Qt.ItemDataRole.UserRole)
        issue = next((item for item in self.report.issues if item.issue_id == issue_id), None)
        if issue is None:
            return
        evidence = []
        for item in issue.evidence:
            evidence.append(f"字段：{item.field}\n观测值：{item.observed}\n期望值：{item.expected}")
        remediation = {
            "filename.pattern": "先核对命名字段；如需改名，应另行生成并批准变更计划。",
            "texture.required-channels": "补齐缺失贴图通道后重新扫描。",
            "version.latest-only": "确认交付版本后，通过后续安全整理计划归档旧版本。",
        }.get(issue.rule_id, issue.remediation)
        self.issue_detail.setPlainText(
            f"{SEVERITY_LABELS[issue.severity]} · {RULE_LABELS.get(issue.rule_id, issue.rule_id)}\n\n受影响文件\n{issue.affected_file}\n\n问题\n{self._localized_issue_message(issue)}\n\n证据\n" + "\n\n".join(evidence) + f"\n\n建议\n{remediation}\n\n自动修改\n未执行"
        )

    def _refresh_summary(self) -> None:
        if self.report is None:
            return
        summary = self.report.summary
        passed = summary.file_count - len({issue.affected_file for issue in self.report.issues})
        self.summary_passed.setText(f"通过文件 {passed}")
        self.summary_warning.setText(f"警告 {summary.warning_count}")
        self.summary_error.setText(f"错误/阻断 {summary.error_count + summary.blocker_count}")
        rules = "、".join(RULE_LABELS.get(item.rule_id, item.rule_id) for item in self.report.rules_evaluated)
        self.report_summary.setPlainText(
            f"审计 ID：{self.report.audit_id}\n交付：{self.report.root_label}\nProfile：{self.report.profile.profile_id}@{self.report.profile.profile_version}\n启用规则：{rules}\n文件：{summary.file_count}\n问题：{summary.issue_count}\n阻断：{summary.blocker_count}\n错误：{summary.error_count}\n警告：{summary.warning_count}\n输入写入：{summary.write_count}"
        )

    @Slot()
    def _choose_organization_output(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "选择归档与收据目录", self.organization_output_edit.text()
        )
        if selected:
            self.configure(organization_output=Path(selected))

    @Slot()
    def _generate_organization_plan(self) -> None:
        if self.report is None or self.delivery_root is None:
            self._show_error("无法生成方案", "请先完成一次检查。")
            return
        output_text = self.organization_output_edit.text().strip()
        if not output_text:
            self._show_error("缺少输出目录", "请选择交付目录之外的归档与收据目录。")
            return
        try:
            plan = generate_organization_plan(
                self.report, self.delivery_root, Path(output_text)
            )
        except (OSError, ValueError, PlanValidationError) as exc:
            self.organization_plan = None
            self.execute_plan_button.setEnabled(False)
            self._show_error("方案未生成", f"{exc}\n\n没有修改任何交付文件。")
            return
        self.organization_plan = plan
        self.settings.setValue("organizationOutput", plan.output_root)
        self.plan_table.blockSignals(True)
        self.plan_table.setRowCount(len(plan.operations))
        for row, operation in enumerate(plan.operations):
            enabled = QTableWidgetItem()
            enabled.setCheckState(Qt.CheckState.Checked)
            enabled.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            enabled.setData(Qt.ItemDataRole.UserRole, operation.operation_id)
            action = QTableWidgetItem("重命名" if operation.action == "rename" else "归档旧版本")
            source = QTableWidgetItem(operation.source_relative)
            target = QTableWidgetItem(operation.target_relative)
            reason = QTableWidgetItem(operation.reason)
            for item in (action, source, reason):
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            for column, item in enumerate((enabled, action, source, target, reason)):
                self.plan_table.setItem(row, column, item)
        self.plan_table.blockSignals(False)
        unresolved = len(plan.unresolved_issue_ids)
        self.plan_status.setText(
            f"计划 {len(plan.operations)} 项，仍有 {unresolved} 个缺失依赖需要人工补齐。"
        )
        self._validate_plan_table()

    def _plan_from_table(self) -> OrganizationPlan:
        if self.organization_plan is None:
            raise PlanValidationError("尚未生成整理方案")
        by_id = {item.operation_id: item for item in self.organization_plan.operations}
        selected: list[OrganizationOperation] = []
        for row in range(self.plan_table.rowCount()):
            enabled = self.plan_table.item(row, 0)
            if enabled is None or enabled.checkState() != Qt.CheckState.Checked:
                continue
            operation_id = str(enabled.data(Qt.ItemDataRole.UserRole))
            operation = by_id[operation_id]
            target = self.plan_table.item(row, 3).text().strip()
            selected.append(operation.model_copy(update={"target_relative": target}))
        return self.organization_plan.model_copy(update={"operations": selected})

    @Slot()
    def _validate_plan_table(self) -> None:
        if self.organization_plan is None:
            self.execute_plan_button.setEnabled(False)
            return
        try:
            plan = self._plan_from_table()
            if not plan.operations:
                raise PlanValidationError("至少选择一项整理操作")
            validate_organization_plan(plan)
        except (OSError, ValueError, PlanValidationError) as exc:
            self.plan_safety.setText(f"预检未通过：{exc}")
            self.plan_safety.setStyleSheet("color: #EF8B78;")
            self.execute_plan_button.setEnabled(False)
            return
        self.plan_safety.setText(
            f"预检通过：{len(plan.operations)} 个源文件哈希一致，目标无冲突；执行后将自动复检并写入外部收据。"
        )
        self.plan_safety.setStyleSheet("color: #74C897;")
        self.execute_plan_button.setEnabled(True)

    @Slot()
    def _execute_organization_plan(self, *, confirm: bool = True) -> None:
        if self.effective_profile is None:
            self._show_error("无法执行", "当前检查 Profile 已失效，请重新扫描。")
            return
        try:
            plan = self._plan_from_table()
            validate_organization_plan(plan)
        except (OSError, ValueError, PlanValidationError) as exc:
            self._show_error("执行前预检失败", f"{exc}\n\n没有修改任何文件。")
            return
        if confirm:
            choice = QMessageBox.warning(
                self,
                "确认执行整理",
                f"将执行 {len(plan.operations)} 项已预览操作。\n\n"
                "目标冲突和源文件哈希已经复检；失败会逆序回滚。是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return
        self.execute_plan_button.setEnabled(False)
        self.generate_plan_button.setEnabled(False)
        self.navigation.setEnabled(False)
        self.status_message.setText("正在执行已批准方案并进行执行后复检…")
        self.organization_thread = QThread(self)
        self.organization_worker = OrganizationWorker(plan, self.effective_profile)
        self.organization_worker.moveToThread(self.organization_thread)
        self.organization_thread.started.connect(self.organization_worker.run)
        self.organization_worker.succeeded.connect(self._organization_succeeded)
        self.organization_worker.failed.connect(self._organization_failed)
        self.organization_worker.finished.connect(self.organization_thread.quit)
        self.organization_worker.finished.connect(self.organization_worker.deleteLater)
        self.organization_thread.finished.connect(self.organization_thread.deleteLater)
        self.organization_thread.finished.connect(self._organization_finished)
        self.organization_thread.start()

    @Slot(object, object)
    def _organization_succeeded(
        self, receipt: OrganizationReceipt, report: DeliveryAuditReport
    ) -> None:
        self.report = report
        self.file_rows = build_file_rows(report)
        self._refresh_files()
        self._populate_rule_filter()
        self._refresh_issues()
        self._refresh_summary()
        self.history_store.record_receipt(receipt)
        if self.delivery_root is not None:
            self.history_store.record_audit(
                report, self.delivery_root, self._delivery_metadata()
            )
        self._refresh_history()
        self.organization_plan = None
        self.plan_table.setRowCount(0)
        self.plan_status.setText(
            f"整理完成：执行 {len(receipt.executed)} 项，复检剩余 {receipt.post_issue_count} 个问题。"
        )
        self.plan_safety.setText(f"执行收据：{receipt.receipt_path}")
        self.status_message.setText(
            f"整理和复检完成，收据已保存到输入目录之外：{receipt.receipt_path}"
        )
        self.navigation.setCurrentRow(4)
        self.organization_ready.emit()

    @Slot(str)
    def _organization_failed(self, message: str) -> None:
        self.plan_safety.setText(f"执行失败：{message}")
        self.plan_safety.setStyleSheet("color: #EF8B78;")
        self.status_message.setText("整理失败，已尝试回滚所有已完成操作。")
        self._show_error(
            "整理未完成",
            f"{message}\n\n请检查文件占用和权限；重新扫描后再生成方案。",
        )

    @Slot()
    def _organization_finished(self) -> None:
        self.navigation.setEnabled(True)
        self.generate_plan_button.setEnabled(self.report is not None)
        if self.organization_plan is not None:
            self._validate_plan_table()
        self.organization_worker = None
        self.organization_thread = None

    def _refresh_history(self) -> None:
        if not hasattr(self, "history_audits"):
            return
        audits = self.history_store.recent_audits()
        self.history_audits.setRowCount(len(audits))
        for row, item in enumerate(audits):
            values = [
                str(item["completed_at"])[:19].replace("T", " "),
                str(item["project_code"] or "—"),
                str(item["asset_code"] or "—"),
                str(item["role"]),
                str(item["review_status"]),
                str(item["file_count"]),
                str(item["issue_count"]),
            ]
            for column, value in enumerate(values):
                self.history_audits.setItem(row, column, QTableWidgetItem(value))
        receipts = self.history_store.recent_receipts()
        self.history_receipts.setRowCount(len(receipts))
        for row, item in enumerate(receipts):
            values = [
                str(item["completed_at"])[:19].replace("T", " "),
                str(item["receipt_id"]),
                str(item["operation_count"]),
                str(item["post_issue_count"]),
                str(item["receipt_path"]),
            ]
            for column, value in enumerate(values):
                self.history_receipts.setItem(row, column, QTableWidgetItem(value))

    @Slot()
    def _export_report(self) -> None:
        if self.report is None or self.delivery_root is None:
            self._show_error("没有可导出的报告", "请先完成一次检查。")
            return
        default_name = f"{self.report.audit_id}.json"
        selected, _ = QFileDialog.getSaveFileName(self, "导出审计报告", default_name, "JSON 报告 (*.json)")
        if not selected:
            return
        try:
            destination = atomic_write_report(self.report, Path(selected), audited_root=self.delivery_root)
        except (OSError, ValueError) as exc:
            self._show_error("报告未导出", f"{exc}\n\n交付目录没有被修改，请选择交付目录之外的位置。")
            return
        self.status_message.setText(f"报告已导出：{destination}")
        QMessageBox.information(self, "报告已导出", f"标准 JSON 报告已保存到：\n{destination}")

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def closeEvent(self, event) -> None:
        busy = (self.worker_thread and self.worker_thread.isRunning()) or (
            self.organization_thread and self.organization_thread.isRunning()
        )
        if busy:
            QMessageBox.information(self, "操作进行中", "请等待当前扫描或整理结束后再关闭窗口。")
            event.ignore()
            return
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:
        narrow = event.size().width() < 1200
        self.issues_table.setColumnHidden(3, narrow)
        self.issues_table.setColumnWidth(0, 68 if narrow else 75)
        self.issues_table.setColumnWidth(1, 130 if narrow else 150)
        self.issues_table.setColumnWidth(2, 245 if narrow else 360)
        self.issues_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            if narrow
            else Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.files_table.setColumnHidden(2, narrow)
        self.files_table.setColumnHidden(3, narrow)
        self.files_table.setColumnWidth(0, 70 if narrow else 82)
        self.files_table.setColumnWidth(1, 330 if narrow else 430)
        self.files_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            if narrow
            else Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.plan_table.setColumnHidden(4, narrow)
        self.plan_table.setColumnWidth(2, 260 if narrow else 330)
        self.plan_table.setColumnWidth(3, 300 if narrow else 390)
        super().resizeEvent(event)
