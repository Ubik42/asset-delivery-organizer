Asset Delivery Organizer 1.1.0 Windows 可移植版
================================================

这是什么
--------
面向技术美术、外包供应商和资产审核人员的中文资产交付工作台。
审计严格只读；改名和归档必须先生成方案、通过预检并明确批准。

首次启动
--------
1. 完整解压 ZIP，不要直接在压缩包里运行。
2. 双击 AssetDeliveryOrganizer.exe。
3. 交付目录可先选 demo\scenarios\05_delivery_boundary_preflight。
4. Profile 选择 profiles\atlas.environment.delivery.json。
5. 点击“扫描并检查”，预期得到 9 个文件、4 个错误。

命令行入口
----------
- ado.exe：只读审计。
- ado-organize.exe：生成/执行经过批准的整理方案。
- ado-capabilities.exe：输出机器可读能力清单。

安装、升级与卸载
----------------
- 安装：把整个文件夹复制到有写权限的位置。
- 升级：关闭程序，用新版本完整文件夹替换旧应用文件夹。
- 卸载：关闭程序后删除应用文件夹。
- 本机历史 history.sqlite3 默认保存在用户数据目录，不在应用文件夹或交付目录中；卸载应用不会静默删除历史。

安全边界
--------
- 不要直接整理 demo\scenarios；它们是不可变演示夹具。
- Profile、报告、归档和收据必须保存到被审计交付目录之外。
- 当前发行物未进行商业代码签名；Windows 可能显示未知发布者。

完整文档与源码
--------------
https://github.com/Ubik42/asset-delivery-organizer
