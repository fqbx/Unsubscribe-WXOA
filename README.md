# 微信公众号批量取关

通过 ADB + uiautomator2 在**已打开的公众号列表页**上，长按第一条并取消关注。

## 使用

1. 手机 USB 调试、安装依赖、`python -m uiautomator2 init`
2. **手动**打开微信 → 公众号列表页
3. `python main.py` 或 `.\run.ps1` → 连接设备 → 开始

## 坐标配置

编辑 [`config/default.yaml`](config/default.yaml)（左上角为原点，荣耀参考 1264×2800）：

```yaml
first_item:
  reference_resolution: { width: 1264, height: 2800 }
  first_item:
    y_top: 350
    y_bottom: 550
```

## 项目结构

```
main.py              入口
config/default.yaml  坐标与批处理参数
src/
  core/              controller, unsubscriber, adb_manager
  gui/app.py         界面
  utils/             coordinates, delays, logger
delete/              已归档的旧脚本与文档
```

## 风险提示

仅供个人便利；可能触发微信风控，建议小号、小批量测试。
