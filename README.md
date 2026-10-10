# macOS 27.0 Contacts Avatar Reversion Regression Analysis & Diagnostic Tool

[![Platform](https://img.shields.io/badge/Platform-macOS%2027.0%20(Build%2026A428)-blue.svg)](#)
[![Status](https://img.shields.io/badge/Status-Regression%20Confirmed-red.svg)](#)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Feedback Assistant](https://img.shields.io/badge/Apple%20Radar-Submit%20Dupe-orange.svg)](#how-to-submit-a-duplicate-report-to-apple)

[English](#english) | [中文说明](#中文说明)

---

<a name="english"></a>
## English

### 1. Issue Overview

In **macOS 27.0 (Build 26A428)**, whenever a user updates a contact's avatar (using custom photos, Memoji, or Emoji) in Contacts or Messages, the avatar displays normally for a few seconds, but **automatically reverts to the default monogram initial (e.g. "W") after approximately 15 to 20 seconds**.

#### Key Observations:
- **iPhone / iOS Works Correctly**: When changing the avatar on iPhone, it persists permanently on iOS. However, when synced down to Mac, the Mac still reverts to the monogram initial.
- **iCloud Web Works Correctly**: Uploading via icloud.com is permanent on the cloud, but triggers the same reversion on macOS.
- **Affects All Media Types**: Custom photos, Memoji, and Emoji all revert.
- **Local Cache Resets Do Not Help**: Deleting `~/Library/Application Support/AddressBook`, resetting `accounts.accountdb`, or toggling iCloud contacts does not fix the issue.

---

### 2. Root Cause Analysis

Through millisecond-level unified log tracing (`log stream`), we identified the definitive root cause within `Contacts.framework` and `ContactsUI.framework`:

```text
[User saves Avatar in Contacts.app]
       │
       ▼ (T+0s)
1. Commit edit: Image rasterized to 19KB PHOTO and saved locally.
       │
       ▼ (T+12s)
2. CardDAV Sync: AddressBookSourceSync uploads photo to iCloud (HTTP 207 Success).
       │
       ▼ (T+15s)
3. APNS Push Return: Apple Push Notification arrives acknowledging the change.
       │
       ▼ (T+16s) ───► 【FATAL REGRESSION IN macOS 27】
4. ChangeHistory Engine: Core daemons query change history. Because the contact
   lacks a custom group container, the fallback handler incorrectly executes:
   "Could not fetch group for change type 1 ..., making it a delete change type."
   (The UPDATE event is erroneously mutated into a DELETE event!)
       │
       ▼ (T+16.1s)
5. AvatarViewSnapshotter: ContactsUI receives the false "Delete" notification,
   finds no vector recipe (No avatarRecipeData), snaps a fallback monogram initial,
   and overrides the UI cache.
```

Detailed technical write-ups are available in the [`docs/`](./docs/) directory:
- [01. In-Depth Root Cause & Evidence Log](./docs/01-technical-root-cause.md)
- [02. postersyncd & AvatarViewSnapshotter Architecture](./docs/02-postersyncd-architecture.md)

---

### 3. Diagnostic Tool

We provide a built-in automated CLI tool to verify if your Mac is suffering from this bug.

#### Step 1: Capture live logs while reproducing the issue
```bash
./tools/capture_contacts_log.sh
```
1. Keep the terminal running.
2. Open **Contacts.app**, edit any contact's avatar, and click **Done**.
3. Wait ~20 seconds until you see the avatar revert.
4. Press `Ctrl+C` in the terminal. The script will automatically generate a sanitized log.

#### Step 2: Run automated log diagnosis
```bash
python3 ./tools/analyze_log.py ./samples/sanitized_reproduction.log
```
The analyzer will parse the timestamps and output:
```text
====================================================================
   macOS Contacts Bug Automated Log Analyzer                       
====================================================================
[*] Detection Summary:
  • Contact Save/Commit Events detected: 3
  • CardDAV Server Push (Status 207) detected: 6
  • APNS Push Notifications detected: 1
  • 'Change Type 1 -> Delete Change Type' triggers: 24
  • AvatarViewSnapshotter Override Events: 270

[✔ BUG CONFIRMED] macOS 27 ChangeHistoryFetch Regression Detected!
Elapsed Duration from Save to Reversion: 19.34 seconds
```

---

### 4. How to Submit a Duplicate Report to Apple

To expedite an official fix from Apple in macOS 27.0.1, please submit a duplicate bug report via **Feedback Assistant**:

1. Open **Feedback Assistant** on your Mac (`open applefeedback://` or press `Cmd+Space` and type *Feedback Assistant*).
2. Click **New Feedback** -> **macOS** -> **Contacts**.
3. Copy the template below:

```markdown
### Title
[macOS 27.0 Regression] Contact avatar reverts to monogram initial after 15-20s due to ChangeHistoryFetch classifying update as delete

### Problem Description
In macOS 27.0 (Build 26A428), editing any contact avatar (Memoji, photo, or emoji) saves temporarily, but automatically reverts to the default monogram letter initial after ~16 seconds.

The change syncs to iCloud and displays permanently on iOS, but every Mac receiving the sync triggers the regression.

### Underlying Log Evidence
All listening daemons (Messages, Contacts, contactsd, postersyncd, AddressBookSourceSync) log:
"Could not fetch group for change type 1 with identifier <private>, making it a delete change type."
Followed by:
"AvatarViewSnapshotter: No avatarRecipeData on ContactID -> generate monogram fallback"

Reference GitHub repository and logs:
https://github.com/Prognosticate-X/macos-contacts-avatar-bug
```
4. Attach the sanitized log file [`samples/sanitized_reproduction.log`](./samples/sanitized_reproduction.log).

---

<a name="中文说明"></a>
## 中文说明

### 1. 问题概述

在 **macOS 27.0 正式版（Build 26A428）** 中，用户在通讯录（Contacts.app）或信息（Messages.app）中修改联系人头像（无论是自定义照片、系统 Emoji 还是拟我表情 Memoji），保存后在界面上正常显示数秒，但在 **15 ~ 20 秒左右会自动回退为默认的单字母占位符**（例如 Wife 回退为大写字母“W”）。

#### 核心特征：
* **iPhone 端完全正常**：在 iPhone 上修改头像能永久保存，绝不回退；但只要同步到 Mac，Mac 依然会在数秒后回退为字母。
* **全媒介格式均受影响**：照片、Emoji、Memoji 无一幸免。
* **本地重置完全无效**：清空 AddressBook 缓存目录、重置 SwiftData `accounts.accountdb` 或开关 iCloud 通讯录均无法解决。

---

### 2. 根本技术成因

通过对统一日志系统（Unified Logging）毫秒级追踪，定位到这是 `Contacts.framework` 联系人变更历史解析引擎中的代码级缺陷：

1. **第 0 秒**：通讯录正常将图片以 19KB 位图存盘。
2. **第 12 秒**：`AddressBookSourceSync` 将头像成功推送至 iCloud CardDAV（状态码 207 成功），这是 iPhone 端能长期保存的原因。
3. **第 15 秒**：苹果 APNS 推送回执到达 Mac，Mac 完成增量存储并广播变更。
4. **第 16 秒【致命 Bug 触发点】**：
   系统 5 大核心进程（Contacts、Messages、contactsd、postersyncd、AddressBookSourceSync）拉取变更历史。由于未关联独立群组容器，底层的降级逻辑错误地抛出：
   `Could not fetch group for change type 1 ..., making it a delete change type.`
   **代码强行将“更新事件（type 1）”错误标记成了“删除事件（delete）”！**
5. **第 16.1 秒**：
   前端快照器 `AvatarViewSnapshotter` 收到被篡改的删除事件，判定无矢量配方（`No avatarRecipeData`），立刻拍下默认单字母快照并覆写界面缓存。

详细深度分析请参阅文档：
* [01. 根本原因深度分析与日志证据链](./docs/01-technical-root-cause.md)
* [02. postersyncd 与快照器架构机理](./docs/02-postersyncd-architecture.md)

---

### 3. 自助诊断工具使用

本项目自带轻量化自动化诊断工具，可在终端一键验证：

```bash
# 1. 启动实时抓取脚本（根据提示在通讯录修改头像，等待回退后按 Ctrl+C）
./tools/capture_contacts_log.sh

# 2. 运行自动分析器对抓取的日志进行诊断
python3 ./tools/analyze_log.py ./samples/sanitized_reproduction.log
```

---

### 4. 推动苹果官方修复指南

该问题属于 macOS 27.0 首发版本的系统代码缺陷，需等待苹果在后续版本（如 macOS 27.0.1）推送修复。

建议所有遇到此问题的用户通过 Mac 自带的 **反馈助理（Feedback Assistant）** 提交 Duplicate 工单，附件上传本项目提供的脱敏日志 [`samples/sanitized_reproduction.log`](./samples/sanitized_reproduction.log)，共同敦促苹果工程团队尽快发布维护更新。

---

## License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.
